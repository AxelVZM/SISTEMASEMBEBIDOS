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
    test('cada lectura aceptada es exactamente la posición del GPS', () {
      final filtro = FiltroGps();
      for (var i = 0; i <= 10; i++) {
        final lat = -13.5 + i * 1.4 / 111320;
        final r = filtro.procesar(
          latitud: lat, longitud: -71.9,
          precision: 5, velocidad: 1.4, rumbo: 0, tiempoMs: i * 1000,
        )!;
        expect(r.esNuevo, isTrue);
        expect(r.punto.latitude, lat);
        expect(r.punto.longitude, -71.9);
      }
    });

    test('quieto (acelerómetro): el ruido no mueve el punto', () {
      final filtro = FiltroGps();
      const lat = -13.53195, lng = -71.96746;
      filtro.procesar(latitud: lat, longitud: lng, precision: 15, velocidad: 0, rumbo: 0, tiempoMs: 0);
      for (var i = 1; i <= 60; i++) {
        final dLat = ((i * 37) % 11 - 5) / 5 * 15 / 111320;
        final dLng = ((i * 53) % 13 - 6) / 6 * 15 / 108240;
        final r = filtro.procesar(
          latitud: lat + dLat, longitud: lng + dLng,
          precision: 15, velocidad: 0, rumbo: 0, tiempoMs: i * 1000,
          sensorEnReposo: true,
        )!;
        expect(r.esNuevo, isFalse);
        expect(r.enMovimiento, isFalse);
        expect(const Distance().as(LengthUnit.Meter, const LatLng(lat, lng), r.punto), 0);
      }
    });

    test('al moverse otra vez sigue cada punto real de inmediato', () {
      final filtro = FiltroGps();
      for (var i = 0; i <= 5; i++) {
        filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 5, velocidad: 0, rumbo: 0, tiempoMs: i * 1000, sensorEnReposo: true);
      }
      final lat = -13.5 + 2 / 111320;
      final r = filtro.procesar(latitud: lat, longitud: -71.9, precision: 5, velocidad: 1.4, rumbo: 0, tiempoMs: 6000)!;
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
