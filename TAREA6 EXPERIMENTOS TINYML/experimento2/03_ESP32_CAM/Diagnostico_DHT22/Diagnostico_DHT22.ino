#include <Arduino.h>
#include <DHT.h>
#define PIN_DHT 13
#define LED_AZUL 14
#define LED_VERDE 15
#define LED_ROJO 2
DHT dht(PIN_DHT,DHT22);
void setup(){Serial.begin(115200);dht.begin();pinMode(LED_AZUL,OUTPUT);pinMode(LED_VERDE,OUTPUT);pinMode(LED_ROJO,OUTPUT);Serial.println("READY,DHT22_DIAGNOSTICO");}
void loop(){float t=dht.readTemperature(),h=dht.readHumidity();digitalWrite(LED_AZUL,LOW);digitalWrite(LED_VERDE,LOW);digitalWrite(LED_ROJO,LOW);if(isnan(t)||isnan(h)){Serial.println("ERROR,DHT22_SIN_LECTURA");}else{int pin=t<12?LED_AZUL:(t<21?LED_VERDE:LED_ROJO);digitalWrite(pin,HIGH);Serial.printf("DHT22,%.2f,%.2f\n",t,h);}delay(2500);}
