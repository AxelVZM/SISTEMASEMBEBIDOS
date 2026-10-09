/// Mapas base disponibles en la app.
///
/// - Satélite y Satélite + calles (Esri World Imagery): fotos reales hasta
///   zoom 19, sin clave. Ideal para comprobar la precisión del GPS.
/// - Calles (OpenStreetMap): nombres de calles detallados, sin clave.
/// - CARTO Voyager: el mapa anterior.
/// - MapTiler Satélite HD: requiere clave gratuita (ver README).
enum CapaMapa {
  satelite('Satélite'),
  hibrido('Satélite + calles'),
  calles('Calles (OpenStreetMap)'),
  carto('CARTO Voyager'),
  maptiler('MapTiler Satélite HD');

  const CapaMapa(this.nombre);

  final String nombre;

  static const _cartoKey = String.fromEnvironment(
    'CARTO_API_KEY',
    defaultValue: 'cb1_4f7e_1_cec811c28cf2ef52dd7565da',
  );

  /// Clave de MapTiler: se pega aquí o se pasa con
  /// --dart-define=MAPTILER_KEY=tu_clave al compilar.
  static const _maptilerKey = String.fromEnvironment(
    'MAPTILER_KEY',
    defaultValue: 'yxn2mt7w4WZM5gDIMwrS',
  );

  /// false si el mapa necesita una clave que no está configurada.
  bool get disponible => this != maptiler || _maptilerKey.isNotEmpty;

  String get url => switch (this) {
    satelite || hibrido =>
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    calles => 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    carto =>
      'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=$_cartoKey',
    maptiler =>
      'https://api.maptiler.com/maps/satellite/256/{z}/{x}/{y}{r}.jpg?key=$_maptilerKey',
  };

  /// Capa transparente con nombres de calles encima del satélite.
  String? get superposicion => this == hibrido
      ? 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}'
      : null;

  /// Zoom máximo con imágenes reales; más cerca se amplía la última.
  int get zoomNativoMaximo => switch (this) {
    satelite || hibrido || calles => 19,
    carto => 18, // CARTO devuelve 403 desde z19.
    maptiler => 20,
  };

  /// Si el proveedor sirve imágenes @2x para pantallas de alta densidad.
  bool get tieneRetina => this == carto || this == maptiler;

  List<String> get atribuciones => switch (this) {
    satelite || hibrido => const ['Esri, Maxar, Earthstar Geographics'],
    calles => const ['OpenStreetMap contributors'],
    carto => const ['OpenStreetMap contributors', 'CARTO'],
    maptiler => const ['MapTiler', 'OpenStreetMap contributors'],
  };

  static CapaMapa desdeNombre(String? nombre) => CapaMapa.values.firstWhere(
    (capa) => capa.name == nombre && capa.disponible,
    orElse: () => maptiler.disponible ? maptiler : hibrido,
  );
}
