import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

import '../modelos/ubicacion_local.dart';

class BaseDatosLocal {
  BaseDatosLocal._();

  static final instancia = BaseDatosLocal._();
  Database? _baseDatos;
  Future<Database>? _apertura;

  Future<Database> get baseDatos {
    final existente = _baseDatos;
    if (existente != null) return Future.value(existente);
    // Evita abrir la base dos veces si llegan varias muestras a la vez.
    return _apertura ??= _abrir();
  }

  Future<Database> _abrir() async {
    final ruta = join(await getDatabasesPath(), 'rastro_local.db');
    final db = await openDatabase(
      ruta,
      version: 4,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id TEXT,
            device_id TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timestamp TEXT NOT NULL,
            accuracy REAL NOT NULL,
            speed REAL NOT NULL DEFAULT 0,
            heading REAL NOT NULL DEFAULT 0,
            altitude REAL,
            battery INTEGER,
            sync_status TEXT NOT NULL DEFAULT 'pending',
            replaces TEXT,
            segment_start INTEGER NOT NULL DEFAULT 0
          )
        ''');
        await db.execute(
          'CREATE INDEX idx_locations_timestamp ON locations(timestamp)',
        );
        await db.execute(
          'CREATE INDEX idx_locations_sync ON locations(sync_status)',
        );
        await db.execute(
          'CREATE INDEX idx_locations_sample ON locations(sample_id)',
        );
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        if (oldVersion < 2) {
          await db.execute(
            'ALTER TABLE locations ADD COLUMN speed REAL NOT NULL DEFAULT 0',
          );
          await db.execute(
            'ALTER TABLE locations ADD COLUMN heading REAL NOT NULL DEFAULT 0',
          );
          await db.execute('ALTER TABLE locations ADD COLUMN battery INTEGER');
        }
        if (oldVersion < 3) {
          await db.execute('ALTER TABLE locations ADD COLUMN sample_id TEXT');
          await db.execute('ALTER TABLE locations ADD COLUMN altitude REAL');
          await db.execute(
            "UPDATE locations SET sample_id = device_id || '-' || id WHERE sample_id IS NULL",
          );
          await db.execute(
            'CREATE INDEX IF NOT EXISTS idx_locations_sync ON locations(sync_status)',
          );
          await db.execute(
            'CREATE INDEX IF NOT EXISTS idx_locations_sample ON locations(sample_id)',
          );
        }
        if (oldVersion < 4) {
          await db.execute('ALTER TABLE locations ADD COLUMN replaces TEXT');
          await db.execute(
            'ALTER TABLE locations ADD COLUMN segment_start INTEGER NOT NULL DEFAULT 0',
          );
        }
      },
    );
    // Limpieza: las muestras ya sincronizadas de hace más de 7 días sobran.
    final limite = DateTime.now()
        .subtract(const Duration(days: 7))
        .toUtc()
        .toIso8601String();
    await db.delete(
      'locations',
      where: 'sync_status = ? AND timestamp < ?',
      whereArgs: ['synced', limite],
    );
    return _baseDatos = db;
  }

  Future<int> insertarUbicacion(UbicacionLocal ubicacion) async {
    final db = await baseDatos;
    return db.insert('locations', ubicacion.toMap());
  }

  Future<List<UbicacionLocal>> pendientes({int limite = 200}) async {
    final db = await baseDatos;
    final filas = await db.query(
      'locations',
      where: 'sync_status = ?',
      whereArgs: ['pending'],
      orderBy: 'timestamp ASC',
      limit: limite,
    );
    return filas.map(UbicacionLocal.fromMap).toList();
  }

  Future<int> contarPendientes() async {
    final db = await baseDatos;
    return Sqflite.firstIntValue(
          await db.rawQuery(
            "SELECT COUNT(*) FROM locations WHERE sync_status = 'pending'",
          ),
        ) ??
        0;
  }

  Future<void> marcarSincronizadas(List<String> sampleIds) async {
    if (sampleIds.isEmpty) return;
    final db = await baseDatos;
    final batch = db.batch();
    for (final sampleId in sampleIds) {
      batch.update(
        'locations',
        {'sync_status': 'synced'},
        where: 'sample_id = ?',
        whereArgs: [sampleId],
      );
    }
    await batch.commit(noResult: true);
  }

  Future<void> cerrar() async {
    await _baseDatos?.close();
    _baseDatos = null;
    _apertura = null;
  }
}
