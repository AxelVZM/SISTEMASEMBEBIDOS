import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';

import '../modelos/ubicacion_local.dart';
import 'base_datos_local.dart';

enum EstadoEnlace { desconectado, conectando, conectado }

/// Estado del enlace con el servidor, para mostrarlo en pantalla.
@immutable
class EstadoRemoto {
  const EstadoRemoto({
    this.enlace = EstadoEnlace.desconectado,
    this.rttMs,
    this.latenciaAckMs,
    this.pendientes = 0,
  });

  final EstadoEnlace enlace;

  /// Tiempo de ida y vuelta de GET /api/time.
  final int? rttMs;

  /// Tiempo desde que se envió (POST) la última muestra hasta que el
  /// servidor confirmó que quedó guardada en PostgreSQL.
  final int? latenciaAckMs;

  /// Muestras guardadas localmente que aún no llegaron al servidor.
  final int pendientes;

  EstadoRemoto copyWith({
    EstadoEnlace? enlace,
    int? rttMs,
    int? latenciaAckMs,
    int? pendientes,
  }) => EstadoRemoto(
    enlace: enlace ?? this.enlace,
    rttMs: rttMs ?? this.rttMs,
    latenciaAckMs: latenciaAckMs ?? this.latenciaAckMs,
    pendientes: pendientes ?? this.pendientes,
  );
}

/// Comunicación con la API REST del servidor (que guarda en PostgreSQL).
///
/// - POST /devices: registro del celular.
/// - POST /devices/:id/locations: cada punto GPS, en cuanto se obtiene.
/// - POST /devices/:id/locations/batch: puntos pendientes (sin red).
/// - POST /devices/:id/heartbeat: "sigo activo" (aunque esté quieto).
/// - GET /time: RTT y desfase de reloj (estilo NTP).
///
/// Se usa una única conexión HTTP persistente (keep-alive): cada POST viaja
/// por el mismo socket TCP ya abierto, sin repetir el saludo de conexión.
/// Cada punto se guarda primero en SQLite y se marca como sincronizado solo
/// cuando el servidor confirma que lo guardó.
class SeguimientoRemoto {
  SeguimientoRemoto({
    this.baseUrl = const String.fromEnvironment(
      'API_URL',
      defaultValue: 'http://18.191.113.248/movimiento/api',
    ),
  });

  static const _maxEnVuelo = 4;
  static const _timeout = Duration(seconds: 5);
  static const _headers = {'Content-Type': 'application/json'};

  final String baseUrl;
  final estado = ValueNotifier(const EstadoRemoto());
  final _informacionDispositivo = DeviceInfoPlugin();
  final _enVuelo = <String>{};
  final _muestrasReloj = <(int rtt, int offset)>[];

  http.Client? _cliente;
  Timer? _temporizadorReloj;
  Timer? _temporizadorLatido;
  Timer? _temporizadorCola;
  bool _activo = false;
  bool _registrado = false;
  bool _vaciandoCola = false;
  bool _desechado = false;
  int _fallosSeguidos = 0;
  int _offsetRelojMs = 0;

  String? _deviceId;
  String _nombre = 'Mi celular';
  String _version = '1.0.0';
  int? _bateria;

  /// Diferencia (servidor - teléfono) en milisegundos.
  int get offsetRelojMs => _offsetRelojMs;

  bool get conectado => estado.value.enlace == EstadoEnlace.conectado;

  set bateria(int? valor) => _bateria = valor;

  http.Client _crearCliente() {
    final cliente = HttpClient()
      ..idleTimeout = const Duration(seconds: 60)
      ..connectionTimeout = _timeout
      ..maxConnectionsPerHost = _maxEnVuelo;
    return IOClient(cliente);
  }

  Future<void> iniciar({
    required String deviceId,
    required String nombre,
    required String version,
  }) async {
    _deviceId = deviceId;
    _nombre = nombre;
    _version = version;
    _activo = true;
    _registrado = false;
    _fallosSeguidos = 0;
    _cliente ??= _crearCliente();
    _actualizar(enlace: EstadoEnlace.conectando);

    _temporizadorReloj?.cancel();
    _temporizadorReloj = Timer.periodic(
      const Duration(seconds: 10),
      (_) => unawaited(_sincronizarReloj()),
    );
    _temporizadorLatido?.cancel();
    _temporizadorLatido = Timer.periodic(
      const Duration(seconds: 5),
      (_) => unawaited(_latido()),
    );
    _temporizadorCola?.cancel();
    _temporizadorCola = Timer.periodic(
      const Duration(seconds: 10),
      (_) => unawaited(_vaciarCola()),
    );

    await _registrar();
    // Varias mediciones al inicio para estimar bien el desfase de reloj.
    for (var i = 0; i < 3; i++) {
      await _sincronizarReloj();
    }
    unawaited(_vaciarCola());
  }

  Uri _uri(String ruta) => Uri.parse('$baseUrl$ruta');

  void _exito() {
    _fallosSeguidos = 0;
    if (!conectado) _actualizar(enlace: EstadoEnlace.conectado);
  }

  void _fallo() {
    _fallosSeguidos++;
    if (_fallosSeguidos >= 2) _actualizar(enlace: EstadoEnlace.desconectado);
  }

  Future<void> _registrar() async {
    final cliente = _cliente;
    final deviceId = _deviceId;
    if (cliente == null || deviceId == null || !_activo) return;
    try {
      final (plataforma, modelo) = await _datosDispositivo();
      final respuesta = await cliente
          .post(
            _uri('/devices'),
            headers: _headers,
            body: jsonEncode({
              'deviceId': deviceId,
              'name': _nombre,
              'platform': plataforma,
              'model': modelo,
              'appVersion': _version,
              'battery': _bateria,
            }),
          )
          .timeout(_timeout);
      if (respuesta.statusCode < 400) {
        _registrado = true;
        _exito();
      } else {
        _fallo();
      }
    } catch (_) {
      _fallo();
    }
  }

  /// GET /time: mide el RTT y estima el desfase de reloj con el servidor.
  Future<void> _sincronizarReloj() async {
    final cliente = _cliente;
    if (cliente == null || !_activo) return;
    final t0 = DateTime.now().millisecondsSinceEpoch;
    try {
      final respuesta = await cliente.get(_uri('/time')).timeout(_timeout);
      final t1 = DateTime.now().millisecondsSinceEpoch;
      if (respuesta.statusCode >= 400) return _fallo();
      final servidor =
          ((jsonDecode(respuesta.body) as Map)['serverTime'] as num).toInt();
      final rtt = t1 - t0;
      _muestrasReloj.add((rtt, servidor - (t0 + rtt ~/ 2)));
      if (_muestrasReloj.length > 8) _muestrasReloj.removeAt(0);
      // La medición con menor RTT es la que mejor estima el desfase.
      _offsetRelojMs = _muestrasReloj.reduce((a, b) => a.$1 <= b.$1 ? a : b).$2;
      _exito();
      _actualizar(rttMs: rtt);
    } catch (_) {
      _fallo();
    }
  }

  /// POST /heartbeat: mantiene el celular "online" en el panel aunque esté
  /// quieto (en reposo no se envían puntos nuevos).
  Future<void> _latido({bool activo = true}) async {
    final cliente = _cliente;
    final deviceId = _deviceId;
    if (cliente == null || deviceId == null) return;
    if (!_registrado && activo) await _registrar();
    try {
      final respuesta = await cliente
          .post(
            _uri('/devices/$deviceId/heartbeat'),
            headers: _headers,
            body: jsonEncode({'battery': _bateria, 'active': activo}),
          )
          .timeout(_timeout);
      respuesta.statusCode < 400 ? _exito() : _fallo();
    } catch (_) {
      _fallo();
    }
  }

  /// POST de una muestra en vivo. Debe llamarse con la muestra ya guardada
  /// (o guardándose) en SQLite: si falla, queda pendiente para el lote.
  void enviar(UbicacionLocal ubicacion) {
    final cliente = _cliente;
    if (cliente == null || !_activo) return;
    // Con muchos envíos en curso (red lenta) la muestra espera en la cola
    // local y se manda en el siguiente lote, sin saturar la conexión.
    if (_enVuelo.length >= _maxEnVuelo) {
      unawaited(_refrescarPendientes());
      return;
    }
    unawaited(_post(cliente, ubicacion));
  }

  Future<void> _post(http.Client cliente, UbicacionLocal ubicacion) async {
    _enVuelo.add(ubicacion.sampleId);
    final inicio = DateTime.now().millisecondsSinceEpoch;
    try {
      final respuesta = await cliente
          .post(
            _uri('/devices/${ubicacion.deviceId}/locations'),
            headers: _headers,
            body: jsonEncode(ubicacion.toJsonServidor()),
          )
          .timeout(_timeout);
      if (respuesta.statusCode < 300) {
        await BaseDatosLocal.instancia.marcarSincronizadas([ubicacion.sampleId]);
        _exito();
        _actualizar(latenciaAckMs: DateTime.now().millisecondsSinceEpoch - inicio);
      } else {
        _fallo();
      }
    } catch (_) {
      _fallo();
    } finally {
      _enVuelo.remove(ubicacion.sampleId);
    }
  }

  /// POST /locations/batch con las muestras que no llegaron al servidor.
  Future<void> _vaciarCola() async {
    final cliente = _cliente;
    final deviceId = _deviceId;
    if (_vaciandoCola || cliente == null || deviceId == null) return;
    _vaciandoCola = true;
    try {
      while (true) {
        final pendientes = await BaseDatosLocal.instancia.pendientes(limite: 200);
        // Se excluyen las muestras en vivo que aún esperan respuesta.
        final lote = pendientes
            .where((item) => !_enVuelo.contains(item.sampleId))
            .toList();
        if (lote.isEmpty) break;
        final respuesta = await cliente
            .post(
              _uri('/devices/$deviceId/locations/batch'),
              headers: _headers,
              body: jsonEncode({
                'locations': lote
                    .map((item) => item.toJsonServidor(enVivo: false))
                    .toList(),
              }),
            )
            .timeout(const Duration(seconds: 15));
        if (respuesta.statusCode >= 400 && respuesta.statusCode != 207) {
          _fallo();
          break;
        }
        final aceptados = ((jsonDecode(respuesta.body) as Map)['accepted'] as List?)
                ?.whereType<String>()
                .toList() ??
            const <String>[];
        await BaseDatosLocal.instancia.marcarSincronizadas(aceptados);
        _exito();
        if (pendientes.length < 200 || aceptados.isEmpty) break;
      }
    } catch (_) {
      _fallo();
    } finally {
      _vaciandoCola = false;
      await _refrescarPendientes();
    }
  }

  Future<void> _refrescarPendientes() async {
    try {
      final cantidad = await BaseDatosLocal.instancia.contarPendientes();
      _actualizar(pendientes: cantidad);
    } catch (_) {}
  }

  void _actualizar({
    EstadoEnlace? enlace,
    int? rttMs,
    int? latenciaAckMs,
    int? pendientes,
  }) {
    if (_desechado) return;
    estado.value = estado.value.copyWith(
      enlace: enlace,
      rttMs: rttMs,
      latenciaAckMs: latenciaAckMs,
      pendientes: pendientes,
    );
  }

  /// Detiene el envío (al terminar el recorrido): envía lo pendiente y avisa
  /// al servidor para que el panel lo muestre offline de inmediato.
  Future<void> detener() async {
    if (!_activo) return;
    _activo = false;
    _temporizadorReloj?.cancel();
    _temporizadorLatido?.cancel();
    _temporizadorCola?.cancel();
    try {
      await _vaciarCola().timeout(const Duration(seconds: 5));
    } catch (_) {}
    await _latido(activo: false);
    _actualizar(enlace: EstadoEnlace.desconectado);
  }

  void dispose() {
    unawaited(detener().whenComplete(() {
      _cliente?.close();
      _cliente = null;
    }));
    _desechado = true;
    estado.dispose();
  }

  (String, String)? _cacheDispositivo;

  Future<(String, String)> _datosDispositivo() async {
    final cache = _cacheDispositivo;
    if (cache != null) return cache;
    try {
      if (Platform.isAndroid) {
        final info = await _informacionDispositivo.androidInfo;
        return _cacheDispositivo = ('android', '${info.manufacturer} ${info.model}');
      }
      if (Platform.isIOS) {
        final info = await _informacionDispositivo.iosInfo;
        return _cacheDispositivo = ('ios', info.utsname.machine);
      }
    } catch (_) {}
    return _cacheDispositivo = (Platform.operatingSystem, 'dispositivo');
  }
}
