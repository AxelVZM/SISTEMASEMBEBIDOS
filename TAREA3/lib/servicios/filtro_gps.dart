import 'dart:math' as math;

import 'package:latlong2/latlong.dart';

/// Resultado de procesar una lectura del GPS.
class LecturaFiltrada {
  const LecturaFiltrada({
    required this.punto,
    required this.precision,
    required this.velocidad,
    required this.rumbo,
    required this.enMovimiento,
  });

  /// Posición suavizada.
  final LatLng punto;

  /// Incertidumbre estimada del filtro en metros (1 sigma).
  final double precision;

  /// Velocidad en m/s.
  final double velocidad;

  /// Rumbo en grados (0 = norte), o null si no se conoce.
  final double? rumbo;

  /// true si el desplazamiento supera el ruido del GPS.
  final bool enMovimiento;
}

/// Filtro de Kalman 2D para GPS (modelo de posición con ruido de proceso
/// proporcional a la velocidad) más rechazo de lecturas atípicas.
///
/// Elimina el "temblor" del marcador cuando el teléfono está quieto y los
/// saltos de varias decenas de metros que produce el GPS en ciudad, sin
/// introducir retraso perceptible en movimiento.
class FiltroGps {
  FiltroGps({
    this.precisionMaxima = 40,
    this.velocidadMaximaFisica = 70,
    this.ruidoProcesoMinimo = 2.5,
  });

  /// Lecturas con precisión peor que esto (m) se descartan.
  final double precisionMaxima;

  /// Saltos que implican más de esta velocidad (m/s) se consideran errores.
  final double velocidadMaximaFisica;

  /// Ruido de proceso base en m/s.
  final double ruidoProcesoMinimo;

  static const _metrosPorGradoLat = 111320.0;

  double? _lat;
  double? _lng;
  double _varianza = -1;
  int _tiempoMs = 0;
  double? _ultimoRumbo;
  int _rechazosSeguidos = 0;

  bool get inicializado => _varianza >= 0;

  void reiniciar() {
    _lat = null;
    _lng = null;
    _varianza = -1;
    _ultimoRumbo = null;
    _rechazosSeguidos = 0;
  }

  /// Procesa una lectura. Devuelve null si se descarta.
  LecturaFiltrada? procesar({
    required double latitud,
    required double longitud,
    required double precision,
    required double velocidad,
    required double rumbo,
    required int tiempoMs,
  }) {
    if (!latitud.isFinite || !longitud.isFinite) return null;
    final precisionValida = precision.isFinite && precision > 0 ? precision : 30.0;
    final velocidadValida = velocidad.isFinite && velocidad >= 0 ? velocidad : 0.0;

    if (!inicializado) {
      // La primera lectura se acepta con un umbral más amplio para no
      // quedarse esperando indefinidamente mientras el GPS "calienta".
      if (precisionValida > precisionMaxima * 2.5) return null;
      _lat = latitud;
      _lng = longitud;
      _varianza = precisionValida * precisionValida;
      _tiempoMs = tiempoMs;
      return _resultado(velocidadValida, rumbo, false);
    }

    if (precisionValida > precisionMaxima) {
      _rechazosSeguidos++;
      // Si llevamos muchas lecturas malas seguidas (túnel, interior) se
      // reinicia el filtro para no quedarnos congelados en un punto viejo.
      if (_rechazosSeguidos > 15) reiniciar();
      return null;
    }

    final dtMs = math.max(1, tiempoMs - _tiempoMs);
    final distancia = _distanciaMetros(_lat!, _lng!, latitud, longitud);
    final velocidadImplicita = distancia / (dtMs / 1000);
    if (velocidadImplicita > velocidadMaximaFisica &&
        distancia > precisionValida * 2 &&
        _rechazosSeguidos < 5) {
      _rechazosSeguidos++;
      return null;
    }
    _rechazosSeguidos = 0;

    // Predicción: la incertidumbre crece con el tiempo y con la velocidad.
    // La velocidad Doppler del GNSS es muy fiable en reposo: si es ~0 el
    // filtro se vuelve "rígido" y el marcador deja de temblar.
    // Si la lectura se aleja mucho de la estimación, el teléfono se está
    // moviendo aunque no reporte velocidad (proveedor sin Doppler).
    final quieto = velocidadValida < 0.3 &&
        distancia < math.max(6.0, precisionValida * 1.5);
    final q = quieto
        ? 0.8
        : math.max(ruidoProcesoMinimo, velocidadValida * 1.5);
    _varianza += dtMs * q * q / 1000;
    _tiempoMs = tiempoMs;

    // Corrección.
    final r = precisionValida * precisionValida;
    final k = _varianza / (_varianza + r);
    final latAnterior = _lat!;
    final lngAnterior = _lng!;
    _lat = latAnterior + k * (latitud - latAnterior);
    _lng = lngAnterior + k * (longitud - lngAnterior);
    _varianza = (1 - k) * _varianza;

    final desplazamiento = _distanciaMetros(latAnterior, lngAnterior, _lat!, _lng!);
    // En movimiento si el GNSS reporta velocidad, o si (sin velocidad
    // disponible) el desplazamiento supera claramente el ruido.
    final enMovimiento = velocidadValida > 0.7 ||
        (quieto && desplazamiento > math.max(3.0, precisionValida)) ||
        (!quieto && desplazamiento > math.max(2.0, precisionValida * 0.5));
    double? rumboCalculado;
    if (velocidadValida > 1.0 && rumbo.isFinite && rumbo >= 0) {
      rumboCalculado = rumbo;
    } else if (enMovimiento && desplazamiento > 1.0) {
      rumboCalculado = _rumbo(latAnterior, lngAnterior, _lat!, _lng!);
    }
    return _resultado(velocidadValida, rumboCalculado, enMovimiento);
  }

  LecturaFiltrada _resultado(double velocidad, double? rumbo, bool enMovimiento) {
    if (rumbo != null && rumbo.isFinite && rumbo >= 0) _ultimoRumbo = rumbo;
    return LecturaFiltrada(
      punto: LatLng(_lat!, _lng!),
      precision: math.sqrt(_varianza),
      velocidad: velocidad,
      rumbo: _ultimoRumbo,
      enMovimiento: enMovimiento,
    );
  }

  static double _distanciaMetros(double lat1, double lng1, double lat2, double lng2) {
    final dLat = (lat2 - lat1) * _metrosPorGradoLat;
    final dLng = (lng2 - lng1) *
        _metrosPorGradoLat *
        math.cos((lat1 + lat2) / 2 * math.pi / 180);
    return math.sqrt(dLat * dLat + dLng * dLng);
  }

  static double _rumbo(double lat1, double lng1, double lat2, double lng2) {
    final dLat = lat2 - lat1;
    final dLng = (lng2 - lng1) * math.cos((lat1 + lat2) / 2 * math.pi / 180);
    final grados = math.atan2(dLng, dLat) * 180 / math.pi;
    return (grados + 360) % 360;
  }
}
