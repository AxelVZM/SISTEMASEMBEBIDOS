// EXPERIMENTO 3 - Prueba de 2 HC-SR04 y LEDs con telemetria USB continua
// ESP32-CAM AI Thinker + ESP32-CAM-MB / 115200 baudios / Sin Wi-Fi
// Misma conexion: Izq TRIG13 ECHO14, Der TRIG15 ECHO2 (ECHO con divisor 1k/2k)
// LED externo izq IO12; LED externo der IO4. Flash blanco IO4, rojo integrado IO33.
#include <Arduino.h>

constexpr uint8_t TRIG_I = 13, ECHO_I = 14, TRIG_D = 15, ECHO_D = 2;
constexpr uint8_t LED_I = 12, LED_D = 4, LED_ROJO_INTEGRADO = 33;
constexpr float UMBRAL_CM = 20.0f;
uint32_t secuencia = 0;

float distanciaCm(uint8_t trig, uint8_t echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(3);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  unsigned long duracion = pulseIn(echo, HIGH, 25000UL);
  if (duracion == 0) return -1.0f;
  float distancia = duracion * 0.0343f / 2.0f;
  return (distancia >= 2.0f && distancia <= 400.0f) ? distancia : -1.0f;
}

void luces(bool izquierdo, bool derecho) {
  digitalWrite(LED_I, izquierdo ? HIGH : LOW);
  digitalWrite(LED_D, derecho ? HIGH : LOW); // tambien flash blanco integrado
  digitalWrite(LED_ROJO_INTEGRADO, izquierdo ? LOW : HIGH); // LED rojo ACTIVO en bajo
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_I, OUTPUT); pinMode(ECHO_I, INPUT);
  pinMode(TRIG_D, OUTPUT); pinMode(ECHO_D, INPUT);
  digitalWrite(TRIG_I, LOW); digitalWrite(TRIG_D, LOW);
  pinMode(LED_I, OUTPUT); pinMode(LED_D, OUTPUT);
  pinMode(LED_ROJO_INTEGRADO, OUTPUT);
  luces(false, false);
  delay(350);
  Serial.println("# EXP3 listo: prueba de sensores, JSON continuo 115200");
}

void loop() {
  float izquierda = distanciaCm(TRIG_I, ECHO_I);
  delay(70);  // evita interferencias entre ambos ultrasonidos
  float derecha = distanciaCm(TRIG_D, ECHO_D);
  bool obstI = izquierda > 0 && izquierda < UMBRAL_CM;
  bool obstD = derecha > 0 && derecha < UMBRAL_CM;
  luces(obstI, obstD);

  const char *decision = "AVANZAR";
  if (izquierda < 0 || derecha < 0) decision = "DETENER";
  else if (obstI && obstD) decision = "DETENER";
  else if (obstI) decision = "DERECHA";
  else if (obstD) decision = "IZQUIERDA";

  Serial.print("{\"izquierda_cm\":"); Serial.print(izquierda, 2);
  Serial.print(",\"derecha_cm\":"); Serial.print(derecha, 2);
  Serial.print(",\"obstaculo_izq\":"); Serial.print(obstI ? "true" : "false");
  Serial.print(",\"obstaculo_der\":"); Serial.print(obstD ? "true" : "false");
  Serial.print(",\"led_rojo_integrado\":"); Serial.print(obstI ? "true" : "false");
  Serial.print(",\"led_blanco_integrado\":"); Serial.print(obstD ? "true" : "false");
  Serial.print(",\"decision\":\""); Serial.print(decision);
  Serial.print("\",\"confianza\":null,\"inferencia_us\":0,\"modo\":\"REGLAS_PRUEBA\",\"secuencia\":");
  Serial.print(++secuencia);
  Serial.println("}");
  delay(280);
}
