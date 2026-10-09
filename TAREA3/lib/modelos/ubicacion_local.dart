class UbicacionLocal {
  const UbicacionLocal({
    this.id,
    required this.deviceId,
    required this.latitude,
    required this.longitude,
    required this.timestamp,
    required this.accuracy,
    this.speed = 0,
    this.heading = 0,
    this.battery,
    this.syncStatus = 'pending',
  });

  final int? id;
  final String deviceId;
  final double latitude;
  final double longitude;
  final DateTime timestamp;
  final double accuracy;
  final double speed;
  final double heading;
  final int? battery;
  final String syncStatus;

  Map<String, Object?> toMap() => {
        'id': id,
        'device_id': deviceId,
        'latitude': latitude,
        'longitude': longitude,
        'timestamp': timestamp.toUtc().toIso8601String(),
        'accuracy': accuracy,
        'speed': speed,
        'heading': heading,
        'battery': battery,
        'sync_status': syncStatus,
      };

  factory UbicacionLocal.fromMap(Map<String, Object?> map) => UbicacionLocal(
        id: map['id'] as int?,
        deviceId: map['device_id'] as String,
        latitude: (map['latitude'] as num).toDouble(),
        longitude: (map['longitude'] as num).toDouble(),
        timestamp: DateTime.parse(map['timestamp'] as String).toLocal(),
        accuracy: (map['accuracy'] as num).toDouble(),
        speed: (map['speed'] as num?)?.toDouble() ?? 0,
        heading: (map['heading'] as num?)?.toDouble() ?? 0,
        battery: (map['battery'] as num?)?.toInt(),
        syncStatus: map['sync_status'] as String? ?? 'pending',
      );
}
