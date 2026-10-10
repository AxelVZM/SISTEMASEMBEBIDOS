import 'package:latlong2/latlong.dart';

import 'filtro_gps.dart';

/// Un vértice de la ruta: una lectura GPS real aceptada por el filtro.
class PuntoRuta {
  const PuntoRuta({
    required this.punto,
    required this.precision,
    required this.sampleId,
    required this.tiempoMs,
  });

  final LatLng punto;
  final double precision;

  /// Identificador estable con el que se guarda en el servidor.
  final String sampleId;

  /// Hora de captura (ms desde epoch).
  final int tiempoMs;
}

/// Cambio que produce una lectura en la ruta. Es exactamente lo que se envía
/// al servidor, para que app, PostgreSQL y panel tengan la misma ruta.
class CambioRuta {
  const CambioRuta({
    required this.punto,
    required this.inicioTramo,
    this.reemplaza,
  });

  final PuntoRuta punto;

  /// true: este punto empieza un tramo (no se une con el anterior).
  final bool inicioTramo;

  /// sampleId del punto que este reemplaza (corrección en reposo).
  final String? reemplaza;
}

/// Ruta del recorrido en tramos. Cada tramo es una lista de puntos GPS reales
/// en orden de captura; los tramos se separan al pausar o al perder la señal
/// para no dibujar líneas rectas ficticias.
class RutaGps {
  final tramos = <List<PuntoRuta>>[];

  /// Distancia recorrida: suma de los tramos (los huecos no cuentan).
  double distanciaMetros = 0;

  bool _cortar = true;

  static const _distancia = Distance();

  int get totalPuntos => tramos.fold(0, (total, tramo) => total + tramo.length);

  List<LatLng> get todosLosPuntos => [
    for (final tramo in tramos)
      for (final p in tramo) p.punto,
  ];

  PuntoRuta? get ultimo => tramos.isEmpty || tramos.last.isEmpty ? null : tramos.last.last;

  void limpiar() {
    tramos.clear();
    distanciaMetros = 0;
    _cortar = true;
  }

  /// El siguiente punto empieza un tramo nuevo (p. ej. tras una pausa).
  void cortar() => _cortar = true;

  /// Aplica una lectura aceptada. Devuelve null si no cambia la ruta (lectura
  /// mantenida, fuera de orden o sin desplazamiento).
  CambioRuta? agregar(LecturaFiltrada lectura, String sampleId, int tiempoMs) {
    if (!lectura.esNuevo) return null;
    final anterior = ultimo;
    // Nunca se inserta un punto más antiguo que el último de la ruta.
    if (anterior != null && tiempoMs <= anterior.tiempoMs) return null;

    final nuevo = PuntoRuta(
      punto: lectura.punto,
      precision: lectura.precision,
      sampleId: sampleId,
      tiempoMs: tiempoMs,
    );

    if (lectura.inicioTramo || _cortar || anterior == null) {
      tramos.add([nuevo]);
      _cortar = false;
      return CambioRuta(punto: nuevo, inicioTramo: true);
    }

    if (lectura.esCorreccion) {
      // Misma posición, más precisa: reemplaza el último punto (no es un
      // desplazamiento y no suma distancia).
      final tramo = tramos.last;
      tramo[tramo.length - 1] = nuevo;
      return CambioRuta(
        punto: nuevo,
        inicioTramo: tramo.length == 1,
        reemplaza: anterior.sampleId,
      );
    }

    final metros = _distancia.as(LengthUnit.Meter, anterior.punto, nuevo.punto);
    if (metros < 0.5) return null;
    tramos.last.add(nuevo);
    distanciaMetros += metros;
    return CambioRuta(punto: nuevo, inicioTramo: false);
  }
}
