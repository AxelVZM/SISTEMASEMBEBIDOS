class UbicacionLocal {
  const UbicacionLocal({
    this.id,
    required this.sampleId,
    required this.deviceId,
    required this.latitude,
    required this.longitude,
    required this.timestamp,
    required this.accuracy,
    this.speed = 0,
    this.heading = 0,
    this.altitude,
    this.battery,
    this.syncStatus = 'pending',
  });

  final int? id;
  final String sampleId;
  final String deviceId;
  final double latitude;
  final double longitude;
  final DateTime timestamp;
  final double accuracy;
  final double speed;
  final double heading;
  final double? altitude;
  final int? battery;
  final String syncStatus;

  Map<String, Object?> toMap() => {
        'id': id,
        'sample_id': sampleId,
        'device_id': deviceId,
        'latitude': latitude,
        'longitude': longitude,
        'timestamp': timestamp.toUtc().toIso8601String(),
        'accuracy': accuracy,
        'speed': speed,
        'heading': heading,
        'altitude': altitude,
        'battery': battery,
        'sync_status': syncStatus,
      };

  /// Formato que espera el servidor.
  Map<String, Object?> toJsonServidor({bool enVivo = true}) => {
        'deviceId': deviceId,
        'sampleId': sampleId,
        'latitude': latitude,
        'longitude': longitude,
        'accuracy': accuracy,
        'speed': speed,
        'heading': heading,
        'altitude': altitude,
        'battery': battery,
        'timestamp': timestamp.toUtc().toIso8601String(),
        'live': enVivo,
      };

  factory UbicacionLocal.fromMap(Map<String, Object?> map) {
    final timestamp = DateTime.parse(map['timestamp'] as String).toLocal();
    final deviceId = map['device_id'] as String;
    return UbicacionLocal(
      id: map['id'] as int?,
      sampleId: map['sample_id'] as String? ?? '$deviceId-${map['id']}',
      deviceId: deviceId,
      latitude: (map['latitude'] as num).toDouble(),
      longitude: (map['longitude'] as num).toDouble(),
      timestamp: timestamp,
      accuracy: (map['accuracy'] as num).toDouble(),
      speed: (map['speed'] as num?)?.toDouble() ?? 0,
      heading: (map['heading'] as num?)?.toDouble() ?? 0,
      altitude: (map['altitude'] as num?)?.toDouble(),
      battery: (map['battery'] as num?)?.toInt(),
      syncStatus: map['sync_status'] as String? ?? 'pending',
    );
  }
}
