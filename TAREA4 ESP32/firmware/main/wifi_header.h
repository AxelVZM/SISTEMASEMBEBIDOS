#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
typedef struct {uint8_t mac[6]; int role; const char *frame;} wifi_identity_t;
bool wifi_identity(const uint8_t *p,size_t len,wifi_identity_t *out);
