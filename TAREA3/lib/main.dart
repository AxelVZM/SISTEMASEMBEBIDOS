import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:battery_plus/battery_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:sensors_plus/sensors_plus.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'modelos/ubicacion_local.dart';
import 'servicios/base_datos_local.dart';
import 'servicios/detector_pasos.dart';
import 'servicios/filtro_gps.dart';
import 'servicios/seguimiento_remoto.dart';

const _versionApp = '2.0.0';
const _canalPantalla = MethodChannel('movimiento/pantalla');

/// Mantiene la pantalla encendida mientras se registra (solo Android).
Future<void> _mantenerPantallaEncendida(bool activar) async {
  try {
    await _canalPantalla.invokeMethod<void>('mantenerEncendida', activar);
  } catch (_) {
    // Otras plataformas o tests.
  }
}

void main() {
  runApp(const AplicacionMovimiento());
}

class AplicacionMovimiento extends StatelessWidget {
  const AplicacionMovimiento({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Rastro',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xff126e64),
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: const Color(0xfff5f7f4),
        useMaterial3: true,
      ),
      home: const PantallaMovimiento(),
    );
  }
}

class RegistroMovimiento {
  const RegistroMovimiento({
    required this.puntos,
    required this.fechaInicio,
    required this.fechaFin,
    required this.distanciaMetros,
    required this.velocidadMaximaKmh,
    required this.velocidadPromedioKmh,
    required this.aceleracionPromedio,
    required this.tipoMovimiento,
    required this.bateriaInicio,
    required this.bateriaFin,
  });

  final List<LatLng> puntos;
  final DateTime fechaInicio;
  final DateTime fechaFin;
  final double distanciaMetros;
  final double velocidadMaximaKmh;
  final double velocidadPromedioKmh;
  final double aceleracionPromedio;
  final String tipoMovimiento;
  final int bateriaInicio;
  final int bateriaFin;

  Duration get duracion => fechaFin.difference(fechaInicio);

  Map<String, dynamic> toJson() => {
    'fechaInicio': fechaInicio.toIso8601String(),
    'fechaFin': fechaFin.toIso8601String(),
    'distanciaMetros': distanciaMetros,
    'velocidadMaximaKmh': velocidadMaximaKmh,
    'velocidadPromedioKmh': velocidadPromedioKmh,
    'aceleracionPromedio': aceleracionPromedio,
    'tipoMovimiento': tipoMovimiento,
    'bateriaInicio': bateriaInicio,
    'bateriaFin': bateriaFin,
    'puntos': puntos
        .map(
          (punto) => {'latitud': punto.latitude, 'longitud': punto.longitude},
        )
        .toList(),
  };

  factory RegistroMovimiento.fromJson(Map<String, dynamic> json) {
    final fecha = DateTime.parse(
      json['fechaInicio'] as String? ?? json['fecha'] as String,
    );
    final puntos = (json['puntos'] as List<dynamic>? ?? [])
        .map(
          (punto) => LatLng(
            (punto['latitud'] as num).toDouble(),
            (punto['longitud'] as num).toDouble(),
          ),
        )
        .toList();
    return RegistroMovimiento(
      puntos: puntos,
      fechaInicio: fecha,
      fechaFin: DateTime.parse(
        json['fechaFin'] as String? ?? fecha.toIso8601String(),
      ),
      distanciaMetros: (json['distanciaMetros'] as num?)?.toDouble() ?? 0,
      velocidadMaximaKmh: (json['velocidadMaximaKmh'] as num?)?.toDouble() ?? 0,
      velocidadPromedioKmh:
          (json['velocidadPromedioKmh'] as num?)?.toDouble() ?? 0,
      aceleracionPromedio:
          (json['aceleracionPromedio'] as num?)?.toDouble() ?? 0,
      tipoMovimiento: json['tipoMovimiento'] as String? ?? 'Sin clasificar',
      bateriaInicio: (json['bateriaInicio'] as num?)?.toInt() ?? 0,
      bateriaFin: (json['bateriaFin'] as num?)?.toInt() ?? 0,
    );
  }
}

/// Telemetría instantánea mostrada en pantalla.
class Telemetria {
  const Telemetria({
    this.velocidadKmh = 0,
    this.precision,
    this.frecuenciaHz,
    this.edadFixMs,
    this.senalDebil = false,
  });

  final double velocidadKmh;
  final double? precision;
  final double? frecuenciaHz;
  final int? edadFixMs;
  final bool senalDebil;
}

class PantallaMovimiento extends StatefulWidget {
  const PantallaMovimiento({super.key});

  @override
  State<PantallaMovimiento> createState() => _PantallaMovimientoState();
}

class _PantallaMovimientoState extends State<PantallaMovimiento> {
  static const _ubicacionInicial = LatLng(-13.53195, -71.96746);
  static const _cartoApiKey = String.fromEnvironment(
    'CARTO_API_KEY',
    defaultValue: 'cb1_4f7e_1_cec811c28cf2ef52dd7565da',
  );
  static const _intervalosDisponibles = [250, 500, 1000, 2000];

  final _mapController = MapController();
  final _bateria = Battery();
  final _baseDatos = BaseDatosLocal.instancia;
  final _seguimientoRemoto = SeguimientoRemoto();
  final _filtro = FiltroGps();
  final _historial = <RegistroMovimiento>[];

  /// Segmentos del recorrido (se abre uno nuevo al reanudar tras una pausa).
  final _segmentos = <List<LatLng>>[];

  // Valores que cambian muchas veces por segundo: se notifican sin
  // reconstruir toda la pantalla (el acelerómetro antes redibujaba el mapa
  // a ~60 Hz y causaba tirones).
  final _posicionMostrada = ValueNotifier<LatLng?>(null);
  final _pasos = ValueNotifier<int>(0);
  final _telemetria = ValueNotifier(const Telemetria());

  double _rumbo = 0;
  double _precisionActual = 0;

  StreamSubscription<Position>? _ubicacionSuscripcion;
  StreamSubscription<AccelerometerEvent>? _sensorSuscripcion;
  Timer? _temporizadorBateria;
  Timer? _temporizadorEdad;

  // Podómetro: solo los pasos reales (picos rítmicos) justifican que la
  // posición avance a pie. Agarrar o mover el teléfono no son pasos.
  final _detectorPasos = DetectorPasos();
  int _pasosDesdeUltimoPunto = 0;
  int? _ultimoSensorMs;
  int _ultimoLogMs = 0;
  double _distanciaMetros = 0;
  double _velocidadMaximaKmh = 0;
  double _velocidadTotalKmh = 0;
  double _aceleracionTotal = 0;
  int _muestrasAceleracion = 0;
  int _muestrasVelocidad = 0;
  int _bateriaInicio = 0;
  int? _nivelBateria;
  int _contadorMuestras = 0;
  DateTime? _inicioRegistro;
  DateTime? _ultimoFix;
  double? _frecuenciaHz;
  bool _registrando = false;
  bool _estaMoviendose = false;
  bool _esperandoFix = false;
  bool _cargando = true;
  bool _pausado = false;
  bool _seguir = true;
  bool _nuevoSegmento = true;
  bool _usarServicioPrimerPlano = true;
  String _deviceId = '';
  int _intervaloMilisegundos = 500;
  String? _mensaje;

  String get _mapTileUrl =>
      'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=$_cartoApiKey';

  List<LatLng> get _todosLosPuntos => [for (final s in _segmentos) ...s];

  int get _cantidadPuntos =>
      _segmentos.fold(0, (total, segmento) => total + segmento.length);

  @override
  void initState() {
    super.initState();
    _cargarHistorial();
    _cargarConfiguracion();
    _mostrarUltimaUbicacionConocida();
  }

  Future<void> _cargarConfiguracion() async {
    final preferencias = await SharedPreferences.getInstance();
    var deviceId = preferencias.getString('device_id');
    if (deviceId == null || deviceId.isEmpty) {
      deviceId =
          'android-${DateTime.now().microsecondsSinceEpoch}-${math.Random.secure().nextInt(1 << 32).toRadixString(16)}';
      await preferencias.setString('device_id', deviceId);
    }
    final intervalo = preferencias.getInt('intervalo_gps') ?? 500;
    if (!mounted) return;
    setState(() {
      _deviceId = deviceId!;
      _intervaloMilisegundos = _intervalosDisponibles.contains(intervalo)
          ? intervalo
          : 500;
    });
  }

  Future<void> _cargarHistorial() async {
    final preferencias = await SharedPreferences.getInstance();
    final registros = preferencias.getStringList('registros_movimiento') ?? [];
    if (!mounted) return;
    setState(() {
      _historial
        ..clear()
        ..addAll(
          registros.map(
            (registro) => RegistroMovimiento.fromJson(
              jsonDecode(registro) as Map<String, dynamic>,
            ),
          ),
        );
      _cargando = false;
    });
  }

  /// Centra el mapa en la última posición conocida sin pedir permisos.
  Future<void> _mostrarUltimaUbicacionConocida() async {
    try {
      final permiso = await Geolocator.checkPermission();
      if (permiso != LocationPermission.always &&
          permiso != LocationPermission.whileInUse) {
        return;
      }
      final ultima = await Geolocator.getLastKnownPosition();
      if (ultima == null || !mounted || _posicionMostrada.value != null) return;
      final punto = LatLng(ultima.latitude, ultima.longitude);
      _posicionMostrada.value = punto;
      _mapController.move(punto, 17);
    } catch (_) {
      // Sin plugin (tests) o sin servicio de ubicación.
    }
  }

  Future<void> _alternarRegistro() async {
    if (_registrando) {
      await _detenerRegistro();
    } else {
      await _iniciarRegistro();
    }
  }

  Future<bool> _verificarPermisos() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      if (mounted) {
        setState(
          () => _mensaje =
              'La ubicación está desactivada. Actívala para comenzar.',
        );
      }
      await Geolocator.openLocationSettings();
      return false;
    }
    var permiso = await Geolocator.checkPermission();
    if (permiso == LocationPermission.denied) {
      permiso = await Geolocator.requestPermission();
    }
    if (permiso == LocationPermission.deniedForever) {
      if (mounted) {
        setState(
          () => _mensaje =
              'El permiso está bloqueado. Actívalo en Ajustes > Aplicaciones > Movimiento GPS > Permisos.',
        );
      }
      await Geolocator.openAppSettings();
      return false;
    }
    if (permiso != LocationPermission.always &&
        permiso != LocationPermission.whileInUse) {
      if (mounted) {
        setState(
          () => _mensaje =
              'Debes permitir el acceso a la ubicación para registrar el recorrido.',
        );
      }
      return false;
    }
    // Sin precisión exacta (Android 12+) el punto puede estar a ~2 km.
    try {
      final precision = await Geolocator.getLocationAccuracy();
      if (precision == LocationAccuracyStatus.reduced && mounted) {
        setState(
          () => _mensaje =
              'Activa "Ubicación precisa" en los permisos de la app para un seguimiento exacto.',
        );
      }
    } catch (_) {}
    if (await Permission.notification.isDenied) {
      await Permission.notification.request();
    }
    return true;
  }

  Future<void> _iniciarRegistro() async {
    if (!await _verificarPermisos()) return;
    if (_deviceId.isEmpty) await _cargarConfiguracion();

    _filtro.reiniciar();
    _detectorPasos.reiniciar();
    _pasosDesdeUltimoPunto = 0;
    _pasos.value = 0;
    _nivelBateria = await _leerBateria();
    _bateriaInicio = _nivelBateria ?? 0;
    _seguimientoRemoto.bateria = _nivelBateria;
    if (!mounted) return;
    setState(() {
      _segmentos.clear();
      _nuevoSegmento = true;
      _registrando = true;
      _esperandoFix = true;
      _pausado = false;
      _seguir = true;
      _mensaje = null;
      _inicioRegistro = DateTime.now();
      _ultimoFix = null;
      _frecuenciaHz = null;
      _contadorMuestras = 0;
      _distanciaMetros = 0;
      _velocidadMaximaKmh = 0;
      _velocidadTotalKmh = 0;
      _aceleracionTotal = 0;
      _muestrasAceleracion = 0;
      _muestrasVelocidad = 0;
    });
    _telemetria.value = const Telemetria();

    // La conexión se abre en paralelo: el GPS empieza a registrar de
    // inmediato y las muestras quedan en cola local hasta que haya enlace.
    unawaited(
      _seguimientoRemoto.iniciar(
        deviceId: _deviceId,
        nombre: 'Mi celular',
        version: _versionApp,
      ),
    );
    _suscribirSensores();
    unawaited(_mantenerPantallaEncendida(true));

    _temporizadorBateria?.cancel();
    _temporizadorBateria = Timer.periodic(const Duration(seconds: 30), (
      _,
    ) async {
      _nivelBateria = await _leerBateria();
      _seguimientoRemoto.bateria = _nivelBateria;
    });
    _temporizadorEdad?.cancel();
    _temporizadorEdad = Timer.periodic(
      const Duration(milliseconds: 500),
      (_) => _actualizarEdadFix(),
    );
  }

  Future<int?> _leerBateria() async {
    try {
      return await _bateria.batteryLevel;
    } catch (_) {
      return null;
    }
  }

  LocationSettings _configuracionGps() {
    if (defaultTargetPlatform == TargetPlatform.android) {
      return AndroidSettings(
        accuracy: LocationAccuracy.bestForNavigation,
        // 0 m: antes con 5 m, caminando solo llegaba un punto cada 3-4 s.
        distanceFilter: 0,
        intervalDuration: Duration(milliseconds: _intervaloMilisegundos),
        foregroundNotificationConfig: _usarServicioPrimerPlano
            ? const ForegroundNotificationConfig(
                notificationTitle:
                    'Movimiento GPS está registrando tu recorrido',
                notificationText: 'Seguimiento en tiempo real activo',
                notificationChannelName: 'Seguimiento de movimiento',
                setOngoing: true,
                enableWakeLock: true,
                enableWifiLock: true,
              )
            : null,
      );
    }
    if (defaultTargetPlatform == TargetPlatform.iOS) {
      return AppleSettings(
        accuracy: LocationAccuracy.bestForNavigation,
        distanceFilter: 0,
        activityType: ActivityType.fitness,
        pauseLocationUpdatesAutomatically: false,
        showBackgroundLocationIndicator: true,
      );
    }
    return const LocationSettings(
      accuracy: LocationAccuracy.bestForNavigation,
      distanceFilter: 0,
    );
  }

  void _suscribirSensores() {
    unawaited(_ubicacionSuscripcion?.cancel());
    unawaited(_sensorSuscripcion?.cancel());
    _ubicacionSuscripcion = Geolocator.getPositionStream(
      locationSettings: _configuracionGps(),
    ).listen(_agregarUbicacion, onError: _errorGps);
    // 50 Hz: suficiente para distinguir el ritmo de los pasos (~2 Hz).
    _sensorSuscripcion = accelerometerEventStream(
      samplingPeriod: SensorInterval.gameInterval,
    ).listen(_leerAcelerometro, onError: (_) {});
    unawaited(_primeraPosicion());
  }

  /// Pide una lectura inmediata para no depender solo del flujo continuo
  /// (algunos equipos tardan varios segundos en emitir la primera muestra).
  Future<void> _primeraPosicion() async {
    try {
      final posicion = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.best,
          timeLimit: Duration(seconds: 15),
        ),
      );
      if (_registrando && !_pausado && _esperandoFix) {
        _agregarUbicacion(posicion);
      }
    } catch (_) {
      // El flujo continuo seguirá intentándolo.
    }
  }

  void _errorGps(Object error) {
    if (!mounted) return;
    // Si el servicio en primer plano falla (restricciones del fabricante),
    // se reintenta una vez sin él para no quedarse sin GPS.
    if (_usarServicioPrimerPlano &&
        error is! LocationServiceDisabledException &&
        error is! PermissionDeniedException) {
      _usarServicioPrimerPlano = false;
      if (_registrando && !_pausado) _suscribirSensores();
      setState(
        () => _mensaje =
            'GPS en modo básico: mantén la app abierta durante el recorrido.',
      );
      return;
    }
    setState(() {
      _mensaje = switch (error) {
        LocationServiceDisabledException() =>
          'La ubicación se desactivó en el teléfono.',
        PermissionDeniedException() =>
          'Android retiró el permiso de ubicación.',
        _ => 'Error del GPS: $error',
      };
    });
  }

  void _agregarUbicacion(Position posicion) {
    if (!mounted) return;
    final ahora = DateTime.now();

    // Frecuencia real de muestras (media móvil exponencial).
    final anterior = _ultimoFix;
    if (anterior != null) {
      final dt = ahora.difference(anterior).inMilliseconds;
      if (dt > 0) {
        final hz = 1000 / dt;
        _frecuenciaHz = _frecuenciaHz == null
            ? hz
            : _frecuenciaHz! * 0.8 + hz * 0.2;
      }
    }
    _ultimoFix = ahora;

    // Edad de la lectura. Si el reloj del GPS y el del sistema no coinciden
    // (diferencia negativa o enorme) se usa el instante de recepción. Las
    // lecturas que Android entrega en lote conservan su hora real.
    var edad = ahora.difference(posicion.timestamp);
    if (edad.isNegative || edad > const Duration(minutes: 5)) {
      edad = Duration.zero;
    }

    final lectura = _filtro.procesar(
      latitud: posicion.latitude,
      longitud: posicion.longitude,
      precision: posicion.accuracy,
      velocidad: posicion.speed,
      rumbo: posicion.heading,
      tiempoMs: ahora.subtract(edad).millisecondsSinceEpoch,
      // Sin acelerómetro activo (null) el filtro usa un límite de velocidad.
      pasosDesdeUltimoPunto: _sensorActivo ? _pasosDesdeUltimoPunto : null,
    );
    if (lectura != null && lectura.esNuevo) _pasosDesdeUltimoPunto = 0;

    if (lectura == null) {
      _telemetria.value = Telemetria(
        velocidadKmh: _telemetria.value.velocidadKmh,
        precision: posicion.accuracy,
        frecuenciaHz: _frecuenciaHz,
        edadFixMs: edad.inMilliseconds,
        senalDebil: true,
      );
      return;
    }

    final punto = lectura.punto;
    final velocidadKmh = lectura.enMovimiento ? lectura.velocidad * 3.6 : 0.0;
    _telemetria.value = Telemetria(
      velocidadKmh: velocidadKmh,
      precision: posicion.accuracy,
      frecuenciaHz: _frecuenciaHz,
      edadFixMs: edad.inMilliseconds,
    );

    // Teléfono quieto: la lectura era ruido y se mantiene el último punto
    // real. No se dibuja, no se suma distancia y no se envía.
    if (!lectura.esNuevo) {
      if (_esperandoFix) setState(() => _esperandoFix = false);
      return;
    }

    _precisionActual = lectura.precision;
    if (lectura.rumbo != null) _rumbo = lectura.rumbo!;

    // Ruta punto a punto: cada lectura real aceptada es un vértice.
    final primerFix = _esperandoFix;
    if (_nuevoSegmento || _segmentos.isEmpty) {
      _segmentos.add([punto]);
      _nuevoSegmento = false;
    } else {
      final segmento = _segmentos.last;
      final distancia = Geolocator.distanceBetween(
        segmento.last.latitude,
        segmento.last.longitude,
        punto.latitude,
        punto.longitude,
      );
      if (distancia >= 0.5) {
        segmento.add(punto);
        _distanciaMetros += distancia;
      }
    }
    if (lectura.enMovimiento) {
      _velocidadMaximaKmh = math.max(_velocidadMaximaKmh, velocidadKmh);
      _velocidadTotalKmh += velocidadKmh;
      _muestrasVelocidad++;
    }
    _contadorMuestras++;

    // El marcador salta exactamente a la posición del GPS (sin animación).
    _posicionMostrada.value = punto;
    if (_seguir) {
      _mapController.move(
        punto,
        primerFix ? math.max(_mapController.camera.zoom, 17) : _mapController.camera.zoom,
      );
    }
    setState(() => _esperandoFix = false);

    // Marca de tiempo alineada con el reloj del servidor.
    final marcaServidor = ahora
        .subtract(edad)
        .add(Duration(milliseconds: _seguimientoRemoto.offsetRelojMs));
    unawaited(
      _guardarYEnviar(
        UbicacionLocal(
          sampleId:
              '$_deviceId-${marcaServidor.microsecondsSinceEpoch}-$_contadorMuestras',
          deviceId: _deviceId,
          latitude: punto.latitude,
          longitude: punto.longitude,
          timestamp: marcaServidor,
          accuracy: posicion.accuracy,
          speed: lectura.enMovimiento ? lectura.velocidad : 0,
          heading: _rumbo,
          altitude: posicion.altitude.isFinite ? posicion.altitude : null,
          battery: _nivelBateria,
        ),
      ),
    );
  }

  Future<void> _guardarYEnviar(UbicacionLocal ubicacion) async {
    if (_deviceId.isEmpty) return;
    // Primero se guarda en SQLite (~1-3 ms) y luego se envía por POST: si no
    // hay red, la muestra queda pendiente y viaja después en un lote.
    try {
      await _baseDatos.insertarUbicacion(ubicacion);
    } catch (_) {}
    _seguimientoRemoto.enviar(ubicacion);
  }

  void _actualizarEdadFix() {
    final ultimo = _ultimoFix;
    if (ultimo == null || _pausado) return;
    final edad = DateTime.now().difference(ultimo).inMilliseconds;
    final actual = _telemetria.value;
    if (edad > 3000 && !actual.senalDebil) {
      _telemetria.value = Telemetria(
        velocidadKmh: actual.velocidadKmh,
        precision: actual.precision,
        frecuenciaHz: actual.frecuenciaHz,
        edadFixMs: edad,
        senalDebil: true,
      );
    }
  }

  void _leerAcelerometro(AccelerometerEvent evento) {
    // Módulo de la aceleración incluyendo gravedad (~9.8 m/s² en reposo).
    final modulo = math.sqrt(
      evento.x * evento.x + evento.y * evento.y + evento.z * evento.z,
    );
    final ahora = DateTime.now().millisecondsSinceEpoch;
    _ultimoSensorMs = ahora;
    final nuevos = _detectorPasos.procesar(modulo, ahora);
    if (nuevos > 0) {
      _pasosDesdeUltimoPunto += nuevos;
      _pasos.value = _detectorPasos.pasosTotales;
    }
    _aceleracionTotal += (modulo - 9.81).abs();
    _muestrasAceleracion++;

    // Diagnóstico (visible con: adb logcat -s flutter).
    if (ahora - _ultimoLogMs > 2000) {
      _ultimoLogMs = ahora;
      debugPrint(
        '[rastro] pasos=${_detectorPasos.pasosTotales} '
        'pendientes=$_pasosDesdeUltimoPunto '
        'caminando=${_detectorPasos.caminando(ahora)}',
      );
    }

    final moviendose = _detectorPasos.caminando(ahora);
    if (moviendose != _estaMoviendose && mounted) {
      setState(() => _estaMoviendose = moviendose);
    }
  }

  /// true si el acelerómetro está entregando datos.
  bool get _sensorActivo =>
      _ultimoSensorMs != null &&
      DateTime.now().millisecondsSinceEpoch - _ultimoSensorMs! < 1500;

  Future<void> _detenerRegistro() async {
    await _ubicacionSuscripcion?.cancel();
    await _sensorSuscripcion?.cancel();
    _ubicacionSuscripcion = null;
    _sensorSuscripcion = null;
    _temporizadorBateria?.cancel();
    _temporizadorEdad?.cancel();
    unawaited(_mantenerPantallaEncendida(false));
    unawaited(_seguimientoRemoto.detener());
    final puntos = _todosLosPuntos;
    if (puntos.isNotEmpty) {
      final fechaFin = DateTime.now();
      final fechaInicio = _inicioRegistro ?? fechaFin;
      final velocidadPromedio = _muestrasVelocidad == 0
          ? 0.0
          : _velocidadTotalKmh / _muestrasVelocidad;
      final aceleracionPromedio = _muestrasAceleracion == 0
          ? 0.0
          : _aceleracionTotal / _muestrasAceleracion;
      final registro = RegistroMovimiento(
        puntos: puntos,
        fechaInicio: fechaInicio,
        fechaFin: fechaFin,
        distanciaMetros: _distanciaMetros,
        velocidadMaximaKmh: _velocidadMaximaKmh,
        velocidadPromedioKmh: velocidadPromedio,
        aceleracionPromedio: aceleracionPromedio,
        tipoMovimiento: _tipoMovimiento(velocidadPromedio, aceleracionPromedio),
        bateriaInicio: _bateriaInicio,
        bateriaFin: await _leerBateria() ?? _bateriaInicio,
      );
      _historial.insert(0, registro);
      final preferencias = await SharedPreferences.getInstance();
      await preferencias.setStringList(
        'registros_movimiento',
        _historial.map((item) => jsonEncode(item.toJson())).toList(),
      );
    }
    if (mounted) {
      setState(() {
        _registrando = false;
        _esperandoFix = false;
        _pausado = false;
        _inicioRegistro = null;
        _ultimoFix = null;
      });
    }
  }

  Future<void> _alternarPausa() async {
    if (!_registrando) return;
    if (_pausado) {
      _filtro.reiniciar();
      _nuevoSegmento = true;
      _ultimoFix = null;
      _frecuenciaHz = null;
      _suscribirSensores();
      setState(() => _pausado = false);
    } else {
      await _ubicacionSuscripcion?.cancel();
      await _sensorSuscripcion?.cancel();
      _ubicacionSuscripcion = null;
      _sensorSuscripcion = null;
      _ultimoSensorMs = null;
      if (mounted) setState(() => _pausado = true);
    }
  }

  String _tipoMovimiento(double velocidadKmh, double aceleracionPromedio) {
    if (velocidadKmh >= 18) return 'Vehículo';
    if (velocidadKmh >= 7) return 'Corriendo';
    if (velocidadKmh >= 1.5) return 'Caminando';
    if (aceleracionPromedio > 1.2) return 'Teléfono en movimiento';
    return 'En reposo';
  }

  void _centrar() {
    final punto = _posicionMostrada.value;
    setState(() => _seguir = true);
    if (punto != null) {
      _mapController.move(punto, math.max(_mapController.camera.zoom, 17));
    }
  }

  @override
  void dispose() {
    _ubicacionSuscripcion?.cancel();
    _sensorSuscripcion?.cancel();
    _temporizadorBateria?.cancel();
    _temporizadorEdad?.cancel();
    _seguimientoRemoto.dispose();
    _posicionMostrada.dispose();
    _pasos.dispose();
    _telemetria.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final color = tema.colorScheme.primary;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rastro'),
        actions: [
          IconButton(
            tooltip: 'Configurar intervalo GPS',
            onPressed: _mostrarConfiguracionIntervalo,
            icon: const Icon(Icons.tune_rounded),
          ),
          IconButton(
            tooltip: 'Historial de recorridos',
            onPressed: _cargando ? null : () => _mostrarHistorial(context),
            icon: const Icon(Icons.history_rounded),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Stack(
              children: [
                FlutterMap(
                  mapController: _mapController,
                  options: MapOptions(
                    initialCenter: _ubicacionInicial,
                    initialZoom: 15,
                    minZoom: 3,
                    maxZoom: 19,
                    // Sin rotación: el mapa queda siempre con el norte arriba
                    // y la flecha indica el rumbo real.
                    interactionOptions: const InteractionOptions(
                      flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
                    ),
                    onPositionChanged: (camera, gesto) {
                      if (gesto && _seguir) setState(() => _seguir = false);
                    },
                  ),
                  children: [
                    TileLayer(
                      urlTemplate: _mapTileUrl,
                      retinaMode: RetinaMode.isHighDensity(context),
                      // CARTO solo publica mosaicos hasta z18 (z19+ da 403 y
                      // dejaba el mapa en blanco); más cerca se amplía el z18.
                      maxNativeZoom: 18,
                      evictErrorTileStrategy:
                          EvictErrorTileStrategy.notVisibleRespectMargin,
                      // Precarga mosaicos alrededor para no ver huecos grises al moverse.
                      keepBuffer: 4,
                      panBuffer: 1,
                      userAgentPackageName: 'com.example.app',
                    ),
                    if (_segmentos.isNotEmpty)
                      PolylineLayer(
                        polylines: [
                          for (final segmento in _segmentos)
                            if (segmento.length > 1)
                              Polyline(
                                points: segmento,
                                color: color,
                                strokeWidth: 4,
                              ),
                        ],
                      ),
                    // Un punto por cada lectura real del GPS (vértices de la ruta).
                    if (_segmentos.isNotEmpty)
                      CircleLayer(
                        circles: [
                          for (final segmento in _segmentos)
                            for (final punto in segmento)
                              CircleMarker(
                                point: punto,
                                radius: 3,
                                color: Colors.white,
                                borderColor: color,
                                borderStrokeWidth: 2,
                              ),
                        ],
                      ),
                    ValueListenableBuilder<LatLng?>(
                      valueListenable: _posicionMostrada,
                      builder: (context, posicion, _) {
                        if (posicion == null) return const SizedBox.shrink();
                        return Stack(
                          children: [
                            if (_registrando && _precisionActual > 0)
                              CircleLayer(
                                circles: [
                                  CircleMarker(
                                    point: posicion,
                                    radius: _precisionActual,
                                    useRadiusInMeter: true,
                                    color: color.withValues(alpha: 0.12),
                                    borderColor: color.withValues(alpha: 0.4),
                                    borderStrokeWidth: 1,
                                  ),
                                ],
                              ),
                            MarkerLayer(
                              markers: [
                                Marker(
                                  point: posicion,
                                  width: 44,
                                  height: 44,
                                  child: _MarcadorRumbo(
                                    color: color,
                                    rumboGrados: _rumbo,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        );
                      },
                    ),
                    RichAttributionWidget(
                      attributions: const [
                        TextSourceAttribution('OpenStreetMap contributors'),
                        TextSourceAttribution('CARTO'),
                      ],
                    ),
                  ],
                ),
                Positioned(
                  top: 12,
                  left: 12,
                  right: 12,
                  child: _EstadoRegistro(
                    registrando: _registrando,
                    pausado: _pausado,
                    esperandoFix: _esperandoFix,
                    moviendose: _estaMoviendose,
                    pasos: _pasos,
                    telemetria: _telemetria,
                    remoto: _seguimientoRemoto.estado,
                  ),
                ),
                Positioned(
                  right: 12,
                  bottom: 28,
                  child: FloatingActionButton.small(
                    heroTag: 'centrar',
                    tooltip: _seguir ? 'Siguiendo' : 'Centrar y seguir',
                    onPressed: _centrar,
                    backgroundColor: _seguir ? color : tema.colorScheme.surface,
                    foregroundColor: _seguir ? Colors.white : color,
                    child: Icon(
                      _seguir
                          ? Icons.gps_fixed_rounded
                          : Icons.gps_not_fixed_rounded,
                    ),
                  ),
                ),
              ],
            ),
          ),
          _PanelInferior(
            registrando: _registrando,
            pausado: _pausado,
            cantidadPuntos: _cantidadPuntos,
            distanciaMetros: _distanciaMetros,
            intervaloMilisegundos: _intervaloMilisegundos,
            telemetria: _telemetria,
            deviceId: _deviceId,
            mensaje: _mensaje,
            onPressed: _alternarRegistro,
            onPause: _alternarPausa,
          ),
        ],
      ),
    );
  }

  void _mostrarHistorial(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => SizedBox(
        height: 360,
        child: _historial.isEmpty
            ? const Center(child: Text('Todavía no hay recorridos guardados.'))
            : ListView.builder(
                itemCount: _historial.length,
                itemBuilder: (context, index) {
                  final registro = _historial[index];
                  return ListTile(
                    leading: const Icon(Icons.route_rounded),
                    title: Text('Recorrido ${_historial.length - index}'),
                    subtitle: Text(
                      '${_formatearFecha(registro.fechaInicio)} · ${registro.tipoMovimiento}\n'
                      '${_formatearDistancia(registro.distanciaMetros)} · ${_formatearDuracion(registro.duracion)} · '
                      '${registro.velocidadPromedioKmh.toStringAsFixed(1)} km/h · batería ${registro.bateriaFin}%',
                    ),
                    trailing: IconButton(
                      tooltip: 'Compartir recorrido',
                      icon: const Icon(Icons.share_rounded),
                      onPressed: () => _compartirRegistro(registro),
                    ),
                  );
                },
              ),
      ),
    );
  }

  Future<void> _mostrarConfiguracionIntervalo() async {
    var intervalo = _intervaloMilisegundos;
    final seleccionado = await showDialog<int>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Intervalo de registro'),
        content: StatefulBuilder(
          builder: (context, actualizar) => Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              DropdownButtonFormField<int>(
                initialValue: intervalo,
                decoration: const InputDecoration(
                  labelText: 'Milisegundos entre muestras',
                ),
                items: _intervalosDisponibles
                    .map(
                      (valor) => DropdownMenuItem(
                        value: valor,
                        child: Text('$valor ms'),
                      ),
                    )
                    .toList(),
                onChanged: (valor) =>
                    actualizar(() => intervalo = valor ?? intervalo),
              ),
              const SizedBox(height: 12),
              const Text(
                'La mayoría de los GPS de celular entregan 1 lectura por segundo; '
                'con 250-500 ms se recibe cada lectura apenas está disponible.',
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, intervalo),
            child: const Text('Guardar'),
          ),
        ],
      ),
    );
    if (seleccionado == null || !mounted) return;
    final preferencias = await SharedPreferences.getInstance();
    await preferencias.setInt('intervalo_gps', seleccionado);
    setState(() => _intervaloMilisegundos = seleccionado);
    // Se aplica sin cortar el recorrido: solo se re-suscribe al GPS.
    if (_registrando && !_pausado) _suscribirSensores();
  }

  String _formatearFecha(DateTime fecha) =>
      '${fecha.day.toString().padLeft(2, '0')}/'
      '${fecha.month.toString().padLeft(2, '0')}/${fecha.year}';

  String _formatearDistancia(double metros) => metros < 1000
      ? '${metros.toStringAsFixed(0)} m'
      : '${(metros / 1000).toStringAsFixed(2)} km';

  String _formatearDuracion(Duration duracion) =>
      '${duracion.inMinutes} min ${duracion.inSeconds % 60} s';

  Future<void> _compartirRegistro(RegistroMovimiento registro) async {
    final inicio = registro.puntos.isEmpty ? null : registro.puntos.first;
    final fin = registro.puntos.isEmpty ? null : registro.puntos.last;
    final coordenadas = inicio == null || fin == null
        ? 'Coordenadas: no disponibles'
        : 'Inicio: ${inicio.latitude.toStringAsFixed(6)}, ${inicio.longitude.toStringAsFixed(6)}\n'
              'Fin: ${fin.latitude.toStringAsFixed(6)}, ${fin.longitude.toStringAsFixed(6)}';
    final contenido =
        '''Rastro - registro de movimiento

  Fecha: ${_formatearFecha(registro.fechaInicio)}
  Tipo de movimiento: ${registro.tipoMovimiento}
  Duración: ${_formatearDuracion(registro.duracion)}
  Distancia: ${_formatearDistancia(registro.distanciaMetros)}
  Velocidad promedio: ${registro.velocidadPromedioKmh.toStringAsFixed(1)} km/h
  Velocidad máxima: ${registro.velocidadMaximaKmh.toStringAsFixed(1)} km/h
  Aceleración promedio: ${registro.aceleracionPromedio.toStringAsFixed(2)} m/s2
  Batería: ${registro.bateriaInicio}% al iniciar, ${registro.bateriaFin}% al finalizar
  Puntos GPS registrados: ${registro.puntos.length}
  $coordenadas''';
    await Share.share(contenido, subject: 'Datos de movimiento - Rastro');
  }
}

class _MarcadorRumbo extends StatelessWidget {
  const _MarcadorRumbo({required this.color, required this.rumboGrados});

  final Color color;
  final double rumboGrados;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 4),
        boxShadow: const [BoxShadow(blurRadius: 4, color: Colors.black26)],
      ),
      child: Transform.rotate(
        angle: rumboGrados * math.pi / 180,
        child: const Icon(
          Icons.navigation_rounded,
          color: Colors.white,
          size: 21,
        ),
      ),
    );
  }
}

class _EstadoRegistro extends StatelessWidget {
  const _EstadoRegistro({
    required this.registrando,
    required this.pausado,
    required this.esperandoFix,
    required this.moviendose,
    required this.pasos,
    required this.telemetria,
    required this.remoto,
  });

  final bool registrando;
  final bool pausado;
  final bool esperandoFix;
  final bool moviendose;
  final ValueListenable<int> pasos;
  final ValueListenable<Telemetria> telemetria;
  final ValueListenable<EstadoRemoto> remoto;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final String titulo;
    if (!registrando) {
      titulo = 'Listo para registrar';
    } else if (pausado) {
      titulo = 'Recorrido en pausa';
    } else if (esperandoFix) {
      titulo = 'Buscando señal GPS...';
    } else {
      titulo = moviendose
          ? 'Movimiento detectado'
          : 'En reposo · posición fija';
    }
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Icon(
                  registrando && !pausado
                      ? Icons.circle
                      : Icons.pause_circle_outline,
                  size: 18,
                  color: registrando && !pausado
                      ? Colors.redAccent
                      : tema.colorScheme.outline,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    titulo,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                ValueListenableBuilder<int>(
                  valueListenable: pasos,
                  builder: (context, valor, _) => Text(
                    '$valor pasos',
                    style: tema.textTheme.labelMedium,
                  ),
                ),
              ],
            ),
            if (registrando) ...[
              const SizedBox(height: 6),
              ValueListenableBuilder<EstadoRemoto>(
                valueListenable: remoto,
                builder: (context, estado, _) {
                  final (texto, color) = switch (estado.enlace) {
                    EstadoEnlace.conectado => ('Servidor en línea', Colors.green),
                    EstadoEnlace.conectando => ('Conectando...', Colors.orange),
                    EstadoEnlace.desconectado => ('Sin conexión', Colors.red),
                  };
                  return Row(
                    children: [
                      Icon(Icons.cloud_rounded, size: 16, color: color),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          [
                            texto,
                            if (estado.rttMs != null) 'RTT ${estado.rttMs} ms',
                            if (estado.latenciaAckMs != null)
                              'guardado en BD ${estado.latenciaAckMs} ms',
                            if (estado.pendientes > 0)
                              '${estado.pendientes} en cola',
                          ].join(' · '),
                          style: tema.textTheme.labelSmall,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  );
                },
              ),
              ValueListenableBuilder<Telemetria>(
                valueListenable: telemetria,
                builder: (context, t, _) => t.senalDebil
                    ? Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Row(
                          children: [
                            const Icon(
                              Icons.signal_cellular_connected_no_internet_0_bar_rounded,
                              size: 16,
                              color: Colors.orange,
                            ),
                            const SizedBox(width: 6),
                            Text(
                              'Señal GPS débil: lecturas imprecisas descartadas',
                              style: tema.textTheme.labelSmall,
                            ),
                          ],
                        ),
                      )
                    : const SizedBox.shrink(),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _PanelInferior extends StatelessWidget {
  const _PanelInferior({
    required this.registrando,
    required this.pausado,
    required this.cantidadPuntos,
    required this.distanciaMetros,
    required this.intervaloMilisegundos,
    required this.telemetria,
    required this.deviceId,
    required this.mensaje,
    required this.onPressed,
    required this.onPause,
  });

  final bool registrando;
  final bool pausado;
  final int cantidadPuntos;
  final double distanciaMetros;
  final int intervaloMilisegundos;
  final ValueListenable<Telemetria> telemetria;
  final String deviceId;
  final String? mensaje;
  final VoidCallback onPressed;
  final VoidCallback onPause;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Material(
      color: tema.scaffoldBackgroundColor,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ValueListenableBuilder<Telemetria>(
                valueListenable: telemetria,
                builder: (context, t, _) => Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _DatoResumen(
                      titulo: 'km/h',
                      valor: registrando
                          ? t.velocidadKmh.toStringAsFixed(1)
                          : '--',
                    ),
                    _DatoResumen(
                      titulo: 'Distancia',
                      valor: distanciaMetros < 1000
                          ? '${distanciaMetros.toStringAsFixed(0)} m'
                          : '${(distanciaMetros / 1000).toStringAsFixed(2)} km',
                    ),
                    _DatoResumen(
                      titulo: 'Precisión',
                      valor: t.precision == null
                          ? '--'
                          : '±${t.precision!.toStringAsFixed(0)} m',
                    ),
                    _DatoResumen(
                      titulo: 'GPS',
                      valor: t.frecuenciaHz == null
                          ? '${intervaloMilisegundos}ms'
                          : '${t.frecuenciaHz!.toStringAsFixed(1)} Hz',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '$cantidadPuntos puntos'
                '${deviceId.isEmpty ? '' : ' · $deviceId'}',
                textAlign: TextAlign.center,
                style: tema.textTheme.labelSmall,
                overflow: TextOverflow.ellipsis,
              ),
              if (mensaje != null) ...[
                const SizedBox(height: 8),
                Text(
                  mensaje!,
                  textAlign: TextAlign.center,
                  style: TextStyle(color: tema.colorScheme.error),
                ),
              ],
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: onPressed,
                      icon: Icon(
                        registrando
                            ? Icons.stop_rounded
                            : Icons.play_arrow_rounded,
                      ),
                      label: Text(
                        registrando ? 'Detener y guardar' : 'Iniciar recorrido',
                      ),
                    ),
                  ),
                  if (registrando) ...[
                    const SizedBox(width: 8),
                    IconButton.filledTonal(
                      tooltip: pausado ? 'Reanudar' : 'Pausar',
                      onPressed: onPause,
                      icon: Icon(pausado ? Icons.play_arrow : Icons.pause),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DatoResumen extends StatelessWidget {
  const _DatoResumen({required this.titulo, required this.valor});

  final String titulo;
  final String valor;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          valor,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.bold,
            fontFeatures: const [FontFeature.tabularFigures()],
          ),
        ),
        Text(titulo, style: Theme.of(context).textTheme.labelSmall),
      ],
    );
  }
}
