import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;

import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/io.dart';

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

  /// Tiempo de ida y vuelta del WebSocket.
  final int? rttMs;

  /// Tiempo desde que se envió la última muestra hasta su confirmación.
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

/// Canal de tiempo real con el servidor.
///
/// - WebSocket persistente (sin handshake HTTP por muestra) con TCP_NODELAY.
/// - Ping cada 2 s: mide RTT y estima el desfase de reloj (estilo NTP) para
///   que la latencia que calcula el servidor sea real.
/// - Cada muestra se guarda en SQLite; si no hay red queda pendiente y se
///   envía en lote al reconectar.
class SeguimientoRemoto {
  SeguimientoRemoto({
    this.baseUrl = const String.fromEnvironment(
      'API_URL',
      defaultValue: 'http://18.191.113.248/movimiento/api',
    ),
  });

  final String baseUrl;
  final estado = ValueNotifier(const EstadoRemoto());
  final _informacionDispositivo = DeviceInfoPlugin();
  final _enviadas = <String, int>{};
  final _muestrasReloj = <(int rtt, int offset)>[];

  IOWebSocketChannel? _socket;
  StreamSubscription<dynamic>? _socketSuscripcion;
  Timer? _temporizadorPing;
  Timer? _temporizadorReconexion;
  Timer? _temporizadorCola;
  Completer<void>? _loteEnCurso;
  bool _conectado = false;
  bool _cerrando = true;
  bool _vaciandoCola = false;
  bool _httpEnCurso = false;
  bool _desechado = false;
  int _intentos = 0;
  int _offsetRelojMs = 0;

  String? _deviceId;
  String _nombre = 'Mi celular';
  String _version = '1.0.0';
  int? _bateria;

  /// Diferencia (servidor - teléfono) en milisegundos.
  int get offsetRelojMs => _offsetRelojMs;

  bool get conectado => _conectado;

  set bateria(int? valor) => _bateria = valor;

  Future<void> iniciar({
    required String deviceId,
    required String nombre,
    required String version,
  }) async {
    _deviceId = deviceId;
    _nombre = nombre;
    _version = version;
    _cerrando = false;
    _intentos = 0;
    _temporizadorCola?.cancel();
    _temporizadorCola = Timer.periodic(
      const Duration(seconds: 15),
      (_) => unawaited(_vaciarCola()),
    );
    await _conectar();
  }

  Uri get _uriSocket {
    final base = Uri.parse(baseUrl);
    final prefijo = base.path.endsWith('/api')
        ? base.path.substring(0, base.path.length - 4)
        : '';
    return Uri(
      scheme: base.scheme == 'https' ? 'wss' : 'ws',
      host: base.host,
      port: base.hasPort ? base.port : null,
      path: '$prefijo/ws',
    );
  }

  Future<void> _conectar() async {
    if (_cerrando || _conectado || _socket != null || _deviceId == null) return;
    _actualizar(enlace: EstadoEnlace.conectando);
    try {
      final socket = IOWebSocketChannel.connect(
        _uriSocket,
        pingInterval: const Duration(seconds: 10),
        connectTimeout: const Duration(seconds: 5),
      );
      _socket = socket;
      await socket.ready;
      if (_cerrando) {
        await socket.sink.close();
        return;
      }
      _conectado = true;
      _intentos = 0;
      _socketSuscripcion = socket.stream.listen(
        _recibir,
        onDone: _socketCerrado,
        onError: (_) => _socketCerrado(),
        cancelOnError: true,
      );
      final (plataforma, modelo) = await _datosDispositivo();
      _enviarMensaje({
        'type': 'hello',
        'data': {
          'deviceId': _deviceId,
          'name': _nombre,
          'platform': plataforma,
          'model': modelo,
          'appVersion': _version,
          'battery': _bateria,
        },
      });
      _actualizar(enlace: EstadoEnlace.conectado);
      _ping();
      _temporizadorPing?.cancel();
      _temporizadorPing = Timer.periodic(
        const Duration(seconds: 2),
        (_) => _ping(),
      );
      unawaited(_vaciarCola());
    } catch (_) {
      _socket = null;
      _socketCerrado();
    }
  }

  void _ping() {
    _enviarMensaje({'type': 'ping', 't': DateTime.now().millisecondsSinceEpoch});
  }

  void _recibir(dynamic crudo) {
    if (crudo is! String) return;
    final Map<String, dynamic> mensaje;
    try {
      mensaje = jsonDecode(crudo) as Map<String, dynamic>;
    } catch (_) {
      return;
    }
    final ahora = DateTime.now().millisecondsSinceEpoch;
    switch (mensaje['type']) {
      case 'pong':
        final t0 = (mensaje['t'] as num?)?.toInt();
        final servidor = (mensaje['serverTime'] as num?)?.toInt();
        if (t0 == null || servidor == null) return;
        final rtt = ahora - t0;
        _muestrasReloj.add((rtt, servidor - (t0 + rtt ~/ 2)));
        if (_muestrasReloj.length > 8) _muestrasReloj.removeAt(0);
        // La muestra con menor RTT es la que mejor estima el desfase.
        final mejor = _muestrasReloj.reduce((a, b) => a.$1 <= b.$1 ? a : b);
        _offsetRelojMs = mejor.$2;
        _actualizar(rttMs: rtt);
      case 'location.accepted':
        final sampleId = (mensaje['data'] as Map?)?['sampleId'] as String?;
        if (sampleId == null) return;
        final enviado = _enviadas.remove(sampleId);
        unawaited(_confirmar([sampleId]));
        if (enviado != null) _actualizar(latenciaAckMs: ahora - enviado);
      case 'locations.accepted':
        final ids = ((mensaje['data'] as Map?)?['sampleIds'] as List?)
                ?.whereType<String>()
                .toList() ??
            const <String>[];
        unawaited(
          _confirmar(ids).whenComplete(() {
            if (_loteEnCurso?.isCompleted == false) _loteEnCurso!.complete();
          }),
        );
    }
  }

  Future<void> _confirmar(List<String> sampleIds) async {
    await BaseDatosLocal.instancia.marcarSincronizadas(sampleIds);
  }

  void _socketCerrado() {
    _conectado = false;
    _temporizadorPing?.cancel();
    unawaited(_socketSuscripcion?.cancel());
    _socketSuscripcion = null;
    _socket = null;
    _enviadas.clear();
    if (_loteEnCurso?.isCompleted == false) {
      _loteEnCurso!.completeError(const SocketException('Socket cerrado'));
    }
    _actualizar(enlace: EstadoEnlace.desconectado);
    _programarReconexion();
  }

  void _programarReconexion() {
    if (_cerrando || _temporizadorReconexion?.isActive == true) return;
    // Reintento rápido (0.5 s, 1 s, 2 s... hasta 5 s).
    final espera = math.min(5000, 500 * (1 << math.min(_intentos, 4)));
    _intentos++;
    _temporizadorReconexion = Timer(
      Duration(milliseconds: espera),
      () => unawaited(_conectar()),
    );
  }

  bool _enviarMensaje(Map<String, Object?> mensaje) {
    final socket = _socket;
    if (!_conectado || socket == null) return false;
    try {
      socket.sink.add(jsonEncode(mensaje));
      return true;
    } catch (_) {
      _socketCerrado();
      return false;
    }
  }

  /// Envía una muestra en vivo. Debe llamarse con la muestra ya guardada en
  /// la base local (si falla, queda pendiente y se reenvía después).
  void enviar(UbicacionLocal ubicacion) {
    final enviado = _enviarMensaje({
      'type': 'location',
      'data': ubicacion.toJsonServidor(),
    });
    if (enviado) {
      _enviadas[ubicacion.sampleId] = DateTime.now().millisecondsSinceEpoch;
      if (_enviadas.length > 200) _enviadas.remove(_enviadas.keys.first);
      return;
    }
    // Sin WebSocket: intento HTTP (uno a la vez para no saturar la red).
    unawaited(_enviarHttp(ubicacion));
  }

  Future<void> _enviarHttp(UbicacionLocal ubicacion) async {
    if (_httpEnCurso || _cerrando) return;
    _httpEnCurso = true;
    try {
      final respuesta = await http
          .post(
            Uri.parse('$baseUrl/devices/${ubicacion.deviceId}/locations'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode(ubicacion.toJsonServidor()),
          )
          .timeout(const Duration(seconds: 3));
      if (respuesta.statusCode < 400) await _confirmar([ubicacion.sampleId]);
    } catch (_) {
      // Queda pendiente en SQLite.
    } finally {
      _httpEnCurso = false;
      unawaited(_refrescarPendientes());
    }
  }

  /// Envía en lotes las muestras que no llegaron al servidor.
  Future<void> _vaciarCola() async {
    if (_vaciandoCola || !_conectado) {
      await _refrescarPendientes();
      return;
    }
    _vaciandoCola = true;
    try {
      while (_conectado) {
        final pendientes = await BaseDatosLocal.instancia.pendientes(limite: 200);
        // Se excluyen las muestras en vivo que esperan confirmación.
        final lote = pendientes
            .where((item) => !_enviadas.containsKey(item.sampleId))
            .toList();
        if (lote.isEmpty) break;
        _loteEnCurso = Completer<void>();
        if (!_enviarMensaje({
          'type': 'locations',
          'data': lote.map((item) => item.toJsonServidor(enVivo: false)).toList(),
        })) {
          break;
        }
        await _loteEnCurso!.future.timeout(const Duration(seconds: 10));
        if (pendientes.length < 200) break;
      }
    } catch (_) {
      // Se reintenta en el próximo ciclo o al reconectar.
    } finally {
      _loteEnCurso = null;
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

  /// Cierra el canal (al detener el recorrido).
  Future<void> detener() async {
    // Último intento de enviar lo pendiente antes de cerrar.
    if (_conectado) {
      try {
        await _vaciarCola().timeout(const Duration(seconds: 3));
      } catch (_) {}
    }
    _cerrando = true;
    _temporizadorReconexion?.cancel();
    _temporizadorPing?.cancel();
    _temporizadorCola?.cancel();
    final socket = _socket;
    _socket = null;
    _conectado = false;
    await _socketSuscripcion?.cancel();
    _socketSuscripcion = null;
    await socket?.sink.close();
    _actualizar(enlace: EstadoEnlace.desconectado);
  }

  void dispose() {
    _desechado = true;
    _cerrando = true;
    unawaited(detener());
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
