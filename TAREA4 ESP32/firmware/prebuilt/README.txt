Firmware 2.3.0 — ESP32 original, 4 MB Flash, ESP-IDF 5.4.2.
Preserves world-safe country code 01. WPS metadata, BLE scan responses and, new in 2.3.0:
Wi-Fi Direct (P2P) Device Info (phone name + device type) and vendor-specific IE OUIs (vendor_ies) from probe/association requests.
Combined esp32-detector.bin: flash at 0x0.
Separate: bootloader at 0x1000, partition-table at 0x8000, application at 0x10000.
Update backend and firmware together.
