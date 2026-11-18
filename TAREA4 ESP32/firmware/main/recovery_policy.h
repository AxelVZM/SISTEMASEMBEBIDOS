#pragma once
#include <stdbool.h>
#define DETECTOR_RECOVERY_LIMIT 3U
static inline bool detector_recovery_allowed(unsigned attempts,unsigned consecutive_failures){
    return attempts<DETECTOR_RECOVERY_LIMIT && consecutive_failures<DETECTOR_RECOVERY_LIMIT;
}
