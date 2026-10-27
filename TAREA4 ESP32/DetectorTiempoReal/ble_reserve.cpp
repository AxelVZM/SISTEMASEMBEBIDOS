// Preserve Bluetooth memory before Arduino setup(); do not start the radio.
// Required when using ESP-IDF GAP directly without Arduino BLEDevice/btStart.
extern "C" bool btInUse(){return true;}
