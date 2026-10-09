import 'dart:math' as math;

import 'package:latlong2/latlong.dart';

/// Resultado de validar una lectura del GPS.
class LecturaFiltrada {
  const LecturaFiltrada({
    required this.punto,
    required this.precision,
    required this.velocidad,
    required this.rumbo,
    required this.enMovimiento,
    required this.esNuevo,
    this.esCorreccion = false,
  });

  /// Posición real del GPS (sin suavizar ni interpolar).
  final LatLng punto;

  /// Precisión reportada por el GPS en metros.
  final double precision;

  /// Velocidad en m/s.
  final double velocidad;

  /// Rumbo en grados (0 = norte), o null si no se conoce.
  final double? rumbo;

  /// true si el punto representa un desplazamiento real.
  final bool enMovimiento;

  /// true si es una lectura nueva aceptada; false si se mantiene el último
  /// punto real porque el teléfono está quieto (la lectura era ruido).
  final bool esNuevo;

  /// true si el punto corrige la posición actual (lectura mucho más precisa
  /// estando quieto): reemplaza el último punto en vez de trazar un tramo.
  final bool esCorreccion;
}

/// Validador de lecturas GPS, punto por punto.
///
/// No suaviza ni inventa posiciones: cada punto aceptado es exactamente la
/// lectura del GPS. Solo descarta lo que es claramente erróneo:
/// - lecturas con precisión peor que [precisionMaxima];
/// - saltos físicamente imposibles (más de [velocidadMaximaFisica] m/s);
/// - a pie: sin pasos detectados no hay movimiento (agarrar el teléfono no
///   son pasos); un desplazamiento menor que el error del GPS no es medible;
///   y un salto mayor que lo que permiten los pasos dados es ruido. En esos
///   casos se mantiene el último punto real;
/// - en vehículo (velocidad GNSS alta) se acepta cada punto.
class FiltroGps {
  FiltroGps({
    this.precisionMaxima = 30,
    this.velocidadMaximaFisica = 70,
    this.velocidadPeatonMaxima = 3,
    this.velocidadVehiculo = 2.5,
    this.longitudPaso = 0.8,
    this.muestrasPromedioMaximas = 120,
  });

  final double precisionMaxima;
  final double velocidadMaximaFisica;

  /// Velocidad máxima a pie (m/s) cuando no hay datos del acelerómetro.
  final double velocidadPeatonMaxima;

  /// Desde esta velocidad GNSS (m/s, 9 km/h) se considera vehículo.
  final double velocidadVehiculo;

  /// Longitud de un paso (m) para el presupuesto de distancia.
  final double longitudPaso;

  /// Lecturas en reposo que se promedian (120 ≈ 1 min a 500 ms).
  final int muestrasPromedioMaximas;

  static const _metrosPorGradoLat = 111320.0;

  LatLng? _ultimo;
  double _precisionUltimo = 0;
  int _tiempoMs = 0;
  double? _ultimoRumbo;
  int _rechazosSeguidos = 0;
  final _muestrasQuieto = <(LatLng, double)>[];

  bool get inicializado => _ultimo != null;

  void reiniciar() {
    _ultimo = null;
    _muestrasQuieto.clear();
    _ultimoRumbo = null;
    _rechazosSeguidos = 0;
  }

  /// Valida una lectura. Devuelve null si se descarta.
  LecturaFiltrada? procesar({
    required double latitud,
    required double longitud,
    required double precision,
    required double velocidad,
    required double rumbo,
    required int tiempoMs,
    int? pasosDesdeUltimoPunto,
  }) {
    if (!latitud.isFinite || !longitud.isFinite) return null;
    final precisionValida = precision.isFinite && precision > 0 ? precision : 99.0;
    final velocidadValida = velocidad.isFinite && velocidad >= 0 ? velocidad : 0.0;
    final punto = LatLng(latitud, longitud);
    final ultimo = _ultimo;

    if (ultimo == null) {
      // Primer punto: umbral más amplio para no esperar indefinidamente.
      if (precisionValida > precisionMaxima * 2) return null;
      return _aceptar(punto, precisionValida, velocidadValida, rumbo, tiempoMs, false);
    }

    if (precisionValida > precisionMaxima) {
      _rechazosSeguidos++;
      // Muchas lecturas malas seguidas (interior, túnel): se reinicia para
      // aceptar la siguiente aunque esté lejos del último punto.
      if (_rechazosSeguidos > 15) reiniciar();
      return null;
    }

    final dtMs = math.max(1, tiempoMs - _tiempoMs);
    final distancia = _distanciaMetros(ultimo, punto);
    if (distancia / (dtMs / 1000) > velocidadMaximaFisica &&
        distancia > precisionValida * 2 &&
        _rechazosSeguidos < 5) {
      _rechazosSeguidos++;
      return null;
    }
    _rechazosSeguidos = 0;

    // Vehículo/bicicleta: la velocidad Doppler del GNSS es la evidencia de
    // movimiento (no hay pasos). Se acepta el punto tal cual.
    final enVehiculo = velocidadValida >= velocidadVehiculo;
    if (!enVehiculo && distancia < 150) {
      final pasos = pasosDesdeUltimoPunto;

      // 1) Evidencia de movimiento: pasos detectados (o, sin acelerómetro,
      //    velocidad GNSS de caminata). Agarrar el teléfono no son pasos.
      final hayEvidencia = pasos != null ? pasos > 0 : velocidadValida >= 0.7;

      if (!hayEvidencia) return _quieto(punto, precisionValida, tiempoMs);

      // 2) Caminando: cada lectura se muestra al instante (< 1 s), salvo
      //    saltos incoherentes con lo caminado (con 2 pasos no se avanzan
      //    12 m: eso es un salto del GPS).
      final maximo = pasos != null
          ? pasos * longitudPaso * 1.5 + 2.0
          : velocidadPeatonMaxima * (dtMs / 1000) + 2.0;
      if (distancia > maximo) return _mantener();
    }

    final rumboCalculado = velocidadValida > 1.0 && rumbo.isFinite && rumbo >= 0
        ? rumbo
        : (distancia >= 1.0 ? _rumbo(ultimo, punto) : null);
    return _aceptar(
      punto,
      precisionValida,
      velocidadValida,
      rumboCalculado,
      tiempoMs,
      velocidadValida > 0.5 || distancia >= 1.0,
    );
  }

  /// Quieto: la posición es el promedio de las lecturas recibidas en reposo,
  /// ponderado por precisión (1/σ²). Una sola lectura tiene ±3-10 m de error
  /// aleatorio; el promedio de muchas se acerca a la posición real. Se
  /// descartan saltos fuera del margen de error y el punto solo se corrige
  /// cuando el promedio se aleja de forma medible (no tiembla).
  LecturaFiltrada _quieto(LatLng punto, double precision, int tiempoMs) {
    final media = _mediaQuieto();
    if (media != null &&
        _distanciaMetros(media, punto) > 2 * math.max(precision, 5)) {
      return _mantener();
    }
    _muestrasQuieto.add((punto, precision));
    if (_muestrasQuieto.length > muestrasPromedioMaximas) {
      _muestrasQuieto.removeAt(0);
    }

    final nueva = _mediaQuieto()!;
    final precisionMedia = _precisionMediaQuieto();
    // Una lectura mucho más precisa corrige al instante; si no, se esperan
    // varias muestras para que el promedio sea fiable.
    final mejorPrecision = precision < _precisionUltimo * 0.9;
    if (!mejorPrecision && _muestrasQuieto.length < 8) return _mantener();
    // Solo se mueve si el cambio supera la incertidumbre del promedio
    // (σ/√n): con pocas muestras o mucho ruido el punto no tiembla.
    final umbral = mejorPrecision
        ? 1.0
        : math.max(
            1.0,
            1.5 * precisionMedia / math.sqrt(_muestrasQuieto.length),
          );
    if (_distanciaMetros(_ultimo!, nueva) < umbral) return _mantener();
    return _aceptar(
      nueva,
      math.min(_precisionUltimo, precisionMedia),
      0,
      _ultimoRumbo,
      tiempoMs,
      false,
      esCorreccion: true,
      reiniciarPromedio: false,
    );
  }

  LatLng? _mediaQuieto() {
    if (_muestrasQuieto.isEmpty) return null;
    var suma = 0.0, lat = 0.0, lng = 0.0;
    for (final (p, precision) in _muestrasQuieto) {
      final peso = 1 / (precision * precision);
      suma += peso;
      lat += p.latitude * peso;
      lng += p.longitude * peso;
    }
    return LatLng(lat / suma, lng / suma);
  }

  /// Precisión típica de las muestras en reposo (media armónica de σ²).
  double _precisionMediaQuieto() {
    var suma = 0.0;
    for (final (_, precision) in _muestrasQuieto) {
      suma += 1 / (precision * precision);
    }
    return math.sqrt(_muestrasQuieto.length / suma);
  }

  /// Mantiene el último punto real (la lectura nueva se considera ruido).
  /// No actualiza la hora de referencia, para que un desplazamiento real
  /// lento se acepte cuando el tiempo acumulado lo haga plausible.
  LecturaFiltrada _mantener() => LecturaFiltrada(
    punto: _ultimo!,
    precision: _precisionUltimo,
    velocidad: 0,
    rumbo: _ultimoRumbo,
    enMovimiento: false,
    esNuevo: false,
  );

  LecturaFiltrada _aceptar(
    LatLng punto,
    double precision,
    double velocidad,
    double? rumbo,
    int tiempoMs,
    bool enMovimiento, {
    bool esCorreccion = false,
    bool reiniciarPromedio = true,
  }) {
    // Tras un desplazamiento, el promedio en reposo empieza desde este punto.
    if (reiniciarPromedio) {
      _muestrasQuieto
        ..clear()
        ..add((punto, precision));
    }
    _ultimo = punto;
    _precisionUltimo = precision;
    _tiempoMs = tiempoMs;
    if (rumbo != null && rumbo.isFinite && rumbo >= 0) _ultimoRumbo = rumbo;
    return LecturaFiltrada(
      punto: punto,
      precision: precision,
      velocidad: velocidad,
      rumbo: _ultimoRumbo,
      enMovimiento: enMovimiento,
      esNuevo: true,
      esCorreccion: esCorreccion,
    );
  }

  static double _distanciaMetros(LatLng a, LatLng b) {
    final dLat = (b.latitude - a.latitude) * _metrosPorGradoLat;
    final dLng = (b.longitude - a.longitude) *
        _metrosPorGradoLat *
        math.cos((a.latitude + b.latitude) / 2 * math.pi / 180);
    return math.sqrt(dLat * dLat + dLng * dLng);
  }

  static double _rumbo(LatLng a, LatLng b) {
    final dLat = b.latitude - a.latitude;
    final dLng = (b.longitude - a.longitude) *
        math.cos((a.latitude + b.latitude) / 2 * math.pi / 180);
    return (math.atan2(dLng, dLat) * 180 / math.pi + 360) % 360;
  }
}
