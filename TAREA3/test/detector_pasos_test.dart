import 'dart:math' as math;

import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';

import 'package:app/servicios/detector_pasos.dart';
import 'package:app/servicios/filtro_gps.dart';

/// Simula el acelerómetro a 50 Hz durante [segundos].
int pasosDetectados(double Function(double t) senal, double segundos) {
  final detector = DetectorPasos();
  var total = 0;
  for (var ms = 0; ms < segundos * 1000; ms += 20) {
    total += detector.procesar(senal(ms / 1000), ms);
  }
  return total;
}

void main() {
  final ruido = math.Random(7);
  double ruidoMesa() => (ruido.nextDouble() - 0.5) * 0.1;

  group('DetectorPasos', () {
    test('caminar (~1.8 pasos/s) cuenta los pasos', () {
      // Cada paso: pico de ~2.5 m/s² sobre la gravedad.
      final pasos = pasosDetectados(
        (t) => 9.81 + 2.5 * math.sin(2 * math.pi * 1.8 * t) + ruidoMesa(),
        10,
      );
      // 18 pasos en 10 s (se toleran los primeros de confirmación).
      expect(pasos, inInclusiveRange(15, 19));
    });

    test('teléfono sobre la mesa: 0 pasos', () {
      expect(pasosDetectados((t) => 9.81 + ruidoMesa(), 20), 0);
    });

    test('agarrar y mover el teléfono (picos irregulares): 0 pasos', () {
      // Picos fuertes pero sin ritmo: 0.2 s, 1.6 s, 1.9 s, 4.0 s, 4.15 s.
      const picos = [0.2, 1.6, 1.9, 4.0, 4.15, 6.5];
      double senal(double t) {
        var extra = 0.0;
        for (final p in picos) {
          final d = t - p;
          if (d >= 0 && d < 0.15) extra += 4 * math.sin(math.pi * d / 0.15);
        }
        return 9.81 + extra + ruidoMesa();
      }
      expect(pasosDetectados(senal, 8), 0);
    });

    test('girar el teléfono en la mano (cambio lento): 0 pasos', () {
      expect(
        pasosDetectados((t) => 9.81 + 1.5 * math.sin(2 * math.pi * 0.4 * t) + ruidoMesa(), 10),
        0,
      );
    });
  });

  group('FiltroGps con presupuesto de pasos', () {
    test('sin pasos, el salto del GPS no mueve el punto', () {
      final filtro = FiltroGps();
      filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 10, velocidad: 0, rumbo: 0, tiempoMs: 0);
      final r = filtro.procesar(
        latitud: -13.5 + 10 / 111320, longitud: -71.9,
        precision: 10, velocidad: 0.4, rumbo: 0, tiempoMs: 1000, pasosDesdeUltimoPunto: 0,
      )!;
      expect(r.esNuevo, isFalse);
      expect(r.punto, const LatLng(-13.5, -71.9));
    });

    test('8 pasos justifican ~6 m pero no 15 m', () {
      final filtro = FiltroGps();
      filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 5, velocidad: 0, rumbo: 0, tiempoMs: 0);
      final lejos = filtro.procesar(
        latitud: -13.5 + 15 / 111320, longitud: -71.9,
        precision: 5, velocidad: 0, rumbo: 0, tiempoMs: 3000, pasosDesdeUltimoPunto: 8,
      )!;
      expect(lejos.esNuevo, isFalse);
      final cerca = filtro.procesar(
        latitud: -13.5 + 6 / 111320, longitud: -71.9,
        precision: 5, velocidad: 0, rumbo: 0, tiempoMs: 4000, pasosDesdeUltimoPunto: 8,
      )!;
      expect(cerca.esNuevo, isTrue);
      expect(cerca.punto.latitude, -13.5 + 6 / 111320);
    });

    test('en vehículo (velocidad GNSS) se acepta sin pasos', () {
      final filtro = FiltroGps();
      filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 5, velocidad: 10, rumbo: 0, tiempoMs: 0);
      final r = filtro.procesar(
        latitud: -13.5 + 10 / 111320, longitud: -71.9,
        precision: 5, velocidad: 10, rumbo: 0, tiempoMs: 1000, pasosDesdeUltimoPunto: 0,
      )!;
      expect(r.esNuevo, isTrue);
    });
  });
}
