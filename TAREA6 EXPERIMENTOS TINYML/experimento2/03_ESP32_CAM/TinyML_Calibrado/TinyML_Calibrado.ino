#include <Arduino.h>
#include <DHT.h>
#include <ArduTFLite.h>
#include "model.h"

#define PIN_DHT 13
#define LED_AZUL 14
#define LED_VERDE 15
#define LED_ROJO 2
DHT dht(PIN_DHT, DHT22);
constexpr int ARENA_BYTES = 48 * 1024;
alignas(16) byte tensorArena[ARENA_BYTES];
bool listo = false;
const char* nombres[3] = {"FRIO", "TEMPLADO", "CALIENTE"};

// Umbrales de referencia acordados (deben coincidir con etiquetas CSV).
constexpr float LIMITE_FRIO = 12.0f;
constexpr float LIMITE_CALIENTE = 21.0f;
// En la primera validacion, el LED refleja la temperatura medida.
// La prediccion TinyML se calcula siempre y se reporta por separado.
// Cambiar a false SOLO cuando el modelo reentrenado supere las pruebas.
constexpr bool MODO_CALIBRACION = true;

void apagar() {
  digitalWrite(LED_AZUL, LOW);
  digitalWrite(LED_VERDE, LOW);
  digitalWrite(LED_ROJO, LOW);
}
int claseReferencia(float t) {
  if (t < LIMITE_FRIO) return 0;
  if (t < LIMITE_CALIENTE) return 1;
  return 2;
}
void leds(int clase) {
  apagar();
  if (clase == 0) digitalWrite(LED_AZUL, HIGH);
  if (clase == 1) digitalWrite(LED_VERDE, HIGH);
  if (clase == 2) digitalWrite(LED_ROJO, HIGH);
}
void setup() {
  Serial.begin(115200);
  delay(1200);
  pinMode(LED_AZUL, OUTPUT);
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);
  apagar();
  dht.begin();
  listo = modelInit(modelo_temperatura, tensorArena, ARENA_BYTES);
  Serial.println("READY,CALIBRACION_DHT22,115200");
  if (!listo) Serial.println("ERROR,MODELO_NO_INICIALIZADO");
  Serial.println("CSV,TEMP_C,HUM_PCT,CLASE_RED,CLASE_REFERENCIA,CLASE_LED,P_FRIO,P_TEMPLADO,P_CALIENTE,LATENCIA_US");
}
void loop() {
  const float t = dht.readTemperature();
  const float h = dht.readHumidity();
  if (isnan(t) || isnan(h) || t < -40 || t > 80 || h < 0 || h > 100) {
    apagar();
    Serial.println("ERROR,DHT22_SIN_LECTURA");
    delay(2500);
    return;
  }
  int referencia = claseReferencia(t);
  int red = -1;
  float p[3] = {NAN, NAN, NAN};
  unsigned long latencia = 0;
  if (listo) {
    float tn = (t - media_entrada[0]) / desv_entrada[0];
    float hn = (h - media_entrada[1]) / desv_entrada[1];
    if (modelSetInput(tn, 0) && modelSetInput(hn, 1)) {
      unsigned long inicio = micros();
      if (modelRunInference()) {
        latencia = micros() - inicio;
        for (int k=0;k<3;k++) p[k] = modelGetOutput(k);
        if (isfinite(p[0]) && isfinite(p[1]) && isfinite(p[2])) {
          red = 0;
          for (int k=1;k<3;k++) if (p[k]>p[red]) red=k;
        }
      }
    }
  }
  int elegido = (MODO_CALIBRACION || red < 0) ? referencia : red;
  leds(elegido);
  Serial.printf("CAL,%.2f,%.2f,%s,%s,%s,%.5f,%.5f,%.5f,%lu\n",
    t,h,red<0?"SIN_MODELO":nombres[red],nombres[referencia],
    nombres[elegido],p[0],p[1],p[2],latencia);
  if (red >= 0 && red != referencia) {
    Serial.println("AVISO,MODELO_DISCREPA_DE_TEMPERATURA");
  }
  delay(2500);
}
