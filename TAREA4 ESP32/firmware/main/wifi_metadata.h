#pragma once
#include <stddef.h>
#include <stdint.h>
typedef struct {
    char manufacturer[65],model_name[33],model_number[33],device_name[33],ssid[33],primary_device_type[17];
    /* Up to 8 distinct vendor-specific IE OUIs (+type) as "OOOOOOTT,..." for client fingerprinting. */
    char vendor_ies[72];
} wifi_metadata_t;
/* Parse WPS attributes, Wi-Fi Direct (P2P) Device Info, AP SSID and vendor IE OUIs. No UUID, serial or user payload. */
void wifi_metadata(const uint8_t *frame,size_t length,wifi_metadata_t *out);
