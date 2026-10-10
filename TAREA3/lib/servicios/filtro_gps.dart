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
    required this.motivo,
    this.esCorreccion = false,
    this.inicioTramo = false,
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
  /// punto aceptado (la lectura no demostraba movimiento).
  final bool esNuevo;

  /// true si el punto corrige la posición actual (lectura mucho más precisa
  /// estando quieto): reemplaza el último punto en vez de trazar un tramo.
  final bool esCorreccion;

  /// true si empieza un tramo nuevo (primer punto o tras perder la señal):
  /// no se une con una línea al punto anterior.
  final bool inicioTramo;

  /// Decisión del filtro, para el registro de diagnóstico.
  final String motivo;
}

/// Validador de lecturas GPS, punto por punto.
///
/// No suaviza ni inventa posiciones: cada punto aceptado es exactamente una
/// lectura del GPS. La pregunta que responde es "¿me moví de verdad?", y la
/// prueba principal es la **velocidad Doppler** que mide el propio chip GNSS:
/// no depende del ruido de posición (con el teléfono quieto marca
/// ~0-0,2 m/s aunque la posición salte 10-20 m). El podómetro solo se usa si
/// la lectura no trae velocidad (WiFi/antenas bajo techo).
///
/// Reglas:
/// - Se descartan lecturas imprecisas, fuera de orden o físicamente
///   imposibles.
/// - Se acumula la distancia que el Doppler dice que se recorrió desde el
///   último punto aceptado ("presupuesto").
/// - Un punto nuevo se acepta solo si se alejó más que el error del GPS y el
///   presupuesto explica al menos la mitad de ese alejamiento. Así el ruido
///   (alejamiento sin velocidad) nunca dibuja un tramo, y una caminata real
///   (~1-1,5 m/s) avanza en 2-3 s.
/// - Sin movimiento, el punto queda anclado; solo una lectura claramente más
///   precisa y cercana lo corrige.
/// - Tras un hueco de señal se empieza un tramo nuevo (sin línea ficticia).
class FiltroGps {
  FiltroGps({
    this.precisionMaxima = 30,
    this.velocidadMaximaFisica = 70,
    this.velocidadPeatonMaxima = 3,
    this.velocidadVehiculo = 2.5,
    this.longitudPaso = 0.75,
    this.ruidoDoppler = 0.3,
    this.distanciaMinima = 2.0,
    this.huecoSenalMs = 15000,
  });

  final double precisionMaxima;
  final double velocidadMaximaFisica;

  /// Velocidad máxima a pie (m/s) sin Doppler ni acelerómetro.
  final double velocidadPeatonMaxima;

  /// Desde esta velocidad GNSS (m/s, 9 km/h) se considera vehículo.
  final double velocidadVehiculo;

  /// Longitud de un paso (m), solo para el respaldo con podómetro.
  final double longitudPaso;

  /// Velocidad Doppler por debajo de la cual se considera ruido (m/s).
  /// Medido en el Honor quieto: 0-0,14 m/s; caminando: 1,1-1,8 m/s.
  final double ruidoDoppler;

  /// Alejamiento mínimo (m) para trazar un tramo.
  final double distanciaMinima;

  /// Sin lecturas válidas durante este tiempo se considera señal perdida.
  final int huecoSenalMs;

  static const _metrosPorGradoLat = 111320.0;

  LatLng? _ultimo;
  double _precisionUltimo = 0;
  int _tiempoMs = 0;
  double? _ultimoRumbo;
  int _rechazosSeguidos = 0;

  /// Hora de captura de la última lectura procesada.
  int? _ultimaLecturaMs;

  /// Hora de la última lectura con precisión aceptable.
  int? _ultimaValidaMs;

  /// Distancia (m) que el Doppler dice que se recorrió desde el último punto.
  double _presupuestoDoppler = 0;

  /// Hora de la última lectura que trajo velocidad Doppler.
  int? _dopplerVistoMs;

  /// Tiempo seguido con Doppler por debajo del ruido.
  int _quietoDopplerMs = 0;

  /// Punto donde empezó el reposo actual y su precisión.
  LatLng? _origenQuieto;
  double _precisionOrigenQuieto = 0;

  /// Motivo de la última decisión (incluidos los descartes, que devuelven null).
  String ultimaDecision = '';

  bool get inicializado => _ultimo != null;

  void reiniciar() {
    _ultimo = null;
    _origenQuieto = null;
    _ultimoRumbo = null;
    _rechazosSeguidos = 0;
    _ultimaLecturaMs = null;
    _ultimaValidaMs = null;
    _presupuestoDoppler = 0;
    _quietoDopplerMs = 0;
    _dopplerVistoMs = null;
  }

  /// Valida una lectura. Devuelve null si se descarta.
  ///
  /// [precisionVelocidad]: precisión de la velocidad (m/s) que da Android;
  /// 0 significa que la lectura no trae velocidad Doppler.
  LecturaFiltrada? procesar({
    required double latitud,
    required double longitud,
    required double precision,
    required double velocidad,
    required double rumbo,
    required int tiempoMs,
    int? pasosDesdeUltimoPunto,
    double? precisionVelocidad,
  }) {
    if (!latitud.isFinite || !longitud.isFinite ||
        latitud.abs() > 90 || longitud.abs() > 180) {
      return _descartar('coordenadas inválidas');
    }
    final precisionValida = precision.isFinite && precision > 0 ? precision : 99.0;
    final velocidadValida = velocidad.isFinite && velocidad >= 0 ? velocidad : 0.0;
    final punto = LatLng(latitud, longitud);
    final ultimo = _ultimo;

    // Orden temporal: una lectura capturada antes (o a la vez) que la última
    // procesada es antigua o repetida y no puede alterar la secuencia.
    final anteriorMs = _ultimaLecturaMs;
    if (anteriorMs != null && tiempoMs <= anteriorMs) {
      return _descartar('fuera de orden (${tiempoMs - anteriorMs} ms)');
    }
    _ultimaLecturaMs = tiempoMs;
    // ¿La lectura trae velocidad Doppler? (ver hayDoppler más abajo).
    if ((precisionVelocidad ?? 1) > 0 || velocidadValida > 0) {
      _dopplerVistoMs = tiempoMs;
    }

    if (ultimo == null) {
      // Primer punto: umbral más amplio para no esperar indefinidamente.
      if (precisionValida > precisionMaxima * 2) {
        return _descartar('imprecisa para iniciar (±${precisionValida.toStringAsFixed(1)} m)');
      }
      _ultimaValidaMs = tiempoMs;
      return _aceptar(punto, precisionValida, velocidadValida, rumbo, tiempoMs,
          false, motivo: 'primer punto', inicioTramo: true);
    }

    if (precisionValida > precisionMaxima) {
      _rechazosSeguidos++;
      return _descartar('imprecisa (±${precisionValida.toStringAsFixed(1)} m '
          '> ${precisionMaxima.toStringAsFixed(0)} m)');
    }

    final previaValidaMs = _ultimaValidaMs ?? tiempoMs;
    final dtLecturaMs = tiempoMs - previaValidaMs;
    _ultimaValidaMs = tiempoMs;

    // Señal perdida: sin lecturas válidas durante un rato no se sabe por
    // dónde se fue. Se empieza un tramo nuevo en vez de unir con una línea
    // recta ficticia.
    if (dtLecturaMs > huecoSenalMs) {
      final segundos = (dtLecturaMs / 1000).toStringAsFixed(0);
      _rechazosSeguidos = 0;
      _presupuestoDoppler = 0;
      _quietoDopplerMs = 0;
      return _aceptar(punto, precisionValida, velocidadValida, rumbo, tiempoMs,
          false, motivo: 'tramo nuevo tras $segundos s sin señal válida',
          inicioTramo: true);
    }

    final dtMs = math.max(1, tiempoMs - _tiempoMs);
    final distancia = _distanciaMetros(ultimo, punto);
    if (distancia / (dtMs / 1000) > velocidadMaximaFisica &&
        distancia > precisionValida * 2 &&
        _rechazosSeguidos < 5) {
      _rechazosSeguidos++;
      return _descartar('salto imposible (${distancia.toStringAsFixed(0)} m en '
          '${(dtMs / 1000).toStringAsFixed(1)} s)');
    }
    _rechazosSeguidos = 0;

    // Presupuesto de movimiento con la velocidad Doppler. Android a veces
    // entrega velocidad 0,00 sin precisión estando quieto: si hubo Doppler
    // hace poco, ese 0 es un 0 real (no se cae al podómetro, que cuenta
    // pasos falsos al mover el teléfono).
    final dopplerVisto = _dopplerVistoMs;
    final hayDoppler = dopplerVisto != null && tiempoMs - dopplerVisto <= 10000;
    if (hayDoppler) {
      if (velocidadValida >= ruidoDoppler) {
        _presupuestoDoppler += velocidadValida * dtLecturaMs / 1000;
        _quietoDopplerMs = 0;
      } else {
        _quietoDopplerMs += dtLecturaMs;
        // 10 s quieto: lo acumulado por picos de ruido ya no vale.
        if (_quietoDopplerMs > 10000) _presupuestoDoppler = 0;
      }
    }

    // Vehículo/bicicleta: velocidad Doppler alta. Cada lectura es un punto.
    if (velocidadValida >= velocidadVehiculo && hayDoppler) {
      return _aceptarMovimiento(punto, precisionValida, velocidadValida, rumbo,
          tiempoMs, ultimo, distancia,
          'vehículo ${velocidadValida.toStringAsFixed(1)} m/s');
    }

    // Distancia que explica el movimiento real: Doppler si hay; si no,
    // podómetro; si tampoco, la velocidad máxima a pie.
    final double presupuesto;
    final String fuente;
    if (hayDoppler) {
      presupuesto = _presupuestoDoppler;
      fuente = 'Doppler';
    } else if (pasosDesdeUltimoPunto != null) {
      presupuesto = pasosDesdeUltimoPunto * longitudPaso;
      fuente = 'pasos';
    } else {
      presupuesto = velocidadPeatonMaxima * dtMs / 1000;
      fuente = 'tiempo';
    }

    // Error combinado de las dos posiciones (la anterior y la nueva): un
    // alejamiento menor no es medible. Con 0,7× la ruta medía 99 m en una
    // caminata simulada de 78 m (zigzag del ruido); con 1× se mantiene.
    final errorCombinado = math.sqrt(
      precisionValida * precisionValida + _precisionUltimo * _precisionUltimo,
    );
    final umbral = math.max(distanciaMinima, errorCombinado);
    final datos = 'd=${distancia.toStringAsFixed(1)} m, '
        '$fuente=${presupuesto.toStringAsFixed(1)} m, '
        'umbral=${umbral.toStringAsFixed(1)} m';

    if (distancia < umbral) {
      // Sin alejamiento medible. Si además no hay movimiento, es reposo.
      if (presupuesto < distanciaMinima) {
        return _quieto(punto, precisionValida, tiempoMs, datos);
      }
      return _mantener('en camino, aún dentro del error ($datos)');
    }

    // Alejamiento medible: solo es movimiento si la velocidad lo explica.
    // Con Doppler (evidencia fuerte) basta la mitad; con pasos (que pueden
    // ser falsos) se exige el 70 %.
    final proporcion = fuente == 'pasos' ? 0.7 : 0.5;
    if (presupuesto < proporcion * distancia) {
      return _mantener('ruido: se alejó sin moverse ($datos)');
    }
    if (distancia > presupuesto + errorCombinado + distanciaMinima) {
      return _mantener('salto mayor que lo recorrido ($datos)');
    }
    return _aceptarMovimiento(punto, precisionValida, velocidadValida, rumbo,
        tiempoMs, ultimo, distancia, 'movimiento ($datos)');
  }

  LecturaFiltrada _aceptarMovimiento(
    LatLng punto,
    double precision,
    double velocidad,
    double rumbo,
    int tiempoMs,
    LatLng ultimo,
    double distancia,
    String motivo,
  ) {
    _presupuestoDoppler = 0;
    final rumboCalculado = velocidad > 1.0 && rumbo.isFinite && rumbo >= 0
        ? rumbo
        : (distancia >= 1.0 ? _rumbo(ultimo, punto) : null);
    return _aceptar(punto, precision, velocidad, rumboCalculado, tiempoMs, true,
        motivo: motivo);
  }

  /// Quieto: el punto queda ANCLADO. El GPS deriva lentamente aun parado
  /// (medido: 20 m en 25 s con velocidad 0 y ±3 m), así que no se sigue esa
  /// deriva. Solo se corrige si llega una lectura claramente más precisa
  /// (< 70 % del error actual) dentro del margen del origen del reposo: un
  /// primer fix malo converge, pero el punto nunca se aleja de donde empezó.
  LecturaFiltrada _quieto(LatLng punto, double precision, int tiempoMs, String datos) {
    final origen = _origenQuieto ?? _ultimo!;
    final margen = math.max(_precisionOrigenQuieto, 5.0);
    if (precision < _precisionUltimo * 0.7 &&
        _distanciaMetros(origen, punto) <= margen &&
        _distanciaMetros(_ultimo!, punto) <= _precisionUltimo) {
      return _aceptar(punto, precision, 0, _ultimoRumbo, tiempoMs, false,
          motivo: 'corrección en reposo ±${precision.toStringAsFixed(1)} m',
          esCorreccion: true, reiniciarOrigen: false);
    }
    return _mantener('quieto ($datos)');
  }

  LecturaFiltrada? _descartar(String motivo) {
    ultimaDecision = 'descartada: $motivo';
    return null;
  }

  /// Mantiene el último punto aceptado (la lectura no demuestra movimiento).
  LecturaFiltrada _mantener(String motivo) {
    ultimaDecision = 'mantenida: $motivo';
    return LecturaFiltrada(
      punto: _ultimo!,
      precision: _precisionUltimo,
      velocidad: 0,
      rumbo: _ultimoRumbo,
      enMovimiento: false,
      esNuevo: false,
      motivo: ultimaDecision,
    );
  }

  LecturaFiltrada _aceptar(
    LatLng punto,
    double precision,
    double velocidad,
    double? rumbo,
    int tiempoMs,
    bool enMovimiento, {
    required String motivo,
    bool esCorreccion = false,
    bool inicioTramo = false,
    bool reiniciarOrigen = true,
  }) {
    // Tras un desplazamiento, el reposo se ancla en este punto.
    if (reiniciarOrigen) {
      _origenQuieto = punto;
      _precisionOrigenQuieto = precision;
    }
    _ultimo = punto;
    _precisionUltimo = precision;
    _tiempoMs = tiempoMs;
    if (rumbo != null && rumbo.isFinite && rumbo >= 0) _ultimoRumbo = rumbo;
    ultimaDecision = 'aceptada: $motivo';
    return LecturaFiltrada(
      punto: punto,
      precision: precision,
      velocidad: velocidad,
      rumbo: _ultimoRumbo,
      enMovimiento: enMovimiento,
      esNuevo: true,
      esCorreccion: esCorreccion,
      inicioTramo: inicioTramo,
      motivo: ultimaDecision,
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
