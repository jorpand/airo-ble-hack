# Plan de trabajo: puente BLE con un ESP32-S3 (MicroPython)

Fecha: 2026-11-21 · Estado: plan cerrado, **sin implementar** (a la espera de "dale")

## 0. Decisiones ya tomadas

| Decisión | Valor |
|---|---|
| Arquitectura | **Puente BLE**: el ESP32 solo habla con el robot; la API sigue en el portátil |
| Stack del firmware | **MicroPython** (no ESP-IDF/C) |
| Placa | **ESP32-S3-DevKitC-1 N16R8** (16 MB flash, 8 MB PSRAM octal) |
| Alcance de este plan | Solo el plan. No se empieza a implementar hasta que se diga |

## 1. Veredicto

**Sí se puede, y con el alcance "puente" sale mucho más barato** que portar la API
entera al chip: de las ~90-150 h de la variante autónoma a **~15-25 h**.

La clave de diseño es una decisión de responsabilidades:

> **El ESP32 no sabe nada del protocolo AIRO.** Solo sabe hacer una cosa: *escribir
> N bytes en la characteristic `FFF1` del robot*. El paquete de 20 bytes lo sigue
> construyendo `airo_ble/protocol.py` en el portátil, y las rampas de brazos, las
> colas y los programas siguen igual que ahora.

Consecuencias:

- `protocol.py` **no se toca ni se duplica** → la regla de "una sola fuente de la
  verdad" se mantiene intacta.
- El firmware no necesita el núcleo compartido ni la web: son ~250 líneas de
  MicroPython y **cero dependencias externas**.
- El ESP32 **mantiene viva la conexión BLE** (el módulo HM-10 del robot se duerme;
  hoy el cliente de Python tiene que reconectar solo). Con el puente, la API del
  portátil va siempre por HTTP y sin ritmos de reconexión.
- La web y la API del portátil **no cambian de comportamiento**: mismo contrato
  JSON, mismos endpoints.

Lo que **no** entra en esta fase (queda como fase posterior, §7): servir la web
desde el chip, meter las rampas en el firmware, o portar FastAPI a MicroPython.

## 2. La cadena, antes y después

Hoy:

```
   API FastAPI (portátil)  ──bleak──BLE──►  robot AIRO (HM-10)
   React (web)            ──HTTP──►  API
```

Con el puente:

```
   React (web)  ──HTTP──►  API FastAPI (portátil)  ──HTTP (WiFi)──►  ESP32-S3
                                                                  │
                                                          BLE (FFF1)
                                                                  ▼
                                                            robot AIRO
```

El paquete de 20 bytes viaja como **bytes crudos** por HTTP, no como JSON de
comandos. El ESP32 los escribe tal cual en `FFF1`.

## 3. Reparto de responsabilidades

| Cosa | Dónde vive | Cambia |
|---|---|---|
| Paquete de 20 bytes | `airo_ble/protocol.py` | No |
| Rampas de brazos, cola, kata, parada | `airo_ble/session.py` | No |
| Reglas de programa (bloques, niveles, duración) | `airo_ble/api/service.py` | No |
| API REST + WebSocket | `airo_ble/api/` (portátil) | No |
| Interfaz React | `web/` | No |
| **Escanear, conectar, descubrir `FFF0`/`FFF1`** | **ESP32** (MicroPython) | Nuevo |
| **Escribir los bytes en `FFF1`** | **ESP32** (MicroPython) | Nuevo |
| **Mantener la conexión BLE viva** | **ESP32** (MicroPython) | Nuevo |
| **Servidor HTTP del puente** | **ESP32** (MicroPython) | Nuevo |
| **Cliente HTTP hacia el puente** | `airo_ble/bridge.py` (nuevo) | Nuevo |
| bleak (BLE directo en el portátil) | `airo_ble/client.py` | Sigue, pero pasa a ser opcional |

## 4. El contrato del puente (API del ESP32)

MicroPython puro, sin frameworks. JSON pequeño, `application/octet-stream` para los
paquetes.

| Endpoint | Qué hace |
|---|---|
| `GET /salud` | `{"ok": true, "servidor": "airo-bridge"}`: para comprobar que el puente vive |
| `GET /estado` | `{"conectado": bool, "mac": str, "nombre": str, "rssi": int, "paquetes": int, "ultimo_error": str\|null, "servicio": [int, int], "characteristic": int, "bytes_guardados": int, "fallos": int}` |
| `POST /escribir` | Cuerpo: **bytes crudos** (los 20 del paquete). Escribe en `FFF1`. Respuesta `{"ok": true, "bytes": 20}` o 409 con `{"error": "..."}` |
| `POST /conectar` | Espera a que la tarea de fondo pille al robot. `{"ok": true, "mac": "..."}` o 409 con `{"error": "no se encuentra el robot"}` |
| `POST /desconectar` | Cierra la conexión BLE |
| `GET /escanear` | `{"dispositivos": [{"mac": str, "nombre": str, "rssi": int}]}` (para depurar) |

Detalles de diseño:

- **Write con respuesta** (`gattc_write(mode=1)`) por defecto, que es lo que hace
  la app oficial, con **timeout**: el HM-10 duerme y deja la escritura colgada.
- El ESP32 responde rápido: si no está conectado, `POST /escribir` devuelve 409
  con un mensaje claro, en vez de colgarse.
- El estado se actualiza con la conexión (IRQ 1/2 **y** 7/8) y se consulta bajo
  demanda; no hace falta WebSocket en el puente (la API del portátil ya tiene el
  suyo para la web).
- **La placa reenvía sola el último paquete cada 50 ms.** El firmware del robot
  devuelve los brazos al reposo si deja de recibir paquetes, y mandar 20 peticiones
  HTTP por segundo sería mucho tráfico para 20 bytes. Así que el portátil solo
  manda el paquete cuando **cambia**, y la placa se encarga del refresco.
- **Solo hay un escaneo a la vez.** NimBLE contesta `EALREADY` si se pisan dos
  escaneos, así que el cliente BLE lleva un candado y las rutas HTTP que
  escanean van con otro (`lock_conexion`): la de `/conectar` (que busca, conecta
  y descubre) no se solapa con la de `/escanear`.

## 5. El lado Python

### 5.1 `airo_ble/cliente.py` y `airo_ble/bridge.py`

Los dos clientes del robot (`AiroRobot`, que habla bleak, y `BridgeRobot`, que
habla HTTP con la placa) heredan de `airo_ble.cliente.ClienteRobot`. La clase
base tiene **lo que no cambia** (los atajos, el ciclo de vida, las consultas) y
los hijos implementan **lo que cambia** (cómo se habla con el robot).

```python
# en ClienteRobot (la base)
async def drive(self, *, left: float = 0.0, right: float = 0.0) -> bytes: ...
async def servo(self, joint: Joint, angle: float) -> bytes: ...
async def servos(self, **angles: float) -> bytes: ...
async def led(self, mode: Led) -> bytes: ...
async def stop(self) -> bytes: ...
async def reset(self) -> bytes: ...
async def reconnect(self) -> None: ...
async def escanear(self, timeout: float = 10.0) -> dict[str, Any]: ...
async def estado(self) -> dict[str, Any]: ...
async def salud(self) -> dict[str, Any]: ...
```

En `BridgeRobot`, lo específico del puente:

```python
async def connect(self) -> None: ...      # POST /conectar
async def disconnect(self) -> None: ...   # POST /desconectar
async def send_raw(self, payload: bytes, *, force: bool = False) -> bytes: ...
async def send(self, command: Command, *, force: bool = False) -> bytes: ...
async def escanear(self, timeout: float = 10.0) -> dict[str, Any]: ...  # GET /escanear?ms=
```

- Cliente HTTP con **`urllib` de la biblioteca estándar**, en un hilo
  (`asyncio.to_thread`): la librería solo depende de `bleak` y no quiere
  arrastrar `httpx` (además, `urllib` no bloquea el event loop si va en un hilo).
- Misma semántica de errores que hoy: si el puente contesta `{"ok": false}` →
  `AiroWriteError` / `AiroNotConnected` / `AiroNotFound` con el mensaje del puente.
- El paquete se manda **solo cuando cambia** (más un latido de 1 Hz por si el
  ESP32 se reinició y perdió el que tenía guardado).
- **El enlace BLE lo lleva la placa**, no el cliente: por eso el cliente no
  suelta la conexión cuando algo falla (el campo `conexion_gestionada` lo
  dice, y la sesión lo respeta).
- El `escanear` de los dos devuelve **el mismo formato**
  (`{"dispositivos": [{"mac", "nombre", "rssi"}]}`), así que `airo scan` se ve
  igual en los dos caminos.

### 5.2 Selección de backend

`AIRO_BRIDGE_URL` (por defecto vacío) decide el camino:

```bash
# con BLE directo (portátil con Bluetooth)
mise run run

# a través del puente ESP32
AIRO_BRIDGE_URL=http://airo-bridge.local:8080 mise run run
```

- `airo_ble/bridge.py` tiene la fábrica `crear_robot()`: si hay `AIRO_BRIDGE_URL`
  → `BridgeRobot`; si no → `AiroRobot` (bleak). **Es el único punto donde se
  decide**, así que la consola, la API web, el puente de Scratch y la CLI se
  comportan igual sin tocar su código.
- `airo_ble/session.py`, `console.py`, `server.py` y `commands.py` usan la fábrica
  (y de tipar el cliente como `ClienteRobot`, no como "uno de estos dos").
- `bleak` sigue siendo una dependencia normal: el import ya es perezoso
  (`client.py` lo hace dentro de `connect()`), así que con el puente puesto no
  hace falta Bluetooth en el portátil.

### 5.3 Tests

- `tests/test_bridge.py`: **el servidor HTTP del firmware de verdad** (con un BLE
  de mentira) contra **el cliente de verdad**. Así se comprueba que las dos
  mitades del contrato encajan: caminos, códigos (409) y cuerpo (bytes crudos).
- Tests de la selección de backend (con y sin `AIRO_BRIDGE_URL`).
- `tests/test_firmware_esp32.py`: el doble de `bluetooth` imita la placa (el IRQ
  7, los layouts de los eventos), así que se prueba el flujo entero —conectar,
  descubrir, escribir, refrescar— sin robot.
- Los tests del camino bleak no se tocan: siguen en verde.

## 6. El firmware

```
firmware/esp32/
├── main.py       # arranque: WiFi + servidor HTTP + BLE + refresco
├── puente.py     # las rutas del puente y el mantenimiento de la conexión
├── ble_robot.py  # cliente BLE: escanear, conectar, descubrir, escribir, refrescar
├── http_srv.py   # servidor HTTP mínimo sobre asyncio.start_server
├── wifi.py       # conexión a la WiFi (las credenciales van en wifi.json)
├── led.py        # el LED RGB: el color es el estado, el destello es la actividad
├── spike.py      # el spike de la Fase 0, a pelo
├── mip.json      # sin dependencias externas
└── README.md     # flasheo, particiones, IP, credenciales del WiFi
```

API de MicroPython que se va a usar (documentada en
<https://docs.micropython.org/en/latest/library/bluetooth.html>):

| Necesidad | Llamada | Evento IRQ |
|---|---|---|
| Escanear | `BLE.gap_scan(duration_ms)` | `_IRQ_SCAN_RESULT` → `(addr_type, addr, adv_type, rssi, adv_data)` |
| Conectar | `BLE.gap_connect(addr_type, addr)` | `_IRQ_CENTRAL_CONNECT` |
| Descubrir servicio `FFF0` | `BLE.gattc_discover_services(conn, uuid)` | `_IRQ_GATTC_SERVICE_RESULT` / `_IRQ_GATTC_SERVICE_DONE` |
| Descubrir characteristic `FFF1` | `BLE.gattc_discover_characteristics(conn, start, end, uuid)` | `_IRQ_GATTC_CHARACTERISTIC_RESULT` / `_..._DONE` |
| Escribir | `BLE.gattc_write(conn, handle, data, mode=1)` | `_IRQ_GATTC_WRITE_DONE` |
| Desconectar | `BLE.gap_disconnect(conn)` | `_IRQ_CENTRAL_DISCONNECT` |

Detalles del hardware:

- **PSRAM octal de 8 MB**: la N16R8 lleva PSRAM *octal*, así que toca la build
  `SPIRAM_OCT` de MicroPython (la normal solo auto-detecta PSRAM_quad). Binario
  exacto para esta placa y versión:
  `https://micropython.org/resources/firmware/ESP32_GENERIC_S3-SPIRAM_OCT-20260824-v1.29.0.bin`
  (1,7 MB). Se fija **v1.26.1** a propósito: es la misma versión que trae Ubuntu
  26.04 en sus repos, así que la CI y el chip hablan el mismo MicroPython.
- **Reloj**: MicroPython avisa de que en ESP32 el clock del sistema no debe bajar de
  80 MHz con el BLE activo. El default (160 MHz) va bien; no tocarlo.
- **Particiones** (16 MB): ~2 MB de firmware MicroPython + ~4 MB de partición
  `littlefs` para logs y configuración; el resto libre.
- **WiFi**: se queda fijo en la red de casa. Las credenciales van en `mip.json`
  (fuera del repo, como está hecho con los secretos).
- **Dos USB en la placa**: el nativo (CDC) y el del puente UART (CH343). Para
  flashear, el UART es más cómodo (auto-reset); con el nativo hay que mantener
  pulsado BOOT al resetear.
- **LED RGB (WS2812)**: está en el GPIO48 en las placas rev. 1.0 y en el
  GPIO38 en las rev. 1.1 (el chip no lo dice, así que se manejan los dos).
  Se usa como indicador de estado: rojo = nada conectado, azul = buscando,
  verde = conectado, y parpadea del color que tenga cuando llegan comandos
  (ver `firmware/esp32/README.md`).

## 7. Plan de trabajo

Estimaciones en jornadas a ratos (4-6 h). "Hito" = verificable con el robot delante.

### Fase 0 — Spike (4-6 h) 🟢 hito — **casi hecha**

- **Pasar la placa a la VM**: el USB de esta VM es emulado, así que la placa hay que
  enchufarla en el host y añadirla como *USB Host Device* en virt-manager (o
  flashear desde el host). Sin esto no hay `/dev/ttyUSB*` ni `/dev/ttyACM*`.
- Flashear el ESP32-S3 con MicroPython (`esptool`), montar `mip.json`.
- Confirmar la PSRAM octal activa (build `SPIRAM_OCT`).
- Escanear desde MicroPython y ver el robot (`AIRo`).
- Conectar, descubrir `FFF0`/`FFF1` y **escribir el paquete de 20 bytes**.
- Comprobar que el robot se mueve.

Comandos preparados (una vez que la placa se vea en `/dev/ttyUSB0`):

```bash
pip install esptool mpremote
esptool --chip esp32s3 --port /dev/ttyUSB0 write_flash 0x0 \
    ~/.cache/airo-firmware/ESP32_GENERIC_S3-SPIRAM_OCT-v1.29.0.bin
mpremote connect /dev/ttyUSB0 fs cp main.py :main.py
mpremote connect /dev/ttyUSB0 reset
```

**Estado**: **hecha**. La placa está flasheada con MicroPython 1.29.0 (build
`SPIRAM_OCT`), arranca, se conecta a la WiFi, **ve al robot** (`AIRo` =
`64:E0:39:2D:90:80`), se conecta a él, descubre `FFF0`/`FFF1` y **escribe los 20
bytes**: el robot los confirmó (3 paquetes: parar → avanzar 1 s → parar) y se
movió un segundo, justo lo que hace el spike.

**Criterio de salida**: el robot se mueve desde el ESP32. Si aquí no se puede, el
proyecto se replantea sin haber gastado más que una jornada.

### Fase 1 — Firmware del puente (6-10 h) 🟢 hito — **hecha**

- `http_srv.py`: servidor HTTP mínimo (parseo de request, JSON, `application/octet-stream`).
- `ble_robot.py`: cliente BLE (escanear → conectar → descubrir → escribir →
  refrescar), con candado, timeout de escritura y reconexión.
- `puente.py`: las rutas y el mantenimiento de la conexión.
- `main.py`: WiFi, arranque y apagado limpio.
- `spike.py`: el spike de la Fase 0, ejecutable a pelo.

**Criterio de salida**: `curl http://<ip>:8080/estado` y `curl -X POST --data-binary
@paquete.bin http://<ip>:8080/escribir` funcionan y el robot obedece.

**Estado**: **hecha**. El puente responde por HTTP desde el portátil (`/salud`,
`/estado`, `/escanear`, `/escribir`, `/conectar`, `/desconectar`), el cliente de
Python habla con él de punta a punta por la red y **el robot obedece**: se
movió un segundo con los 20 bytes que le mandó la placa.

### Fase 2 — Backend Python (4-6 h) 🟢 hito — **hecha**

- `airo_ble/cliente.py` con la clase base `ClienteRobot` (la interfaz común).
- `airo_ble/bridge.py` con `BridgeRobot` (y la fábrica `crear_robot`).
- Selección de backend por `AIRO_BRIDGE_URL` en `session.py`, `commands.py`,
  `console.py` y `server.py`.
- Tests sin hardware: el servidor del firmware contra el cliente de verdad.

**Criterio de salida**: la API del portátil, con `AIRO_BRIDGE_URL` puesto, mueve el
robot a través del ESP32. Los tests en verde.

**Estado**: **hecha**. El cliente y la API hablan con el puente (verificado
contra la placa real) y el paquete que llega al robot es el de 20 bytes que
construye `protocol.py`.

Además, los dos caminos (BLE y puente) quedaron **unificados**: los dos
clientes heredan de `ClienteRobot`, devuelven el mismo formato y dan los mismos
errores, así que el código que llama al robot no sabe por dónde va. El test
`tests/test_bridge.py` compara sus interfaces y falla si a uno le falta un
método del otro.

### Fase 3 — Tooling, CI y documentación (4-6 h)

- `mise run firmware-flash` (esptool + mpremote), `firmware-deploy`,
  `firmware-run`, `firmware-spike`, `firmware-wifi`, `firmware-logs`.
- CI: job que comprueba que el firmware pasa `ruff`/`pyright` (MicroPython es
  Python; se puede analizar con las mismas herramientas) y que `mip.json` está
  coherente.
- `firmware/esp32/README.md`: flasheo, particiones, IP, mDNS, credenciales y la
  trampa del puerto serie.

**Estado**: las tareas de mise están (`firmware-flash`, `firmware-run`,
`firmware-wifi`, `firmware-logs`). La CI no necesita un job aparte: `ruff` y
`pyright` ya miran `firmware/` (está en la configuración), los tests del
firmware van en la suite normal, y `tests/test_firmware_coherencia.py`
comprueba que la versión de MicroPython sea la misma en `mip.json`, en
`mise.toml` y en el README, que todo módulo de la placa tenga su stub y que
los ficheros no se desvían del ASCII.

El mDNS lo trae el propio port del ESP32 (el nombre se pone antes de activar
la interfaz, que es cuando se inicializa el responder), pero **no se ha podido
comprobar**: en la red de pruebas el tráfico mDNS entero no pasaba, así que el
camino que funciona es la IP.

**Criterio de salida**: clonar el repo en otra máquina y flashear con un comando.

### Fase 4 — Robustez (4-8 h, opcional)

- Reconexión si el robot se apaga y se vuelve a encender. *(Hecha: la tarea de
  fondo del puente reconecta solo. Con `AUTO_CONECTAR = False` la placa no
  agarra al robot sola, pero el botón "Conectar" de la web vuelve a buscarlo y
  a engancharlo cuando aparece.)*
- Watchdog y reinicio limpio del puente.
- Token simple en las peticiones (si la red no es de fiar).
- OTA (`mpremote` + `rshell`).

### Resumen

| Fase | Contenido | Horas | Hito |
|---|---|---|---|
| 0 | Spike con hardware | 4-6 | El robot se mueve desde el ESP32 |
| 1 | Firmware del puente (BLE + HTTP) | 6-10 | El puente acepta escrituras por HTTP |
| 2 | Backend Python (`bridge.py` + tests) | 4-6 | La API del portátil mueve el robot vía ESP32 |
| 3 | Tooling, CI, documentación | 4-6 | Flasheo en un comando |
| 4 | Robustez (opcional) | 4-8 | El puente aguanta solo |
| | **Total** | **~18-36 h** | |

Comparado con la variante "el ESP32 sirve también la API y la web" (~90-150 h),
el puenteBLE es la primera entrega con muy buena relación esfuerzo/resultado.

## 8. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| La IP del ESP32 cambia al reiniciar el router | Medio | mDNS (`airo-bridge.local`) + `AIRO_BRIDGE_URL` con hostname; opcionalmente IP fija por DHCP |
| El HM-10 se duerme y deja la escritura colgada | Alto (ya conocido) | Write con respuesta + timeout en el firmware, con reconexión |
| La build de MicroPython no lleva la PSRAM octal | Medio | Se verifica en la Fase 0, antes de escribir código |
| La API de `bluetooth` cambia entre versiones | Medio | Fijar la versión en `mip.json` y documentarla |
| Un salto extra de latencia (HTTP) en el ritmo de envíos | Bajo | +1-3 ms sobre un ritmo de 50 ms: irrelevante |
| El puente queda accesible a toda la red | Bajo | Solo en la LAN; token simple en la Fase 4 |
| Que el portable y el ESP32 se queden sin la misma red | Medio | Aviso claro en `README` y en el mensaje de error de la API |

## 9. Criterio de éxito (una frase)

> Con el ESP32 encendido y en la misma red, `AIRO_BRIDGE_URL=http://airo-bridge.local:8080 mise run run`
> levanta la API y la web de siempre, y desde la web se mueve el robot: el
> portátil no necesita Bluetooth y el ESP32 no sabe nada del protocolo AIRO.

## 10. Si más adelante se quiere el ESP32 autónomo

Hace falta lo que se analyzed en la variante completa: copiar el núcleo
(`protocol.py`, `session.py`, `arms.py`) al firmware mediante una tarea de mise
(con su test de "copia al día", como el de `web/src/servos.js`), reimplementar la
capa HTTP/WebSocket sin FastAPI y servir `web/dist` desde LittleFS. Son las fases
4-6 de la variante autónoma, unas 70-120 h más. El puente que se hace aquí es
exactamente el primer 30% de ese camino: el cliente BLE del ESP32 y su servidor
HTTP ya son los mismos.
