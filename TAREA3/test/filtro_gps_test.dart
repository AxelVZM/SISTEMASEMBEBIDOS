import 'dart:math' as math;

import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';

import 'package:app/servicios/filtro_gps.dart';
import 'package:app/servicios/ruta_gps.dart';

// Simulador de GPS de celular con los valores medidos en el Honor CRT-NX3:
// precisión ±2-3,5 m, Doppler quieto 0-0,14 m/s (picos hasta 0,4),
// caminando 1,1-1,8 m/s, y deriva lenta estando quieto (20 m en 25 s).

const _origen = LatLng(-13.5236, -71.95737);
const _mLat = 111320.0;
final _mLng = 111320.0 * math.cos(_origen.latitude * math.pi / 180);
const _distancia = Distance();

LatLng _desplazar(double esteM, double norteM) =>
    LatLng(_origen.latitude + norteM / _mLat, _origen.longitude + esteM / _mLng);

double _metros(LatLng a, LatLng b) => _distancia.as(LengthUnit.Meter, a, b);

class _Gps {
  _Gps(int semilla) : _azar = math.Random(semilla);
  final math.Random _azar;

  double gauss(double sd) {
    final u1 = 1 - _azar.nextDouble();
    final u2 = _azar.nextDouble();
    return sd * math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2);
  }

  double uniforme(double a, double b) => a + (b - a) * _azar.nextDouble();
}

/// Aplica una lectura al filtro y a la ruta, como hace main.dart.
class _Sistema {
  _Sistema({FiltroGps? filtro}) : filtro = filtro ?? FiltroGps(precisionMaxima: 25);
  final FiltroGps filtro;
  final ruta = RutaGps();
  final enviados = <CambioRuta>[];
  int _n = 0;

  LecturaFiltrada? leer(LatLng p, {
    required double precision,
    required double velocidad,
    required int tiempoMs,
    int? pasos,
    double precisionVelocidad = 0.3,
  }) {
    final r = filtro.procesar(
      latitud: p.latitude, longitud: p.longitude, precision: precision,
      velocidad: velocidad, rumbo: 0, tiempoMs: tiempoMs,
      pasosDesdeUltimoPunto: pasos, precisionVelocidad: precisionVelocidad,
    );
    if (r != null) {
      final cambio = ruta.agregar(r, 'm${++_n}', tiempoMs);
      if (cambio != null) enviados.add(cambio);
    }
    return r;
  }

  /// Longitud dibujada (suma de los tramos).
  double get longitudDibujada {
    var total = 0.0;
    for (final tramo in ruta.tramos) {
      for (var i = 1; i < tramo.length; i++) {
        total += _metros(tramo[i - 1].punto, tramo[i].punto);
      }
    }
    return total;
  }
}

void main() {
  group('A · usuario detenido', () {
    test('5 min quieto con ruido, deriva y pasos falsos: no dibuja recorrido', () {
      for (final semilla in [1, 2, 3, 4, 5]) {
        final gps = _Gps(semilla);
        final s = _Sistema();
        var derivaE = 0.0, derivaN = 0.0;
        for (var i = 0; i < 600; i++) {
          // Deriva lenta tipo "random walk" (como la medida en el Honor) +
          // ruido blanco de ±2-3 m.
          derivaE = (derivaE + gps.gauss(0.25)).clamp(-20, 20);
          derivaN = (derivaN + gps.gauss(0.25)).clamp(-20, 20);
          final precision = gps.uniforme(1.8, 3.5);
          s.leer(
            _desplazar(derivaE + gps.gauss(1.5), derivaN + gps.gauss(1.5)),
            precision: precision,
            // Doppler quieto: 0-0,15 m/s con algún pico de 0,35.
            velocidad: i % 37 == 0 ? 0.35 : gps.uniforme(0, 0.15),
            tiempoMs: i * 500,
            // El podómetro cuenta pasos falsos al mover el teléfono en la mano.
            pasos: i % 20 < 4 ? 3 : 0,
          );
        }
        expect(s.longitudDibujada, lessThan(3), reason: 'semilla $semilla');
        expect(s.ruta.totalPuntos, 1, reason: 'semilla $semilla');
        expect(_metros(s.ruta.ultimo!.punto, _origen), lessThan(8), reason: 'semilla $semilla');
      }
    });

    test('deriva real medida (≈23 m en 25 s, ±3 m, v≈0,03): el punto no se arrastra', () {
      final s = _Sistema();
      s.leer(_origen, precision: 3.3, velocidad: 0, tiempoMs: 0);
      for (var i = 1; i <= 50; i++) {
        s.leer(_desplazar(i * 0.46, 0), precision: 3.3 - i * 0.012,
            velocidad: 0.03, tiempoMs: i * 500, pasos: 2);
      }
      expect(s.ruta.totalPuntos, 1);
      expect(_metros(s.ruta.ultimo!.punto, _origen), lessThan(3));
    });

    test('3 pasos reales (≈2,2 m) con ruido: no dibuja un tramo largo', () {
      for (final semilla in [11, 12, 13, 14, 15, 16, 17, 18]) {
        final gps = _Gps(semilla);
        final s = _Sistema();
        // 10 s quieto, 2 s caminando (3 pasos a 1,1 m/s), 10 s quieto.
        var norte = 0.0;
        for (var i = 0; i < 44; i++) {
          final caminando = i >= 20 && i < 24;
          if (caminando) norte += 1.1 * 0.5;
          s.leer(
            _desplazar(gps.gauss(1.5), norte + gps.gauss(1.5)),
            precision: 2.5,
            velocidad: caminando ? 1.1 + gps.gauss(0.15) : gps.uniforme(0, 0.15),
            tiempoMs: i * 500,
            pasos: caminando ? 3 : 0,
          );
        }
        expect(s.longitudDibujada, lessThan(5), reason: 'semilla $semilla');
      }
    });
  });

  group('B · caminata real', () {
    test('60 s a 1,3 m/s: puntos en orden, sobre el recorrido y sin perder distancia', () {
      for (final semilla in [21, 22, 23, 24, 25]) {
        final gps = _Gps(semilla);
        final s = _Sistema();
        final verdad = <int, LatLng>{};
        for (var i = 0; i <= 120; i++) {
          final real = _desplazar(0, 1.3 * i * 0.5);
          verdad[i * 500] = real;
          s.leer(
            _desplazar(gps.gauss(1.2), 1.3 * i * 0.5 + gps.gauss(1.2)),
            precision: gps.uniforme(1.8, 3),
            velocidad: 1.3 + gps.gauss(0.15),
            tiempoMs: i * 500,
            pasos: 1,
          );
        }
        final puntos = s.ruta.tramos.expand((t) => t).toList();
        expect(s.ruta.tramos.length, 1, reason: 'un solo tramo continuo');
        expect(puntos.length, greaterThanOrEqualTo(15), reason: 'semilla $semilla');
        for (var i = 1; i < puntos.length; i++) {
          expect(puntos[i].tiempoMs, greaterThan(puntos[i - 1].tiempoMs));
        }
        for (final p in puntos) {
          // Cada vértice es una lectura real, a menos de 6 m de donde estaba.
          expect(_metros(p.punto, verdad[p.tiempoMs]!), lessThan(6));
        }
        // 78 m reales: la ruta dibujada no los pierde ni los infla.
        expect(s.longitudDibujada, inInclusiveRange(65, 95), reason: 'semilla $semilla');
        expect(_metros(puntos.last.punto, verdad[60000]!), lessThan(8));
      }
    });

    test('al echar a andar tras estar quieto, avanza en menos de 4 s', () {
      final s = _Sistema();
      for (var i = 0; i < 20; i++) {
        s.leer(_origen, precision: 2.5, velocidad: 0.05, tiempoMs: i * 500);
      }
      int? primerMovimientoMs;
      for (var i = 1; i <= 12; i++) {
        final r = s.leer(_desplazar(0, 1.3 * i * 0.5), precision: 2.5,
            velocidad: 1.3, tiempoMs: 10000 + i * 500)!;
        if (r.enMovimiento && primerMovimientoMs == null) primerMovimientoMs = i * 500;
      }
      expect(primerMovimientoMs, isNotNull);
      expect(primerMovimientoMs!, lessThanOrEqualTo(4000));
    });

    test('en vehículo cada lectura es un punto exacto', () {
      final s = _Sistema();
      for (var i = 0; i <= 10; i++) {
        final p = _desplazar(0, i * 8.0);
        final r = s.leer(p, precision: 4, velocidad: 8, tiempoMs: i * 1000)!;
        expect(r.esNuevo, isTrue);
        expect(r.punto, p);
      }
      expect(s.ruta.totalPuntos, 11);
    });

    test('sin velocidad Doppler (bajo techo) usa el podómetro como respaldo', () {
      final s = _Sistema();
      s.leer(_origen, precision: 3, velocidad: 0, tiempoMs: 0, precisionVelocidad: 0);
      // 6 m con 10 pasos (7,5 m): movimiento.
      final r = s.leer(_desplazar(0, 6), precision: 3, velocidad: 0, tiempoMs: 5000,
          pasos: 10, precisionVelocidad: 0)!;
      expect(r.enMovimiento, isTrue);
      // 6 m más con solo 3 pasos (2,25 m): ruido.
      final ruido = s.leer(_desplazar(0, 12), precision: 3, velocidad: 0, tiempoMs: 6000,
          pasos: 3, precisionVelocidad: 0)!;
      expect(ruido.esNuevo, isFalse);
    });
  });

  test('A · quieto con velocidad 0,00 sin precisión: no vuelve al podómetro', () {
    final s = _Sistema();
    s.leer(_origen, precision: 2.5, velocidad: 0.05, tiempoMs: 0);
    // Lecturas con speed=0 y speedAccuracy=0 y pasos falsos de agarrar el
    // teléfono, con ruido de 4-5 m.
    for (var i = 1; i <= 20; i++) {
      s.leer(_desplazar(i.isEven ? 4.5 : -4.5, 0), precision: 2.5, velocidad: 0,
          precisionVelocidad: 0, tiempoMs: i * 500, pasos: 8);
    }
    expect(s.ruta.totalPuntos, 1);
  });

  group('C · salto anómalo', () {
    test('lectura a 300 m en 1 s: se descarta y no crea línea', () {
      final s = _Sistema();
      s.leer(_origen, precision: 3, velocidad: 0, tiempoMs: 0);
      expect(s.leer(_desplazar(300, 0), precision: 4, velocidad: 0, tiempoMs: 1000), isNull);
      expect(s.filtro.ultimaDecision, contains('salto imposible'));
      expect(s.ruta.totalPuntos, 1);
    });

    test('salto de 18 m con Doppler 0,05 m/s (dato real): se mantiene el punto', () {
      final s = _Sistema();
      s.leer(_origen, precision: 3.4, velocidad: 0.13, tiempoMs: 0);
      for (var i = 1; i <= 20; i++) {
        s.leer(_origen, precision: 3.4, velocidad: 0.1, tiempoMs: i * 500, pasos: 5);
      }
      final r = s.leer(_desplazar(-8.6, 15.8), precision: 3.9, velocidad: 0.05,
          tiempoMs: 10500, pasos: 15)!;
      expect(r.esNuevo, isFalse);
      expect(r.motivo, contains('ruido'));
      expect(s.ruta.totalPuntos, 1);
    });
  });

  group('D · mala precisión', () {
    test('±40 m se descarta; ±80 m no sirve ni para iniciar', () {
      final s = _Sistema();
      expect(s.leer(_origen, precision: 80, velocidad: 0, tiempoMs: 0), isNull);
      expect(s.filtro.ultimaDecision, contains('imprecisa'));
      s.leer(_origen, precision: 3, velocidad: 0, tiempoMs: 500);
      expect(s.leer(_desplazar(30, 0), precision: 40, velocidad: 1.2, tiempoMs: 1000), isNull);
      expect(s.ruta.totalPuntos, 1);
      expect(s.ruta.ultimo!.precision, 3);
    });
  });

  group('E · lectura antigua o fuera de orden', () {
    test('una lectura capturada antes que la última no altera la ruta', () {
      final s = _Sistema();
      s.leer(_origen, precision: 3, velocidad: 0, tiempoMs: 10000);
      final antigua = s.leer(_desplazar(0, 10), precision: 2, velocidad: 1.3, tiempoMs: 4000);
      expect(antigua, isNull);
      expect(s.filtro.ultimaDecision, contains('fuera de orden'));
      final repetida = s.leer(_origen, precision: 2, velocidad: 0, tiempoMs: 10000);
      expect(repetida, isNull);
      expect(s.ruta.totalPuntos, 1);
    });
  });

  group('F · pérdida de señal', () {
    test('tras 30 s sin señal empieza un tramo nuevo, sin línea ficticia', () {
      final s = _Sistema();
      for (var i = 0; i <= 20; i++) {
        s.leer(_desplazar(0, 1.3 * i * 0.5), precision: 2.5, velocidad: 1.3, tiempoMs: i * 500);
      }
      final antes = s.longitudDibujada;
      // Túnel: 30 s sin lecturas; reaparece 40 m más allá.
      final r = s.leer(_desplazar(0, 13 + 40), precision: 3, velocidad: 1.3, tiempoMs: 40000)!;
      expect(r.inicioTramo, isTrue);
      expect(r.motivo, contains('sin señal'));
      expect(s.ruta.tramos.length, 2);
      expect(s.longitudDibujada, antes, reason: 'el hueco no suma distancia');
      expect(s.enviados.last.inicioTramo, isTrue, reason: 'el servidor recibe segmentStart');
      // Y sigue trazando normalmente en el tramo nuevo.
      for (var i = 1; i <= 8; i++) {
        s.leer(_desplazar(0, 53 + 1.3 * i * 0.5), precision: 2.5, velocidad: 1.3,
            tiempoMs: 40000 + i * 500);
      }
      expect(s.ruta.tramos.last.length, greaterThan(1));
    });

    test('lecturas imprecisas seguidas durante 20 s también cortan el tramo', () {
      final s = _Sistema();
      s.leer(_origen, precision: 3, velocidad: 0, tiempoMs: 0);
      for (var i = 1; i <= 40; i++) {
        s.leer(_desplazar(i * 2.0, 0), precision: 60, velocidad: 1, tiempoMs: i * 500);
      }
      final r = s.leer(_desplazar(80, 0), precision: 3, velocidad: 1.2, tiempoMs: 20500)!;
      expect(r.inicioTramo, isTrue);
      expect(s.ruta.tramos.length, 2);
    });
  });

  group('Corrección en reposo (coherencia app ↔ servidor)', () {
    test('un primer fix malo se corrige y el cambio indica qué punto reemplaza', () {
      final s = _Sistema();
      s.leer(_origen, precision: 17, velocidad: 0, tiempoMs: 0);
      final r = s.leer(_desplazar(0, 6), precision: 4, velocidad: 0, tiempoMs: 1000)!;
      expect(r.esCorreccion, isTrue);
      expect(s.ruta.totalPuntos, 1);
      expect(s.ruta.ultimo!.punto, _desplazar(0, 6));
      expect(s.enviados.last.reemplaza, 'm1');
      expect(s.enviados.last.inicioTramo, isTrue, reason: 'conserva el inicio de tramo');
      expect(s.ruta.distanciaMetros, 0);
    });

    test('lectura más precisa pero lejos del origen del reposo: se ignora', () {
      final s = _Sistema();
      s.leer(_origen, precision: 10, velocidad: 0, tiempoMs: 0);
      final r = s.leer(_desplazar(0, 15), precision: 3, velocidad: 0, tiempoMs: 1000)!;
      expect(r.esNuevo, isFalse);
    });
  });
}
