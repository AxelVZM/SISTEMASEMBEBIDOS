import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

import '../modelos/ubicacion_local.dart';

class BaseDatosLocal {
  BaseDatosLocal._();

  static final instancia = BaseDatosLocal._();
  Database? _baseDatos;

  Future<Database> get baseDatos async {
    final existente = _baseDatos;
    if (existente != null) return existente;
    final ruta = join(await getDatabasesPath(), 'rastro_local.db');
    return _baseDatos = await openDatabase(
      ruta,
      version: 2,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timestamp TEXT NOT NULL,
            accuracy REAL NOT NULL,
            speed REAL NOT NULL DEFAULT 0,
            heading REAL NOT NULL DEFAULT 0,
            battery INTEGER,
            sync_status TEXT NOT NULL DEFAULT 'pending'
          )
        ''');
        await db.execute(
          'CREATE INDEX idx_locations_timestamp ON locations(timestamp)',
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
      },
    );
  }

  Future<int> insertarUbicacion(UbicacionLocal ubicacion) async {
    final db = await baseDatos;
    return db.insert('locations', ubicacion.toMap());
  }

  Future<List<UbicacionLocal>> pendientes({int limite = 500}) async {
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

  Future<void> marcarSincronizada(int id) async {
    final db = await baseDatos;
    await db.update(
      'locations',
      {'sync_status': 'synced'},
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  Future<void> cerrar() async {
    await _baseDatos?.close();
    _baseDatos = null;
  }
}
