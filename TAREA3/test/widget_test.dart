import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:app/main.dart';
import 'package:app/servicios/filtro_gps.dart';

void main() {
  testWidgets('Pantalla inicial', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const AplicacionMovimiento());
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Rastro'), findsOneWidget);
    expect(find.text('Iniciar recorrido'), findsOneWidget);
    expect(find.text('Listo para registrar'), findsOneWidget);
  });

  group('FiltroGps (punto por punto)', () {
    test('en vehículo cada lectura es exactamente la posición del GPS', () {
      final filtro = FiltroGps();
      for (var i = 0; i <= 10; i++) {
        final lat = -13.5 + i * 5 / 111320;
        final r = filtro.procesar(
          latitud: lat, longitud: -71.9,
          precision: 5, velocidad: 5, rumbo: 0, tiempoMs: i * 1000,
        )!;
        expect(r.esNuevo, isTrue);
        expect(r.punto.latitude, lat);
        expect(r.punto.longitude, -71.9);
      }
    });

    test('caminando: avanza con puntos reales cuando la distancia es medible', () {
      final filtro = FiltroGps();
      var pasos = 0;
      final aceptados = <double>[];
      // 30 s caminando a 1.4 m/s (≈2 pasos/s), GPS de ±5 m.
      for (var i = 0; i <= 30; i++) {
        final lat = -13.5 + i * 1.4 / 111320;
        final r = filtro.procesar(
          latitud: lat, longitud: -71.9,
          precision: 5, velocidad: 0, rumbo: 0, tiempoMs: i * 1000,
          pasosDesdeUltimoPunto: i == 0 ? null : pasos,
        )!;
        if (r.esNuevo) {
          pasos = 0;
          aceptados.add(r.punto.latitude);
          expect(r.punto.latitude, lat, reason: 'el punto es la lectura real');
        }
        pasos += 2;
      }
      // Avanza a saltos de ~4-5 m (más que el error del GPS), hasta el final.
      expect(aceptados.length, greaterThanOrEqualTo(8));
      expect((aceptados.last - (-13.5 + 30 * 1.4 / 111320)).abs() * 111320, lessThan(5));
    });

    test('tu prueba real: 2 pasos con saltos de 5-12 m no simulan un recorrido', () {
      final filtro = FiltroGps();
      const lat = -13.5237, lng = -71.9572;
      // Punto inicial impreciso (±18.5 m), velocidad 0.
      filtro.procesar(latitud: lat, longitud: lng, precision: 18.5, velocidad: 0, rumbo: 0, tiempoMs: 0);
      // +5.4 m con ±6.8 m: lectura mucho más precisa → corrige el punto.
      final p2 = lat + 5.4 / 111320;
      final r2 = filtro.procesar(latitud: p2, longitud: lng, precision: 6.8, velocidad: 0.4, rumbo: 0, tiempoMs: 15000, pasosDesdeUltimoPunto: 0)!;
      expect(r2.esCorreccion, isTrue);
      expect(r2.enMovimiento, isFalse);
      final fijo = r2.punto.latitude;
      // +12.4 m y +6.6 m más con solo 2 pasos: saltos del GPS → se ignoran.
      for (final (salto, precision, t) in [(12.4, 5.6, 34000), (19.0, 5.4, 40000)]) {
        final r = filtro.procesar(
          latitud: p2 + salto / 111320, longitud: lng,
          precision: precision, velocidad: 0.06, rumbo: 0, tiempoMs: t,
          pasosDesdeUltimoPunto: 2,
        )!;
        expect(r.esNuevo, isFalse, reason: 'salto de $salto m con 2 pasos');
        expect(r.punto.latitude, fijo);
      }
    });

    test('quieto: el ruido de ±15 m no mueve el punto', () {
      final filtro = FiltroGps();
      const lat = -13.53195, lng = -71.96746;
      filtro.procesar(latitud: lat, longitud: lng, precision: 15, velocidad: 0, rumbo: 0, tiempoMs: 0);
      for (var i = 1; i <= 60; i++) {
        final dLat = ((i * 37) % 11 - 5) / 5 * 15 / 111320;
        final dLng = ((i * 53) % 13 - 6) / 6 * 15 / 108240;
        final r = filtro.procesar(
          latitud: lat + dLat, longitud: lng + dLng,
          precision: 15, velocidad: 0, rumbo: 0, tiempoMs: i * 1000,
          pasosDesdeUltimoPunto: 0,
        )!;
        expect(r.esNuevo, isFalse);
        expect(const Distance().as(LengthUnit.Meter, const LatLng(lat, lng), r.punto), 0);
      }
    });

    test('quieto: la deriva lenta del GPS (23 m en 25 s, ±3 m) no arrastra el punto', () {
      final filtro = FiltroGps();
      const lat = -13.5236, lng = -71.95737;
      filtro.procesar(latitud: lat, longitud: lng, precision: 3.3, velocidad: 0, rumbo: 0, tiempoMs: 0);
      LatLng? punto;
      // Datos reales: deriva hacia el este ~1 m/s con precisión mejorando.
      for (var i = 1; i <= 25; i++) {
        final r = filtro.procesar(
          latitud: lat, longitud: lng + (i * 0.9) / 108240,
          precision: 3.3 - i * 0.025, velocidad: 0.03, rumbo: 0, tiempoMs: i * 1000,
          pasosDesdeUltimoPunto: 0,
        )!;
        punto = r.punto;
      }
      expect(const Distance().as(LengthUnit.Meter, const LatLng(lat, lng), punto!), lessThan(3));
    });

    test('quieto: un primer punto malo (±17 m) se corrige con uno preciso cercano', () {
      final filtro = FiltroGps();
      const lat = -13.53195, lng = -71.96746;
      filtro.procesar(latitud: lat, longitud: lng, precision: 17, velocidad: 0, rumbo: 0, tiempoMs: 0);
      final r = filtro.procesar(latitud: lat + 6 / 111320, longitud: lng, precision: 4, velocidad: 0, rumbo: 0, tiempoMs: 1000, pasosDesdeUltimoPunto: 0)!;
      expect(r.esCorreccion, isTrue);
      expect(r.punto.latitude, lat + 6 / 111320);
    });

    test('datos reales del Honor quieto: saltos de 10-30 m se ignoran', () {
      final filtro = FiltroGps();
      const lat = -13.5237, lng = -71.9572;
      filtro.procesar(latitud: lat, longitud: lng, precision: 10, velocidad: 0, rumbo: 0, tiempoMs: 0);
      // Saltos medidos en el celular real con velocidad 0 y precisión ~10 m.
      const saltosNorte = [10.9, -14.9, 14.2, 26.8, -29.9, 25.0];
      for (var i = 0; i < saltosNorte.length; i++) {
        final r = filtro.procesar(
          latitud: lat + saltosNorte[i] / 111320, longitud: lng,
          precision: 10, velocidad: 0, rumbo: 0, tiempoMs: (i + 1) * 1000,
          pasosDesdeUltimoPunto: 0,
        )!;
        expect(r.esNuevo, isFalse, reason: 'salto de ${saltosNorte[i]} m');
        expect(r.punto, const LatLng(lat, lng));
      }
    });

    test('pasos coherentes se aceptan; saltos mayores que los pasos no', () {
      final filtro = FiltroGps();
      filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 5, velocidad: 0, rumbo: 0, tiempoMs: 0);
      final paso = filtro.procesar(latitud: -13.5 + 6 / 111320, longitud: -71.9, precision: 5, velocidad: 0, rumbo: 0, tiempoMs: 4000, pasosDesdeUltimoPunto: 8)!;
      expect(paso.esNuevo, isTrue);
      final salto = filtro.procesar(latitud: -13.5 + 34.5 / 111320, longitud: -71.9, precision: 5, velocidad: 0, rumbo: 0, tiempoMs: 5000, pasosDesdeUltimoPunto: 2)!;
      expect(salto.esNuevo, isFalse);
    });

    test('caminando de verdad (5 pasos, 3,5 m, ±2 m) el punto avanza al instante', () {
      final filtro = FiltroGps();
      filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 2, velocidad: 0, rumbo: 0, tiempoMs: 0);
      final r = filtro.procesar(latitud: -13.5 + 3.5 / 111320, longitud: -71.9, precision: 2, velocidad: 0, rumbo: 0, tiempoMs: 1000, pasosDesdeUltimoPunto: 5)!;
      expect(r.esNuevo, isTrue);
      expect(r.punto.latitude, -13.5 + 3.5 / 111320);
    });

    test('3 pasos y el GPS salta 4-6 m (±3 m): NO dibuja movimiento', () {
      final filtro = FiltroGps();
      filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 3, velocidad: 0, rumbo: 0, tiempoMs: 0);
      for (final salto in [4.0, 5.0, 6.0]) {
        final r = filtro.procesar(latitud: -13.5 + salto / 111320, longitud: -71.9, precision: 3, velocidad: 0, rumbo: 0, tiempoMs: 2000, pasosDesdeUltimoPunto: 3)!;
        expect(r.esNuevo, isFalse, reason: 'salto de $salto m con 3 pasos');
        expect(r.punto.latitude, -13.5);
      }
    });

    test('un cambio menor que el error del GPS no es movimiento', () {
      final filtro = FiltroGps();
      filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 5, velocidad: 0, rumbo: 0, tiempoMs: 0);
      final r = filtro.procesar(latitud: -13.5 + 3 / 111320, longitud: -71.9, precision: 5, velocidad: 0, rumbo: 0, tiempoMs: 1000, pasosDesdeUltimoPunto: 4)!;
      expect(r.esNuevo, isFalse);
    });

    test('quieto: el punto converge a la lectura más precisa sin saltar', () {
      final filtro = FiltroGps();
      // Primer punto malo: ±17 m.
      filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 17, velocidad: 0, rumbo: 0, tiempoMs: 0);
      // Lectura mejor (±10 m) a 9 m: dentro del margen → corrige.
      final a = filtro.procesar(latitud: -13.5 + 9 / 111320, longitud: -71.9, precision: 10, velocidad: 0, rumbo: 0, tiempoMs: 1000, pasosDesdeUltimoPunto: 0)!;
      expect(a.esCorreccion, isTrue);
      // Lectura mejor (±8 m) pero a 20 m: fuera del margen → se ignora.
      final b = filtro.procesar(latitud: -13.5 + 29 / 111320, longitud: -71.9, precision: 8, velocidad: 0, rumbo: 0, tiempoMs: 2000, pasosDesdeUltimoPunto: 0)!;
      expect(b.esNuevo, isFalse);
      expect(b.punto, a.punto);
    });

    test('al volver a caminar sigue el punto real', () {
      final filtro = FiltroGps();
      for (var i = 0; i <= 5; i++) {
        filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 5, velocidad: 0, rumbo: 0, tiempoMs: i * 1000, pasosDesdeUltimoPunto: 0);
      }
      final lat = -13.5 + 6 / 111320;
      final r = filtro.procesar(latitud: lat, longitud: -71.9, precision: 5, velocidad: 1.4, rumbo: 0, tiempoMs: 10000, pasosDesdeUltimoPunto: 8)!;
      expect(r.esNuevo, isTrue);
      expect(r.punto.latitude, lat);
      expect(r.enMovimiento, isTrue);
    });

    test('descarta un salto imposible', () {
      final filtro = FiltroGps();
      filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 5, velocidad: 1, rumbo: 0, tiempoMs: 0);
      final r = filtro.procesar(latitud: -13.49, longitud: -71.9, precision: 8, velocidad: 1, rumbo: 0, tiempoMs: 1000);
      expect(r, isNull);
    });

    test('descarta lecturas imprecisas', () {
      final filtro = FiltroGps();
      filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 5, velocidad: 0, rumbo: 0, tiempoMs: 0);
      final r = filtro.procesar(latitud: -13.5001, longitud: -71.9, precision: 80, velocidad: 0, rumbo: 0, tiempoMs: 1000);
      expect(r, isNull);
    });
  });
}
