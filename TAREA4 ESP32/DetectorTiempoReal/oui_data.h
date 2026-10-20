#pragma once
#include <Arduino.h>
#include "ieee_registry.h"
// Drop-in replacement for the previous firmware interface; preserves raw organization names.
inline String manufacturer(const uint8_t *mac){
 const auto result=ieee_mac::lookup(mac);
 switch(result.status){
  case ieee_mac::Status::matched:return String(result.organization);
  case ieee_mac::Status::local:return String("No inferible: MAC local");
  case ieee_mac::Status::group:return String("Direccion de grupo; no identifica fabricante");
  case ieee_mac::Status::invalid:return String("MAC invalida");
  default:return String("Sin asignacion en la copia IEEE MA-L/MA-M/MA-S");
 }
}
// Optional provenance display, independent of WPS/model classification.
inline String manufacturerEvidence(const uint8_t *mac){
 const auto result=ieee_mac::lookup(mac);if(result.status!=ieee_mac::Status::matched)return manufacturer(mac);
 char prefix[10],description[64];ieee_mac::assignmentText(result,prefix,sizeof(prefix));
 snprintf(description,sizeof(description),"IEEE %s /%u; prefijo %s",result.registry,result.bits,prefix);
 return String(description);
}
