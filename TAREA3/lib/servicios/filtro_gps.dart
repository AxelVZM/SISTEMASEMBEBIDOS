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
}

/// Validador de lecturas GPS, punto por punto.
///
/// No suaviza ni inventa posiciones: cada punto aceptado es exactamente la
/// lectura del GPS. Solo descarta lo que es claramente erróneo:
/// - lecturas con precisión peor que [precisionMaxima];
/// - saltos físicamente imposibles (más de [velocidadMaximaFisica] m/s);
/// - el "ruido" cuando el acelerómetro indica que el teléfono está quieto
///   (se mantiene el último punto real).
class FiltroGps {
  FiltroGps({this.precisionMaxima = 30, this.velocidadMaximaFisica = 70});

  final double precisionMaxima;
  final double velocidadMaximaFisica;

  static const _metrosPorGradoLat = 111320.0;

  LatLng? _ultimo;
  double _precisionUltimo = 0;
  int _tiempoMs = 0;
  double? _ultimoRumbo;
  int _rechazosSeguidos = 0;

  bool get inicializado => _ultimo != null;

  void reiniciar() {
    _ultimo = null;
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
    bool sensorEnReposo = false,
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

    // Teléfono quieto (acelerómetro) y GPS sin velocidad: la nueva lectura
    // es ruido; se mantiene el último punto real. Un salto grande (o una
    // velocidad real, p. ej. vehículo) sí se acepta.
    if (sensorEnReposo &&
        velocidadValida < 1.0 &&
        distancia < math.max(25.0, precisionValida * 2)) {
      _tiempoMs = tiempoMs;
      return LecturaFiltrada(
        punto: ultimo,
        precision: _precisionUltimo,
        velocidad: 0,
        rumbo: _ultimoRumbo,
        enMovimiento: false,
        esNuevo: false,
      );
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

  LecturaFiltrada _aceptar(
    LatLng punto,
    double precision,
    double velocidad,
    double? rumbo,
    int tiempoMs,
    bool enMovimiento,
  ) {
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
