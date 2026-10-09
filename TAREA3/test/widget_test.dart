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

  group('FiltroGps', () {
    test('quieto: el ruido no mueve el punto ni cuenta como movimiento', () {
      final filtro = FiltroGps();
      const lat = -13.53195, lng = -71.96746;
      filtro.procesar(latitud: lat, longitud: lng, precision: 5, velocidad: 0, rumbo: 0, tiempoMs: 0);
      var movimientos = 0;
      for (var i = 1; i <= 30; i++) {
        // Ruido de ±3 m alrededor del mismo punto.
        final ruido = (i.isEven ? 1 : -1) * 0.000027;
        final r = filtro.procesar(
          latitud: lat + ruido, longitud: lng - ruido,
          precision: 5, velocidad: 0, rumbo: 0, tiempoMs: i * 1000,
        )!;
        if (r.enMovimiento) movimientos++;
      }
      expect(movimientos, 0);
    });

    test('reposo por acelerómetro: saltos de ±15 m (interior) no mueven el punto', () {
      final filtro = FiltroGps();
      const lat = -13.53195, lng = -71.96746;
      final inicio = filtro.procesar(latitud: lat, longitud: lng, precision: 15, velocidad: 0, rumbo: 0, tiempoMs: 0)!.punto;
      LecturaFiltrada? r;
      var movimientos = 0;
      for (var i = 1; i <= 60; i++) {
        // Saltos pseudoaleatorios de hasta ~15 m en ambas direcciones.
        final dLat = ((i * 37) % 11 - 5) / 5 * 15 / 111320;
        final dLng = ((i * 53) % 13 - 6) / 6 * 15 / 108240;
        r = filtro.procesar(
          latitud: lat + dLat, longitud: lng + dLng,
          precision: 15, velocidad: 0, rumbo: 0, tiempoMs: i * 1000,
          sensorEnReposo: true,
        );
        if (r!.enMovimiento) movimientos++;
      }
      final deriva = const Distance().as(LengthUnit.Meter, inicio, r!.punto);
      expect(movimientos, 0);
      expect(deriva, lessThan(2));
    });

    test('al salir del reposo vuelve a seguir sin retraso', () {
      final filtro = FiltroGps();
      for (var i = 0; i <= 30; i++) {
        filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 5, velocidad: 0, rumbo: 0, tiempoMs: i * 1000, sensorEnReposo: true);
      }
      LecturaFiltrada? r;
      for (var i = 1; i <= 10; i++) {
        r = filtro.procesar(
          latitud: -13.5 + i * 1.4 / 111320, longitud: -71.9,
          precision: 5, velocidad: 1.4, rumbo: 0, tiempoMs: 30000 + i * 1000,
        );
      }
      final esperado = -13.5 + 14 / 111320;
      expect((r!.punto.latitude - esperado).abs() * 111320, lessThan(4));
      expect(r.enMovimiento, isTrue);
    });

    test('sin velocidad reportada igual sigue al caminar', () {
      final filtro = FiltroGps();
      LecturaFiltrada? r;
      // 1.4 m/s hacia el este pero velocidad = 0 (proveedor sin Doppler).
      for (var i = 0; i <= 60; i++) {
        r = filtro.procesar(
          latitud: -13.5, longitud: -71.9 + i * 1.4 / 108240,
          precision: 5, velocidad: 0, rumbo: 0, tiempoMs: i * 1000,
        );
      }
      final esperado = -71.9 + 60 * 1.4 / 108240;
      expect((r!.punto.longitude - esperado).abs() * 108240, lessThan(10));
    });

    test('descarta un salto imposible', () {
      final filtro = FiltroGps();
      filtro.procesar(latitud: -13.5, longitud: -71.9, precision: 5, velocidad: 1, rumbo: 0, tiempoMs: 0);
      // ~1.1 km en 1 s
      final r = filtro.procesar(latitud: -13.49, longitud: -71.9, precision: 8, velocidad: 1, rumbo: 0, tiempoMs: 1000);
      expect(r, isNull);
    });

    test('en movimiento sigue la trayectoria con poco retraso', () {
      final filtro = FiltroGps();
      // 10 m/s hacia el norte, 1 Hz.
      LecturaFiltrada? r;
      for (var i = 0; i <= 10; i++) {
        r = filtro.procesar(
          latitud: -13.5 + i * 10 / 111320, longitud: -71.9,
          precision: 5, velocidad: 10, rumbo: 0, tiempoMs: i * 1000,
        );
      }
      final esperado = -13.5 + 100 / 111320;
      final errorMetros = (r!.punto.latitude - esperado).abs() * 111320;
      expect(errorMetros, lessThan(4));
      expect(r.enMovimiento, isTrue);
    });
  });
}
