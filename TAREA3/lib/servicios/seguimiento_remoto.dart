import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:battery_plus/battery_plus.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../modelos/ubicacion_local.dart';
import 'base_datos_local.dart';

class SeguimientoRemoto {
  SeguimientoRemoto({
    this.baseUrl = const String.fromEnvironment(
      'API_URL',
      defaultValue: 'http://10.0.2.2:8080/api',
    ),
  });

  final String baseUrl;
  final _bateria = Battery();
  final _informacionDispositivo = DeviceInfoPlugin();
  String? _token;
  String? _deviceId;
  WebSocketChannel? _socket;
  StreamSubscription<dynamic>? _socketSubscription;
  Timer? _reconnectTimer;
  bool _socketReady = false;
  bool _closing = false;
  final _pendingAcks = <String, int>{};

  bool get estaAutorizado => _token != null;

  Future<void> cargarSesion() async {
    final preferencias = await SharedPreferences.getInstance();
    _token = preferencias.getString('seguimiento_token');
    _deviceId = preferencias.getString('seguimiento_device_id');
  }

  Future<void> iniciarTiempoReal() async {
    _closing = false;
    await _conectarSocket();
  }

  Future<void> _conectarSocket() async {
    if (_closing || _socketReady || _deviceId == null) return;
    final base = Uri.parse(baseUrl);
    final apiPrefix = base.path.endsWith('/api')
        ? base.path.substring(0, base.path.length - 4)
        : '';
    final uri = Uri(
      scheme: base.scheme == 'https' ? 'wss' : 'ws',
      host: base.host,
      port: base.hasPort ? base.port : null,
      path: '${apiPrefix.isEmpty ? '' : apiPrefix}/ws',
      queryParameters: _token == null ? null : {'token': _token!},
    );
    try {
      final socket = IOWebSocketChannel.connect(uri);
      await socket.ready;
      _socket = socket;
      _socketReady = true;
      _socketSubscription = socket.stream.listen(
        _recibirSocket,
        onDone: _socketCerrado,
        onError: (_) => _socketCerrado(),
        cancelOnError: true,
      );
    } catch (_) {
      _programarReconexion();
    }
  }

  void _recibirSocket(dynamic raw) {
    final mensaje = jsonDecode(raw as String) as Map<String, dynamic>;
    if (mensaje['type'] == 'location.accepted') {
      final sampleId = mensaje['data']['sampleId'] as String?;
      final localId = sampleId == null ? null : _pendingAcks.remove(sampleId);
      if (localId != null) {
        unawaited(BaseDatosLocal.instancia.marcarSincronizada(localId));
      }
    }
  }

  void _socketCerrado() {
    _socketReady = false;
    _socket = null;
    _socketSubscription = null;
    _programarReconexion();
  }

  void _programarReconexion() {
    if (_closing || _reconnectTimer?.isActive == true) return;
    _reconnectTimer = Timer(const Duration(seconds: 3), _conectarSocket);
  }

  Future<bool> iniciarSesion(String correo, String contrasena) async {
    final respuesta = await http.post(
      Uri.parse('$baseUrl/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': correo, 'password': contrasena}),
    );
    if (respuesta.statusCode != 200) return false;
    final datos = jsonDecode(respuesta.body) as Map<String, dynamic>;
    _token = datos['token'] as String;
    final preferencias = await SharedPreferences.getInstance();
    await preferencias.setString('seguimiento_token', _token!);
    return true;
  }

  Future<void> cerrarSesion() async {
    _token = null;
    final preferencias = await SharedPreferences.getInstance();
    await preferencias.remove('seguimiento_token');
  }

  Future<void> registrarDispositivo({
    required String nombre,
    required String version,
  }) async {
    final preferencias = await SharedPreferences.getInstance();
    _deviceId ??= preferencias.getString('device_id');
    _deviceId ??= preferencias.getString('seguimiento_device_id');
    _deviceId ??= _generarId();
    await preferencias.setString('seguimiento_device_id', _deviceId!);
    await preferencias.setString('device_id', _deviceId!);
    final datos = await _datosDispositivo();
    final respuesta = await http.post(
      Uri.parse('$baseUrl/devices'),
      headers: _headers(),
      body: jsonEncode({
        'deviceId': _deviceId,
        'name': nombre,
        'platform': datos.$1,
        'appVersion': version,
        'model': datos.$2,
        'battery': await _bateria.batteryLevel,
      }),
    );
    if (respuesta.statusCode >= 400) {
      throw Exception('No se pudo registrar el dispositivo');
    }
  }

  Future<void> enviarUbicacion({
    required double latitude,
    required double longitude,
    required double accuracy,
    required double speed,
    required double heading,
    required int battery,
    required DateTime timestamp,
    required int localId,
  }) async {
    final deviceId = _deviceId;
    if (deviceId == null) return;
    final datos = {
      'deviceId': deviceId,
      'sampleId': '$deviceId-$localId-${timestamp.microsecondsSinceEpoch}',
      'latitude': latitude,
      'longitude': longitude,
      'accuracy': accuracy,
      'speed': speed,
      'heading': heading,
      'battery': battery,
      'timestamp': timestamp.toUtc().toIso8601String(),
    };
    if (_socketReady) {
      try {
        _pendingAcks[datos['sampleId'] as String] = localId;
        _socket!.sink.add(jsonEncode({'type': 'location', 'data': datos}));
        return;
      } catch (_) {
        _socketCerrado();
      }
    }
    try {
      final respuesta = await http.post(
        Uri.parse('$baseUrl/devices/$deviceId/locations'),
        headers: _headers(),
        body: jsonEncode(datos),
      );
      if (respuesta.statusCode >= 400) {
        throw Exception('HTTP ${respuesta.statusCode}');
      }
      await _enviarPendientes(deviceId);
      await BaseDatosLocal.instancia.marcarSincronizada(localId);
    } catch (_) {
      _programarReconexion();
    }
  }

  Future<void> _enviarPendientes(String deviceId) async {
    final pendientes = await BaseDatosLocal.instancia.pendientes(limite: 50);
    for (final pendiente in pendientes) {
      final respuesta = await http.post(
        Uri.parse('$baseUrl/devices/$deviceId/locations'),
        headers: _headers(),
        body: jsonEncode(_datosPendiente(pendiente)),
      );
      if (respuesta.statusCode < 400 && pendiente.id != null) {
        await BaseDatosLocal.instancia.marcarSincronizada(pendiente.id!);
      }
    }
  }

  Map<String, dynamic> _datosPendiente(UbicacionLocal ubicacion) => {
    'sampleId':
        '${ubicacion.deviceId}-${ubicacion.id}-${ubicacion.timestamp.microsecondsSinceEpoch}',
    'latitude': ubicacion.latitude,
    'longitude': ubicacion.longitude,
    'accuracy': ubicacion.accuracy,
    'speed': ubicacion.speed,
    'heading': ubicacion.heading,
    'battery': ubicacion.battery,
    'timestamp': ubicacion.timestamp.toUtc().toIso8601String(),
  };

  Future<void> cerrar() async {
    _closing = true;
    _reconnectTimer?.cancel();
    await _socketSubscription?.cancel();
    await _socket?.sink.close();
    _socket = null;
    _socketReady = false;
  }

  Map<String, String> _headers() => {'Content-Type': 'application/json'};

  Future<(String, String)> _datosDispositivo() async {
    if (Platform.isAndroid) {
      final info = await _informacionDispositivo.androidInfo;
      return ('android', '${info.manufacturer} ${info.model}');
    }
    if (Platform.isIOS) {
      final info = await _informacionDispositivo.iosInfo;
      return ('ios', info.utsname.machine);
    }
    return (Platform.operatingSystem, 'dispositivo');
  }

  String _generarId() {
    final aleatorio = Random.secure();
    final partes = List.generate(
      4,
      (_) => aleatorio.nextInt(1 << 32).toRadixString(16).padLeft(8, '0'),
    );
    return '${DateTime.now().microsecondsSinceEpoch}-${partes.join('-')}';
  }
}
