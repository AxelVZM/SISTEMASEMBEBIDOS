#include <Arduino.h>
#include <DHT.h>
#define DHT_PIN 13
#define LED_AZUL 14
#define LED_VERDE 15
#define LED_ROJO 2
DHT dht(DHT_PIN,DHT22);
unsigned long ciclos=0;
void setup() {
  Serial.begin(115200);
  delay(1200);
  Serial.println();
  Serial.println("BOOT,ESP32CAM_RESCATE_V1,115200");
  Serial.printf("RESET_REASON,%d\n", (int)esp_reset_reason());
  pinMode(LED_AZUL, OUTPUT);pinMode(LED_VERDE, OUTPUT);pinMode(LED_ROJO, OUTPUT);
  digitalWrite(LED_AZUL,LOW);digitalWrite(LED_VERDE,LOW);digitalWrite(LED_ROJO,LOW);
  dht.begin();
  Serial.println("READY,DHT22,GPIO13,LEDS14_15_2");
}
void loop() {
  ++ciclos;
  float t=dht.readTemperature(),h=dht.readHumidity();
  digitalWrite(LED_AZUL,LOW);digitalWrite(LED_VERDE,LOW);digitalWrite(LED_ROJO,LOW);
  if (isnan(t)||isnan(h)||t< -40||t>80||h<0||h>100) {
    Serial.printf("ERROR,DHT22_SIN_LECTURA,%lu\n",ciclos);
  } else {
    int pin=t<12?LED_AZUL:(t<21?LED_VERDE:LED_ROJO);
    digitalWrite(pin,HIGH);
    Serial.printf("DHT22,%.2f,%.2f\n",t,h);
  }
  Serial.flush();
  delay(2500);
}
