// EXPERIMENTO 3 - TinyML (inferencia neuronal en el ESP32-CAM, SIN bibliotecas TFLM)
// Modelo 2 -> 24 (ReLU) -> 16 (ReLU) -> 4 (Softmax), entrenado en dataset sintetico.
// Entradas: distancia izq / 200, distancia der / 200. Clases: AVANZAR, IZQUIERDA,
// DERECHA, DETENER. Model.h contiene pesos aprendidos (incluido como ejemplo).
// Arduino IDE: placa AI Thinker ESP32-CAM. Sin Wi-Fi, con serial JSON a 115200.
#include <Arduino.h>
#include <math.h>
#include "model.h"

// Evita el error confuso de PESOS_1 / SESGOS_1 ausentes si se usa un model.h antiguo.
#ifndef EXP3_MODELO_PESOS_V1
#error "model.h INCOMPATIBLE: usa el model.h de este ZIP (pesos PESOS_1..3 y SESGOS_1..3)."
#endif
static_assert(sizeof(PESOS_1)/sizeof(PESOS_1[0]) == 48, "PESOS_1 incorrecto");
static_assert(sizeof(SESGOS_1)/sizeof(SESGOS_1[0]) == 24, "SESGOS_1 incorrecto");
static_assert(sizeof(PESOS_2)/sizeof(PESOS_2[0]) == 384, "PESOS_2 incorrecto");
static_assert(sizeof(SESGOS_2)/sizeof(SESGOS_2[0]) == 16, "SESGOS_2 incorrecto");
static_assert(sizeof(PESOS_3)/sizeof(PESOS_3[0]) == 64, "PESOS_3 incorrecto");
static_assert(sizeof(SESGOS_3)/sizeof(SESGOS_3[0]) == 4, "SESGOS_3 incorrecto");

constexpr uint8_t TRIG_I = 13, ECHO_I = 14, TRIG_D = 15, ECHO_D = 2;
constexpr uint8_t LED_I = 12, LED_D = 4, LED_ROJO_INTEGRADO = 33;
constexpr float UMBRAL_CM = 20.0f, SEGURIDAD_CM = 6.0f, CONFIANZA_MIN = 0.60f;
const char* CLASES[4] = {"AVANZAR", "IZQUIERDA", "DERECHA", "DETENER"};
uint32_t secuencia = 0;

float distanciaCm(uint8_t trig, uint8_t echo) {
  digitalWrite(trig, LOW); delayMicroseconds(3);
  digitalWrite(trig, HIGH); delayMicroseconds(10);
  digitalWrite(trig, LOW);
  unsigned long us = pulseIn(echo, HIGH, 25000UL);
  if (us == 0) return -1.0f;
  float cm = us * 0.0343f / 2.0f;
  return (cm >= 2.0f && cm <= 400.0f) ? cm : -1.0f;
}

void luces(bool obstI, bool obstD) {
  digitalWrite(LED_I, obstI ? HIGH : LOW);
  digitalWrite(LED_D, obstD ? HIGH : LOW);             // LED externo der + flash blanco
  digitalWrite(LED_ROJO_INTEGRADO, obstI ? LOW : HIGH); // rojo integrado: activo LOW
}

// Evaluacion de la misma red aprendida en Colab: Dense + ReLU + Softmax.
// No se implementan reglas aqui: son pesos numericos entrenados y exportados en model.h.
void inferir(float distanciaI, float distanciaD, float prob[4]) {
  float entrada[2] = {
    constrain(distanciaI, 0.0f, 200.0f) / 200.0f,
    constrain(distanciaD, 0.0f, 200.0f) / 200.0f
  };
  float oculta1[24];
  float oculta2[16];
  float logits[4];

  for (int j=0; j<24; ++j) {
    float suma = SESGOS_1[j];
    for (int i=0; i<2; ++i) suma += entrada[i] * PESOS_1[i*24+j];
    oculta1[j] = fmaxf(suma, 0.0f);
  }
  for (int j=0; j<16; ++j) {
    float suma = SESGOS_2[j];
    for (int i=0; i<24; ++i) suma += oculta1[i] * PESOS_2[i*16+j];
    oculta2[j] = fmaxf(suma, 0.0f);
  }
  for (int j=0; j<4; ++j) {
    float suma = SESGOS_3[j];
    for (int i=0; i<16; ++i) suma += oculta2[i] * PESOS_3[i*4+j];
    logits[j] = suma;
  }
  float maximo = logits[0];
  for (int j=1; j<4; ++j) if (logits[j] > maximo) maximo = logits[j];
  float total = 0.0f;
  for (int j=0; j<4; ++j) {
    prob[j] = expf(logits[j] - maximo);
    total += prob[j];
  }
  if (total > 0.0f) for (int j=0; j<4; ++j) prob[j] /= total;
}

void enviar(float izq, float der, bool obstI, bool obstD,
            const char* decisionModelo, const char* decisionFinal, float confianza,
            uint32_t inferenciaUs) {
  Serial.print("{\"izquierda_cm\":"); Serial.print(izq, 2);
  Serial.print(",\"derecha_cm\":"); Serial.print(der, 2);
  Serial.print(",\"obstaculo_izq\":"); Serial.print(obstI ? "true" : "false");
  Serial.print(",\"obstaculo_der\":"); Serial.print(obstD ? "true" : "false");
  Serial.print(",\"led_rojo_integrado\":"); Serial.print(obstI ? "true" : "false");
  Serial.print(",\"led_blanco_integrado\":"); Serial.print(obstD ? "true" : "false");
  Serial.print(",\"decision_modelo\":\""); Serial.print(decisionModelo);
  Serial.print("\",\"decision\":\""); Serial.print(decisionFinal);
  Serial.print("\",\"confianza\":");
  if (confianza < 0.0f) Serial.print("null"); else Serial.print(confianza, 4);
  Serial.print(",\"inferencia_us\":"); Serial.print(inferenciaUs);
  Serial.print(",\"modo\":\"TINYML\",\"secuencia\":"); Serial.print(++secuencia);
  Serial.println("}");
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
  Serial.println("# EXP3 TinyML listo: datos JSON continuos 115200 (sin tflm_esp32)");
}

void loop() {
  float izquierda = distanciaCm(TRIG_I, ECHO_I);
  delay(70);
  float derecha = distanciaCm(TRIG_D, ECHO_D);
  bool obstI = izquierda > 0 && izquierda < UMBRAL_CM;
  bool obstD = derecha > 0 && derecha < UMBRAL_CM;
  luces(obstI, obstD);

  if (izquierda < 0.0f || derecha < 0.0f) {
    enviar(izquierda,derecha,obstI,obstD,"SIN_LECTURA","DETENER",-1.0f,0);
    delay(280);
    return;
  }
  float p[4];
  uint32_t inicio = micros();
  inferir(izquierda, derecha, p);
  uint32_t duracion = micros() - inicio;
  int mejor = 0;
  for (int i=1;i<4;++i) if (p[i] > p[mejor]) mejor=i;
  const char* modelo = CLASES[mejor];
  const char* decision = modelo;
  // Capa de seguridad: ante peligro, baja confianza o avance contradictorio, DETENER.
  if (izquierda < SEGURIDAD_CM || derecha < SEGURIDAD_CM ||
      p[mejor] < CONFIANZA_MIN ||
      (mejor == 0 && (obstI || obstD))) decision = "DETENER";
  enviar(izquierda, derecha, obstI, obstD, modelo, decision, p[mejor], duracion);
  delay(280);
}
