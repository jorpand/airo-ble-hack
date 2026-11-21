# Firmware del puente BLE (ESP32-S3)

Este directorio es el MicroPython que corre en el ESP32-S3. Es la Fase 0 del
plan ([`docs/plan-esp32.md`](../../docs/plan-esp32.md)): el **spike** que
comprueba que el chip puede ver al robot, conectarse y escribirle.

La idea del proyecto (versión corta): el ESP32 **no sabe nada del protocolo
AIRO**. Solo sabe escribir bytes en la characteristic `FFF1`. El paquete de 20
bytes lo sigue construyendo `airo_ble/protocol.py` en el portátil, así que el
protocolo no se duplica ni se toca.

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

## La API de `bluetooth` en la práctica

Estas son las rarezas que hay que tener en el bolsillo, todas comprobadas
contra la placa (no salen en la documentación):

| Lo que parece | Lo que hay que hacer |
|---|---|
| `bluetooth.UUID16(0xFFF0)` | No existe: es `bluetooth.UUID(0xFFF0)` |
| `str(uuid)` → `"0000fff0-…"` | Es `"UUID(0xfff0)"`. Mejor comparar con `bytes(uuid)` |
| `bluetooth._IRQ_SCAN_RESULT` | No existen: los eventos van numerados (ver `main.py`) |
| Conexión hecha → IRQ 1 | En el port NimBLE, `gap_connect` avisa con el **7** |
| `gap_scan(0)` para parar | No: `gap_scan(0)` deja el escaneo para siempre. Se para con `gap_scan(None)` |
| Descubrir `UUID(0xFFF0)` | El robot lo registra con UUID de 128 bits: hay que descubrir **todo** y filtrar |
| `print(..., flush=True)` | No existe en MicroPython |

Y el layout de los datos de cada evento (en 1.26 y en 1.29 es el mismo):

```
SCAN_RESULT            (addr_type, addr, adv_type, rssi, adv_data)
GATTC_SERVICE_RESULT   (conn_handle, inicio, fin, uuid)
GATTC_CHARACTERISTIC   (conn_handle, fin, handle, props, uuid)
GATTC_WRITE_DONE       (conn_handle, value_handle, status)
```

## Ejecutar el spike

```bash
python -m mpremote connect /dev/ttyUSB0 run firmware/esp32/main.py
```

Lo que hace, paso a paso:

1. Escanea 5 s y lista lo que ve.
2. Busca al robot por su nombre (`AIRo`, con la "o" en minúscula).
3. Conecta y descubre `FFF0` (servicio) y `FFF1` (characteristic).
4. Escribe el paquete de **parar** (con respuesta: `gattc_write(mode=1)`).
5. Escribe el de **avanzar despacio**, espera 1 s y vuelve a parar.

Si el robot se mueve, el BLE funciona desde el chip y se puede seguir con la
Fase 1 (el servidor HTTP del puente).

## Notas de la API

- Se usa la API **de bajo nivel** de MicroPython (`BLE.gattc_*`), la de 1.24 en
  adelante; la vieja `bluetooth.Scanner` ya no existe.
- Los IRQ se atienden en la tarea del BLE: el manejador solo guarda estado, no
  duerme ni imprime. Las esperas se hacen fuera, con `time.ticks_ms`.
- Los UUID se comparan por su parte corta de 16 bits, porque el base UUID del
  robot puede cambiar (`0000fff0-...-00805f9b34fb` o `0000fff0-...-000000000000`).
- Los 20 bytes del paquete caben justo en el MTU mínimo (23 bytes ATT → 20 de
  payload), así que no hace falta trocear ni negociar MTU.

## Lo que NO está aquí todavía

- El servidor HTTP del puente (Fase 1).
- La copia del núcleo de Python (no hace falta en la versión puente: el chip no
  construye paquetes).
- Las credenciales del WiFi: van en `mip.json`, fuera del repo.
