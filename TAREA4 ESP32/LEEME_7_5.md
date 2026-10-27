# Órbita ESP32 — actualización 7.5

Sistema embebido para ESP32 clásico: captura, clasificación y registro ejecutados en la placa. El navegador presenta resultados y envía órdenes; no realiza la búsqueda LAN ni los nuevos decodificadores.

| Función | Implementación y alcance |
|---|---|
| Wi-Fi por defecto | Inicia al alimentar o reiniciar. Captura pasiva de 2,4 GHz, canales 1–11. |
| BLE manual | Solo inicia con Activar detección BLE. Desactivar espera la parada y recupera Wi-Fi. Cambiar de apartado no activa ni apaga la radio. |
| Tipo de equipo | WPS/P2P, Appearance BLE, formatos reconocidos, servicios LAN y palabras en nombres. Diferencia declarado, indicio, rol, conflicto y desconocido. No todos los equipos anuncian evidencia suficiente. |
| Marca | Normalización de fabricantes anunciados, incluidos Samsung, Honor, Apple, Xiaomi, Huawei, Lenovo y otros. IEEE sigue separado: titular de bloque, no marca comercial garantizada. |
| Modelo | Conserva lo anunciado. Catálogo exacto de códigos SM-S911B y SM-S911B/DS → Galaxy S23; BVL-N49 → Honor Magic6 Pro; FNE-NX9 → HONOR 70. Solo se aplica a campos de modelo/código, nunca SSID o nombre arbitrario. No se extiende por parecido a otros códigos. |
| BLE ampliado | Nueve IDs Apple/Beats existentes; MiBeacon pasa de 3 a 13 IDs (12 nombres de modelo, CGG1 tiene dos IDs). Nuevo reconocimiento Ruuvi RAWv2 como telemetría de sensor, sin atribuir modelo exacto. |
| LAN | Diez consultas mDNS: device-info, airplay, googlecast, ipp, ipps, printer, pdl-datastream, raop, smb, http. Añade SSDP y lectura de descripción UPnP de la subred local. |
| Registro autónomo | Wi-Fi, BLE y ahora la búsqueda LAN se guardan en el registro rotativo LittleFS. Una búsqueda iniciada continúa sin navegador. |
| Interfaz | Tipo y evidencia visibles en BLE/LAN; marca anunciada y modelo de catálogo visibles en Wi-Fi; modelo/código LAN y exportación CSV. |

## Límites reales
No hay identificación universal exacta ni porcentaje de acierto medido con hardware. Los anuncios no se autentican y pueden ser falsos. Conectarse a una red no obliga a celulares, cámaras o PCs a publicar su modelo. No se enlazan direcciones privadas entre sesiones ni entre Wi-Fi/BLE. Las filas LAN son servicios/descripciones, no un conteo de equipos físicos únicos.

El descubrimiento puede reconocer al router mediante su descripción UPnP, pero **no consulta su lista privada de clientes**: para implementar ese inventario falta conocer marca, modelo y API autorizada del router. No existe una interfaz común que entregue todos los modelos.

La captura y el registro funcionan con alimentación USB estable, sin PC. La visualización remota EC2 conserva el transporte existente mediante navegador USB o puente Python activo. La opción HTTPS/Lambda existente sigue siendo separada y envía su resumen Wi-Fi; esta versión no convierte esa opción en publicación directa de BLE/LAN a EC2.

No se instaló un modelo de aprendizaje automático nuevo: estas mejoras usan protocolos, identificadores documentados y reglas con evidencia. El catálogo experimental de huellas sigue vacío porque no hay validación suficiente para identificación comercial fiable.

Consulta ACTUALIZAR_7_5.md para instalar y PRUEBAS_7_5.md para los resultados de verificación.
