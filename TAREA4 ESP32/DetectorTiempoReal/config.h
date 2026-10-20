#pragma once
#include <cstdint>
#include <cstddef>
constexpr size_t MAX_RECORDS=96,QUEUE_LENGTH=64;
constexpr uint32_t ACTIVE_TTL_MS=60000,JUST_SEEN_MS=10000,HOP_MS=300;
constexpr uint8_t FIRST_CHANNEL=1,LAST_CHANNEL=11;
constexpr uint32_t WIFI_OBSERVE_MS=10000,BLE_OBSERVE_SECONDS=2;
constexpr int MIN_RSSI=-100;
constexpr int LED_PIN=25; // External LED + 330 ohm resistor. -1 disables.
constexpr bool LED_ACTIVE_HIGH=true;
constexpr int I2C_SDA=21,I2C_SCL=22;
constexpr bool ENABLE_OLED=true,ENABLE_RTC=true;
constexpr uint32_t LOG_FILE_BYTES=131072,LOG_BUFFER_BYTES=4096;
