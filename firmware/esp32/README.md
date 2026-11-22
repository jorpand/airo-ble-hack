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

Y para ver lo que dice la placa (la reinicia y saca el log de arranque):

```bash
mise run firmware-logs
```

## La trampa del puerto serie

**Todo lo que abra el REPL por el puerto serie para el puente en marcha.**

MicroPython ejecuta `main.py` una vez, al arrancar. Si alguien abre el REPL
mientras tanto (un `mpremote exec`, un `Ctrl+C`, un `mpremote fs cp` o el
reinicio de la máquina virtual al reconectar el USB), MicroPython **interrumpe
el programa**: la placa cae al REPL y el puente deja de servir.

Lo que confunde es que **la WiFi sigue puesta**: la placa contesta al ping y
parece viva, pero `http://<ip>:8080/salud` no responde. Lo que se ve es:

```
$ curl http://192.168.1.147:8080/salud     # no contesta
$ ping 192.168.1.147                        # responde: la placa esta viva
```

La solución es reiniciarla:

```bash
mise run firmware-deploy    # copia el firmware y reinicia
mise run firmware-logs     # reinicia y enseña el log de arranque
```

Por eso `firmware-deploy` **siempre reinicia al final**, y por eso los logs
se sacan con `--reset`.

## Los ficheros

| Fichero | Qué hace |
|---|---|
| `main.py` | arranque: WiFi + servidor HTTP + conexión BLE + refresco + LED |
| `puente.py` | las rutas del puente y el mantenimiento de la conexión |
| `ble_robot.py` | cliente BLE: escanear, conectar, descubrir, escribir, refrescar |
| `http_srv.py` | servidor HTTP mínimo sobre `asyncio.start_server` |
| `wifi.py` | conexión a la WiFi (las credenciales van en `wifi.json`) |
| `led.py` | el LED RGB: el color es el estado, el destello es la actividad |
| `spike.py` | el spike de la Fase 0, ejecutable a pelo |
| `mip.json` | metadatos de `mip` (sin dependencias externas) |

## Las rutas del puente

| Ruta | Qué hace |
|---|---|
| `GET /salud` | `{"ok": true, "servidor": "airo-bridge"}` |
| `GET /estado` | conexión, MAC, paquetes, último error, bytes guardados, color del LED |
| `GET /escanear` | lo que se ve por BLE ahora mismo (acepta `?ms=`) |
| `POST /escribir` | escribe el cuerpo (bytes crudos) en `FFF1` |
| `POST /conectar` | **busca el robot y se conecta** (tarda: el robot se duerme) |
| `POST /desconectar` | cierra la conexión BLE |

```bash
curl http://192.168.1.147:8080/salud
curl http://192.168.1.147:8080/estado
curl -X POST --data-binary @paquete.bin http://192.168.1.147:8080/escribir
```

### La placa no agarra al robot sola

Por defecto (`AUTO_CONECTAR = False` en `puente.py`) la placa **no se
conecta al robot por su cuenta**: se conecta cuando alguien se lo pide
(`POST /conectar`), que es lo que hace el botón "Conectar" de la web. El
robot se queda como está hasta entonces.

Con `AUTO_CONECTAR = True` la placa lo pilla en cuanto aparece y lo mantiene
(conveniente si el robot se duerme mucho, pero el enlace se queda abierto
solo). Se cambia en `puente.py` y se despliega con `mise run firmware-deploy`.

## El LED RGB

La placa lleva un LED RGB **direccionable** (un WS2812) que dice en qué estado
está el puente:

| Color | Cuándo |
|---|---|
| 🔴 rojo | no hay nada conectado |
| 🔵 azul | se está buscando al robot |
| 🟢 verde | el robot está conectado |

Y **parpadea del color que tenga** cuando hay tráfico de comandos.

Cosas que conviene saber:

- El WS2812 está en el **GPIO48** en las placas rev. 1.0 y en el **GPIO38** en
  las rev. 1.1. El chip no dice qué revisión es, así que `led.py` maneja **los
  dos pines**: el que no tenga el LED enganchado no hace nada.
- El LED se gestiona con el módulo `neopixel` de MicroPython (que va con
  `machine.bitstream`, o sea, con el RMT del ESP32: no es bit-bang). El driver
  ya reordena a GRB, así que los colores se dan como `(r, g, b)` de toda la
  vida.
- El **destello es un overlay**, no un cuarto color: el LED se apaga y se
  enciende un par de veces *con el color del estado*. Así se sigue viendo en
  qué estado está el enlace mientras hay tráfico.
- El puente **no recibe comandos del robot** (el robot no los manda), así que
  el parpadeo se provoca con la ruta `/escribir`: al leer el cuerpo de la
  petición y al mandarlo al robot.
- `GET /estado` también enseña el color (`"led": "rojo"`) y cuántos parpadeos
  ha habido (`"led_parpadeos": 12`), para ver el estado del puente desde el
  portátil sin poder mirar la placa: los parpadeos son los comandos que han
  llegado al puente.
- Si una placa no tuviera WS2812 (o el módulo `neopixel` no estuviera), el
  puente **sigue funcionando igual**: solo se pierde el LED.

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
| Dos escrituras a la vez | El robot contesta con error (7) y se pierde el enlace. Por eso las escrituras tambien van con candado |
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
- **Solo hay un escaneo a la vez.** Por eso las rutas HTTP no escanean a la
  vez que la de conectar: cada escaneo y cada conexión van con su candado.
- **Y solo hay una escritura a la vez.** La tarea de refresco (que reenvía el
  último paquete cada 50 ms) y las peticiones HTTP de `/escribir` van con un
  candado: si se solapan, el robot contesta con error y se cae el enlace.
- **El enlace BLE lo lleva la placa, no el cliente.** El cliente del portátil
  no debe soltar la conexión cuando algo falla (eso le arrancaría el robot de
  las manos a la placa en justo el momento en que lo acaba de pillar).

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
mise run firmware-spike      # o: python -m mpremote connect /dev/ttyUSB0 run firmware/esp32/spike.py
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
