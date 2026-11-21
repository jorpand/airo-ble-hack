# Firmware del puente BLE (ESP32-S3)

Este directorio es el MicroPython que corre en el ESP32-S3: el **puente** que
habla con el robot y al que se le pueden mandar bytes por HTTP.

La idea del proyecto (versión corta): el ESP32 **no sabe nada del protocolo
AIRO**. Solo sabe escribir bytes en la characteristic `FFF1`. El paquete de 20
bytes lo sigue construyendo `airo_ble/protocol.py` en el portátil, así que el
protocolo no se duplica ni se toca.

El plan entero está en [`docs/plan-esp32.md`](../../docs/plan-esp32.md).

## La placa

- **ESP32-S3-DevKitC-1 N16R8**: 16 MB de flash y **8 MB de PSRAM octal**.
- Ojo con la PSRAM: la build normal de MicroPython solo auto-detecta la
  PSRAM *quad*. Para la octal hace falta la variante `SPIRAM_OCT`.
- Dos USB: el nativo (CDC) y el del puente UART (CH343). Para flashear, usa el
  **UART** (auto-reset); con el nativo hay que mantener pulsado BOOT al resetear.

## Flashear (la primera vez)

```bash
# el firmware: 1,7 MB, con la PSRAM octal
mkdir -p ~/.cache/airo-firmware
curl -L -o ~/.cache/airo-firmware/ESP32_GENERIC_S3-SPIRAM_OCT-v1.29.0.bin \
  https://micropython.org/resources/firmware/ESP32_GENERIC_S3-SPIRAM_OCT-20260824-v1.29.0.bin

# y al chip (cambia /dev/ttyUSB0 si tu puerto es otro)
python -m esptool --chip esp32s3 --port /dev/ttyUSB0 write_flash 0x0 \
  ~/.cache/airo-firmware/ESP32_GENERIC_S3-SPIRAM_OCT-v1.29.0.bin
```

La versión es la **v1.29.0**, la última estable. Ojo: la build normal solo
auto-detecta la PSRAM *quad*, y esta placa (N16R8) lleva PSRAM **octal**, así que
hace falta la variante `SPIRAM_OCT`.

Antes de flashear una versión nueva, hay que **borrar la flash** (si no, la
placa arranca con el fichero viejo):

```bash
python -m esptool --chip esp32s3 --port /dev/ttyUSB0 erase_flash
```

En el repo hay tareas de mise para todo esto: `mise run firmware-flash`,
`mise run firmware-run` y `mise run firmware-wifi`.

## Los ficheros

| Fichero | Qué hace |
|---|---|
| `main.py` | arranque: WiFi + servidor HTTP + conexión BLE + refresco |
| `puente.py` | las rutas del puente y el mantenimiento de la conexión |
| `ble_robot.py` | cliente BLE: escanear, conectar, descubrir, escribir, refrescar |
| `http_srv.py` | servidor HTTP mínimo sobre `asyncio.start_server` |
| `wifi.py` | conexión a la WiFi (las credenciales van en `wifi.json`) |
| `spike.py` | el spike de la Fase 0, ejecutable a pelo |
| `mip.json` | metadatos de `mip` (sin dependencias externas) |

## Las rutas del puente

| Ruta | Qué hace |
|---|---|
| `GET /salud` | `{"ok": true, "servidor": "airo-bridge"}` |
| `GET /estado` | conexión, MAC, paquetes, último error, bytes guardados |
| `GET /escanear` | lo que se ve por BLE ahora mismo |
| `POST /escribir` | escribe el cuerpo (bytes crudos) en `FFF1` |
| `POST /conectar` | espera a que la tarea de fondo pille al robot |
| `POST /desconectar` | cierra la conexión BLE |

```bash
curl http://192.168.1.147:8080/salud
curl http://192.168.1.147:8080/estado
curl -X POST --data-binary @paquete.bin http://192.168.1.147:8080/escribir
```

## La WiFi

Las credenciales **no están en el repo**: van en `firmware/esp32/wifi.json`
(que está en el `.gitignore`). Copia el ejemplo y pon las tuyas:

```bash
cp firmware/esp32/wifi.example.json firmware/esp32/wifi.json
$EDITOR firmware/esp32/wifi.json
mise run firmware-wifi     # copia el fichero a la placa y se conecta
```

La placa se llama `airo-bridge`: el **propio port del ESP32** trae el responder de
mDNS, así que con `network.hostname("airo-bridge")` (que `wifi.py` pone **antes**
de activar la interfaz, que es cuando el port inicializa el responder) se puede
llamar a `airo-bridge.local:8080`.

Ojo: no hay que instalar el paquete `mdns` de micropython-lib (además, no está
en el índice de `mip`): quiere el puerto 5353 y el del port ya lo tiene. Y que
`airo-bridge.local` funcione depende de que la red **no filtre el multicast**:
en la red donde se ha probado esto, el tráfico mDNS entero no pasaba, así que
la **IP es el camino que funciona**.

## La API de `bluetooth` en la práctica

Estas son las rarezas que hay que tener en el bolsillo, todas comprobadas
contra la placa (no salen en la documentación):

| Lo que parece | Lo que hay que hacer |
|---|---|
| `bluetooth.UUID16(0xFFF0)` | No existe: es `bluetooth.UUID(0xFFF0)` |
| `str(uuid)` → `"0000fff0-…"` | Es `"UUID(0xfff0)"`. Mejor comparar con `bytes(uuid)` |
| `bluetooth._IRQ_SCAN_RESULT` | No existen: los eventos van numerados (ver `ble_robot.py`) |
| Conexión hecha → IRQ 1 | En el port NimBLE, `gap_connect` avisa con el **7** |
| `gap_scan(0)` para parar | No: `gap_scan(0)` deja el escaneo para siempre. Se para con `gap_scan(None)` |
| Descubrir `UUID(0xFFF0)` | El robot lo registra con UUID de 128 bits: hay que descubrir **todo** y filtrar |
| Dos escaneos a la vez | NimBLE contesta `EALREADY`: solo se admite uno. Por eso el cliente lleva un candado |
| `print(..., flush=True)` | No existe en MicroPython |

Y el layout de los datos de cada evento (en 1.26 y en 1.29 es el mismo):

```
SCAN_RESULT            (addr_type, addr, adv_type, rssi, adv_data)
GATTC_SERVICE_RESULT   (conn_handle, inicio, fin, uuid)
GATTC_CHARACTERISTIC   (conn_handle, fin, handle, props, uuid)
GATTC_WRITE_DONE       (conn_handle, value_handle, status)
```

## Notas de diseño

- Se usa la API **de bajo nivel** de MicroPython (`BLE.gattc_*`), la de 1.24 en
  adelante; la vieja `bluetooth.Scanner` ya no existe.
- Los IRQ se atienden en la tarea del BLE: el manejador solo guarda estado, no
  duerme ni imprime. Las esperas se hacen fuera, con `time.ticks_ms`.
- Los UUID se comparan por su parte corta de 16 bits, porque el base UUID del
  robot puede cambiar (`0000fff0-...-00805f9b34fb` o `0000fff0-...-000000000000`).
- Los 20 bytes del paquete caben justo en el MTU mínimo (23 bytes ATT → 20 de
  payload), así que no hace falta trocear ni negociar MTU.
- **La placa reenvía sola el último paquete cada 50 ms.** El firmware del robot
  devuelve los brazos al reposo si deja de recibir paquetes, así que el paquete
  tiene que ir sin parar; y hacerlo desde el portátil serían 20 peticiones HTTP
  por segundo. El portátil solo manda el paquete cuando **cambia**.
- **Solo hay un escaneo a la vez.** Por eso las rutas HTTP no escanean: esperan a
  la tarea de fondo (`mantener_conexion`), que es la que busca al robot.

## Hablar con la placa desde el portátil

El cliente de Python (`airo_ble.bridge`) habla con el puente y se comporta
igual que el cliente BLE:

```bash
export AIRO_BRIDGE_URL=http://192.168.1.147:8080
python -m airo_ble.console      # o la API web, o el servidor de Scratch
```

Sin esa variable, todo sigue yendo por BLE directo.

## Ejecutar el spike (a pelo, sin el servidor HTTP)

```bash
python -m mpremote connect /dev/ttyUSB0 run firmware/esp32/spike.py
```

Lo que hace, paso a paso:

1. Escanea 5 s y lista lo que ve.
2. Busca al robot por su nombre (`AIRo`, con la "o" en minúscula).
3. Conecta y descubre `FFF0` (servicio) y `FFF1` (characteristic).
4. Escribe el paquete de **parar** (con respuesta: `gattc_write(mode=1)`).
5. Escribe el de **avanzar despacio**, espera 1 s y vuelve a parar.

## Lo que NO está aquí todavía

- OTA: para actualizar hay que volver a copiar los ficheros con `mpremote`.
- Token en las peticiones: si la red no es de fiar, cualquiera que llegue al
  puerto 8080 puede mover el robot.
