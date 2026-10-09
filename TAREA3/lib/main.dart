import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:battery_plus/battery_plus.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:sensors_plus/sensors_plus.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'modelos/ubicacion_local.dart';
import 'servicios/base_datos_local.dart';
import 'servicios/seguimiento_remoto.dart';

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

class PantallaMovimiento extends StatefulWidget {
  const PantallaMovimiento({super.key});

  @override
  State<PantallaMovimiento> createState() => _PantallaMovimientoState();
}

class _PantallaMovimientoState extends State<PantallaMovimiento> {
  static const _ubicacionInicial = LatLng(-13.53195, -71.96746);
  static const _cartoApiKey = String.fromEnvironment('CARTO_API_KEY');
  final _mapController = MapController();
  final _bateria = Battery();
  final _baseDatos = BaseDatosLocal.instancia;
  final _seguimientoRemoto = SeguimientoRemoto();
  final _puntos = <LatLng>[];
  final _historial = <RegistroMovimiento>[];
  StreamSubscription<Position>? _ubicacionSuscripcion;
  StreamSubscription<UserAccelerometerEvent>? _sensorSuscripcion;
  LatLng _centro = _ubicacionInicial;
  double _aceleracion = 0;
  double _distanciaMetros = 0;
  double _velocidadMaximaKmh = 0;
  double _velocidadTotalKmh = 0;
  double _aceleracionTotal = 0;
  int _muestrasAceleracion = 0;
  int _muestrasVelocidad = 0;
  int _bateriaInicio = 0;
  DateTime? _inicioRegistro;
  Position? _ultimaPosicion;
  bool _registrando = false;
  bool _estaMoviendose = false;
  bool _cargando = true;
  bool _pausado = false;
  String _deviceId = '';
  int _intervaloMilisegundos = 500;
  String? _mensaje;

  String get _mapTileUrl => _cartoApiKey.isEmpty
      ? 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
      : 'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=$_cartoApiKey';

  @override
  void initState() {
    super.initState();
    _cargarHistorial();
    _cargarConfiguracion();
    _seguimientoRemoto.cargarSesion();
  }

  Future<void> _cargarConfiguracion() async {
    final preferencias = await SharedPreferences.getInstance();
    var deviceId = preferencias.getString('device_id');
    if (deviceId == null || deviceId.isEmpty) {
      deviceId =
          'android-${DateTime.now().microsecondsSinceEpoch}-${math.Random.secure().nextInt(1 << 32).toRadixString(16)}';
      await preferencias.setString('device_id', deviceId);
    }
    if (!mounted) return;
    setState(() {
      _deviceId = deviceId!;
      _intervaloMilisegundos = preferencias.getInt('intervalo_gps') ?? 500;
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

  Future<void> _alternarRegistro() async {
    if (_registrando) {
      await _detenerRegistro();
    } else {
      await _iniciarRegistro();
    }
  }

  Future<void> _iniciarRegistro() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      if (mounted) {
        setState(
          () => _mensaje =
              'La ubicación está desactivada. Actívala para comenzar.',
        );
        await _mostrarConfiguracionUbicacion();
      }
      return;
    }
    var permiso = await Geolocator.checkPermission();
    if (permiso == LocationPermission.denied) {
      permiso = await Geolocator.requestPermission();
    }
    if (permiso == LocationPermission.deniedForever) {
      if (mounted) {
        setState(
          () => _mensaje =
              'El permiso está bloqueado. Actívalo en Ajustes > Aplicaciones > app > Permisos.',
        );
        await Geolocator.openAppSettings();
      }
      return;
    }
    if (permiso == LocationPermission.denied) {
      setState(
        () => _mensaje =
            'Debes permitir el acceso a la ubicación para registrar el recorrido.',
      );
      return;
    }
    if (permiso == LocationPermission.whileInUse) {
      permiso = await Geolocator.requestPermission();
    }
    if (permiso != LocationPermission.always &&
        permiso != LocationPermission.whileInUse) {
      setState(
        () => _mensaje = 'Se necesita permiso de ubicación para continuar.',
      );
      return;
    }
    if (await Permission.notification.isDenied) {
      await Permission.notification.request();
    }

    try {
      final posicion = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 20),
        ),
      );
      final puntoInicial = LatLng(posicion.latitude, posicion.longitude);
      await _registrarDispositivoLocal();
      await _seguimientoRemoto.iniciarTiempoReal();
      _bateriaInicio = await _bateria.batteryLevel;
      setState(() {
        _puntos
          ..clear()
          ..add(puntoInicial);
        _centro = puntoInicial;
        _registrando = true;
        _pausado = false;
        _mensaje = null;
        _inicioRegistro = DateTime.now();
        _ultimaPosicion = posicion;
        _distanciaMetros = 0;
        _velocidadMaximaKmh = 0;
        _velocidadTotalKmh = 0;
        _aceleracionTotal = 0;
        _muestrasAceleracion = 0;
        _muestrasVelocidad = 0;
      });
      _mapController.move(puntoInicial, 17);
      _ubicacionSuscripcion = Geolocator.getPositionStream(
        locationSettings: AndroidSettings(
          accuracy: LocationAccuracy.high,
          distanceFilter: 5,
          intervalDuration: Duration(milliseconds: _intervaloMilisegundos),
          foregroundNotificationConfig: const ForegroundNotificationConfig(
            notificationTitle: 'Rastro está registrando tu recorrido',
            notificationText: 'La ubicación continúa activa en segundo plano',
            notificationChannelName: 'Seguimiento de movimiento',
            setOngoing: true,
            enableWakeLock: true,
          ),
        ),
      ).listen(_agregarUbicacion);
      _sensorSuscripcion = userAccelerometerEventStream().listen(
        _leerAcelerometro,
      );
      await _guardarUbicacion(posicion);
    } on TimeoutException {
      if (mounted) {
        setState(
          () => _mensaje =
              'El GPS tardó demasiado. Sal a un lugar abierto y vuelve a intentarlo.',
        );
      }

    } on LocationServiceDisabledException {
      if (mounted) {
        setState(
          () => _mensaje = 'La ubicación está desactivada en el teléfono.',
        );
        await _mostrarConfiguracionUbicacion();
      }
    } on PermissionDeniedException {
      if (mounted) {
        setState(
          () =>
              _mensaje = 'Android no concedió permiso para leer la ubicación.',
        );
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _mensaje =
              'No se pudo obtener la ubicación. Revisa GPS y permisos del teléfono.',
        );
      }
    }
  }

  Future<void> _registrarDispositivoLocal() async {
    try {
      await _seguimientoRemoto.registrarDispositivo(
        nombre: 'Mi celular',
        version: '1.0.0',
      );
    } catch (_) {
      if (mounted) {
        setState(
          () => _mensaje =
              'No se pudo conectar al monitoreo web. El GPS local seguirá funcionando.',
        );
      }
    }
  }

  // ignore: unused_element
  Future<bool> _asegurarAutorizacionRemota() async {
    if (_seguimientoRemoto.estaAutorizado) return true;
    if (!mounted) return false;
    final correo = TextEditingController();
    final contrasena = TextEditingController();
    var consentimiento = false;
    final autorizado = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, actualizar) => AlertDialog(
          title: const Text('Autorizar seguimiento'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Se enviarán ubicación, batería y datos del dispositivo al panel autorizado mientras el registro esté activo.',
                ),
                TextField(
                  controller: correo,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(labelText: 'Correo'),
                ),
                TextField(
                  controller: contrasena,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: 'Contraseña'),
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: consentimiento,
                  onChanged: (valor) =>
                      actualizar(() => consentimiento = valor ?? false),
                  title: const Text('Acepto enviar estos datos.'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: consentimiento
                  ? () async {
                      final ingreso = await _seguimientoRemoto.iniciarSesion(
                        correo.text.trim(),
                        contrasena.text,
                      );
                      if (!context.mounted) return;
                      if (ingreso) {
                        Navigator.pop(context, true);
                      } else {
                        setState(
                          () => _mensaje =
                              'No se pudo iniciar sesión en el servidor.',
                        );
                      }
                    }
                  : null,
              child: const Text('Autorizar'),
            ),
          ],
        ),
      ),
    );
    correo.dispose();
    contrasena.dispose();
    if (autorizado != true) return false;
    try {
      await _seguimientoRemoto.registrarDispositivo(
        nombre: 'Mi celular',
        version: '1.0.0',
      );
      return true;
    } catch (_) {
      if (mounted) {
        setState(
          () =>
              _mensaje = 'No se pudo registrar el dispositivo en el servidor.',
        );
      }
      return false;
    }
  }

  Future<void> _mostrarConfiguracionUbicacion() async {
    await Geolocator.openLocationSettings();
  }

  void _agregarUbicacion(Position posicion) {
    if (!mounted) return;
    if (!posicion.latitude.isFinite ||
        !posicion.longitude.isFinite ||
        posicion.latitude < -90 ||
        posicion.latitude > 90 ||
        posicion.longitude < -180 ||
        posicion.longitude > 180) {
      return;
    }
    final anterior = _ultimaPosicion;
    if (anterior != null &&
        anterior.latitude == posicion.latitude &&
        anterior.longitude == posicion.longitude &&
        anterior.timestamp == posicion.timestamp) {
      return;
    }
    final punto = LatLng(posicion.latitude, posicion.longitude);
    if (anterior != null) {
      _distanciaMetros += Geolocator.distanceBetween(
        anterior.latitude,
        anterior.longitude,
        posicion.latitude,
        posicion.longitude,
      );
    }
    _ultimaPosicion = posicion;
    final velocidadKmh = posicion.speed >= 0 ? posicion.speed * 3.6 : 0.0;
    _velocidadMaximaKmh = math
        .max(_velocidadMaximaKmh, velocidadKmh)
        .toDouble();
    _velocidadTotalKmh += velocidadKmh;
    _muestrasVelocidad++;
    setState(() {
      _puntos.add(punto);
      _centro = punto;
    });
    unawaited(_guardarUbicacion(posicion));
    _mapController.move(punto, _mapController.camera.zoom);
  }

  Future<void> _guardarUbicacion(Position posicion) async {
    if (_deviceId.isEmpty) return;
    final localId = await _baseDatos.insertarUbicacion(
      UbicacionLocal(
        deviceId: _deviceId,
        latitude: posicion.latitude,
        longitude: posicion.longitude,
        timestamp: posicion.timestamp,
        accuracy: posicion.accuracy,
        speed: posicion.speed,
        heading: posicion.heading,
        battery: await _bateria.batteryLevel,
      ),
    );
    unawaited(
      _seguimientoRemoto.enviarUbicacion(
        latitude: posicion.latitude,
        longitude: posicion.longitude,
        accuracy: posicion.accuracy,
        speed: posicion.speed,
        heading: posicion.heading,
        battery: await _bateria.batteryLevel,
        timestamp: posicion.timestamp,
        localId: localId,
      ),
    );
  }

  void _leerAcelerometro(UserAccelerometerEvent evento) {
    final intensidad = math.sqrt(
      evento.x * evento.x + evento.y * evento.y + evento.z * evento.z,
    );
    if (!mounted) return;
    setState(() {
      _aceleracion = intensidad;
      _estaMoviendose = intensidad > 1.2;
      _aceleracionTotal += intensidad;
      _muestrasAceleracion++;
    });
  }

  Future<void> _detenerRegistro() async {
    await _ubicacionSuscripcion?.cancel();
    await _sensorSuscripcion?.cancel();
    _ubicacionSuscripcion = null;
    _sensorSuscripcion = null;
    if (_puntos.isNotEmpty) {
      final fechaFin = DateTime.now();
      final fechaInicio = _inicioRegistro ?? fechaFin;
      final velocidadPromedio = _muestrasVelocidad == 0
          ? 0.0
          : _velocidadTotalKmh / _muestrasVelocidad;
      final aceleracionPromedio = _muestrasAceleracion == 0
          ? 0.0
          : _aceleracionTotal / _muestrasAceleracion;
      final registro = RegistroMovimiento(
        puntos: List.of(_puntos),
        fechaInicio: fechaInicio,
        fechaFin: fechaFin,
        distanciaMetros: _distanciaMetros,
        velocidadMaximaKmh: _velocidadMaximaKmh,
        velocidadPromedioKmh: velocidadPromedio,
        aceleracionPromedio: aceleracionPromedio,
        tipoMovimiento: _tipoMovimiento(velocidadPromedio, aceleracionPromedio),
        bateriaInicio: _bateriaInicio,
        bateriaFin: await _bateria.batteryLevel,
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
        _inicioRegistro = null;
        _ultimaPosicion = null;
      });
    }
  }

  String _tipoMovimiento(double velocidadKmh, double aceleracionPromedio) {
    if (velocidadKmh >= 18) return 'Vehículo';
    if (velocidadKmh >= 7) return 'Corriendo';
    if (velocidadKmh >= 1.5) return 'Caminando';
    if (aceleracionPromedio > 1.2) return 'Teléfono en movimiento';
    return 'En reposo';
  }

  @override
  void dispose() {
    _ubicacionSuscripcion?.cancel();
    _sensorSuscripcion?.cancel();
    _seguimientoRemoto.cerrar();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
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
                  options: MapOptions(initialCenter: _centro, initialZoom: 15),
                  children: [
                    TileLayer(
                      urlTemplate: _mapTileUrl,
                      subdomains: const ['a', 'b', 'c', 'd'],
                      userAgentPackageName: 'com.example.movimiento',
                    ),
                    RichAttributionWidget(
                      attributions: [
                        const TextSourceAttribution(
                          'OpenStreetMap contributors',
                        ),
                        if (_cartoApiKey.isNotEmpty)
                          const TextSourceAttribution('CARTO'),
                      ],
                    ),
                    if (_puntos.length > 1)
                      PolylineLayer(
                        polylines: [
                          Polyline(
                            points: _puntos,
                            color: tema.colorScheme.primary,
                            strokeWidth: 5,
                          ),
                        ],
                      ),
                    MarkerLayer(
                      markers: [
                        Marker(
                          point: _centro,
                          width: 44,
                          height: 44,
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                              color: tema.colorScheme.primary,
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white, width: 4),
                            ),
                            child: const Icon(
                              Icons.navigation_rounded,
                              color: Colors.white,
                              size: 21,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                Positioned(
                  top: 16,
                  left: 16,
                  right: 16,
                  child: _EstadoRegistro(
                    registrando: _registrando,
                    moviendose: _estaMoviendose,
                    aceleracion: _aceleracion,
                  ),
                ),
              ],
            ),
          ),
          _PanelInferior(
            registrando: _registrando,
            pausado: _pausado,
            cantidadPuntos: _puntos.length,
            cantidadRecorridos: _historial.length,
            intervaloMilisegundos: _intervaloMilisegundos,
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

  Future<void> _iniciarSuscripciones() async {
    _ubicacionSuscripcion = Geolocator.getPositionStream(
      locationSettings: AndroidSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 5,
        intervalDuration: Duration(milliseconds: _intervaloMilisegundos),
        foregroundNotificationConfig: const ForegroundNotificationConfig(
          notificationTitle: 'Rastro está registrando tu recorrido',
          notificationText: 'La ubicación continúa activa en segundo plano',
          notificationChannelName: 'Seguimiento de movimiento',
          setOngoing: true,
          enableWakeLock: true,
        ),
      ),
    ).listen(_agregarUbicacion);
    _sensorSuscripcion = userAccelerometerEventStream().listen(
      _leerAcelerometro,
    );
    if (mounted) setState(() => _pausado = false);
  }

  Future<void> _mostrarConfiguracionIntervalo() async {
    var intervalo = _intervaloMilisegundos;
    final seleccionado = await showDialog<int>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Intervalo de registro'),
        content: StatefulBuilder(
          builder: (context, actualizar) => DropdownButtonFormField<int>(
            initialValue: intervalo,
            decoration: const InputDecoration(
              labelText: 'Milisegundos entre muestras',
            ),
            items: const [500, 1000, 2000, 5000, 10000]
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
    if (_registrando) {
      await _detenerRegistro();
      await _iniciarRegistro();
    }
  }

  Future<void> _alternarPausa() async {
    if (!_registrando) return;
    if (_pausado) {
      await _iniciarSuscripciones();
    } else {
      await _ubicacionSuscripcion?.cancel();
      await _sensorSuscripcion?.cancel();
      if (mounted) setState(() => _pausado = true);
    }
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

class _EstadoRegistro extends StatelessWidget {
  const _EstadoRegistro({
    required this.registrando,
    required this.moviendose,
    required this.aceleracion,
  });

  final bool registrando;
  final bool moviendose;
  final double aceleracion;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Icon(
              registrando ? Icons.circle : Icons.pause_circle_outline,
              color: registrando ? Colors.redAccent : tema.colorScheme.outline,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                registrando
                    ? (moviendose
                          ? 'Movimiento detectado'
                          : 'Registrando recorrido')
                    : 'Listo para registrar',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ),
            Text(
              '${aceleracion.toStringAsFixed(1)} m/s2',
              style: tema.textTheme.labelMedium,
            ),
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
    required this.cantidadRecorridos,
    required this.intervaloMilisegundos,
    required this.deviceId,
    required this.mensaje,
    required this.onPressed,
    required this.onPause,
  });

  final bool registrando;
  final bool pausado;
  final int cantidadPuntos;
  final int cantidadRecorridos;
  final int intervaloMilisegundos;
  final String deviceId;
  final String? mensaje;
  final VoidCallback onPressed;
  final VoidCallback onPause;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Material(
      color: Theme.of(context).scaffoldBackgroundColor,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _DatoResumen(titulo: 'Puntos', valor: '$cantidadPuntos'),
                  _DatoResumen(
                    titulo: 'Guardados',
                    valor: '$cantidadRecorridos',
                  ),
                  _DatoResumen(titulo: 'GPS', valor: '${intervaloMilisegundos}ms'),
                ],
              ),
              if (deviceId.isNotEmpty)
                Text(
                  'Dispositivo: $deviceId',
                  textAlign: TextAlign.center,
                  style: tema.textTheme.labelSmall,
                ),
              if (mensaje != null) ...[
                const SizedBox(height: 10),
                Text(
                  mensaje!,
                  textAlign: TextAlign.center,
                  style: TextStyle(color: tema.colorScheme.error),
                ),
              ],
              const SizedBox(height: 14),
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
          style: Theme.of(
            context,
          ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
        ),
        Text(titulo, style: Theme.of(context).textTheme.labelMedium),
      ],
    );
  }
}
