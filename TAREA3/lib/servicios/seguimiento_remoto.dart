import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:battery_plus/battery_plus.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

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

  bool get estaAutorizado => _token != null;

  Future<void> cargarSesion() async {
    final preferencias = await SharedPreferences.getInstance();
    _token = preferencias.getString('seguimiento_token');
    _deviceId = preferencias.getString('seguimiento_device_id');
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

  Future<void> registrarDispositivo({required String nombre, required String version}) async {
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
    if (respuesta.statusCode >= 400) throw Exception('No se pudo registrar el dispositivo');
  }

  Future<void> enviarUbicacion({
    required double latitude,
    required double longitude,
    required double accuracy,
    required double speed,
    required double heading,
    required int battery,
    required DateTime timestamp,
  }) async {
    final deviceId = _deviceId;
    if (deviceId == null) return;
    final datos = {
      'latitude': latitude,
      'longitude': longitude,
      'accuracy': accuracy,
      'speed': speed,
      'heading': heading,
      'battery': battery,
      'timestamp': timestamp.toUtc().toIso8601String(),
    };
    try {
      final respuesta = await http.post(
        Uri.parse('$baseUrl/devices/$deviceId/locations'),
        headers: _headers(),
        body: jsonEncode(datos),
      );
      if (respuesta.statusCode >= 400) throw Exception('HTTP ${respuesta.statusCode}');
      await _enviarPendientes(deviceId);
    } catch (_) {
      final preferencias = await SharedPreferences.getInstance();
      final pendientes = preferencias.getStringList('ubicaciones_pendientes') ?? [];
      pendientes.add(jsonEncode(datos));
      await preferencias.setStringList('ubicaciones_pendientes', pendientes.take(500).toList());
    }
  }

  Future<void> _enviarPendientes(String deviceId) async {
    final preferencias = await SharedPreferences.getInstance();
    final pendientes = preferencias.getStringList('ubicaciones_pendientes') ?? [];
    if (pendientes.isEmpty) return;
    final restantes = <String>[];
    for (final pendiente in pendientes) {
      final respuesta = await http.post(
        Uri.parse('$baseUrl/devices/$deviceId/locations'),
        headers: _headers(),
        body: pendiente,
      );
      if (respuesta.statusCode >= 400) restantes.add(pendiente);
    }
    await preferencias.setStringList('ubicaciones_pendientes', restantes);
  }

  Map<String, String> _headers() => {
        'Content-Type': 'application/json',
      };

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
    final partes = List.generate(4, (_) => aleatorio.nextInt(1 << 32).toRadixString(16).padLeft(8, '0'));
    return '${DateTime.now().microsecondsSinceEpoch}-${partes.join('-')}';
  }
}
