# AIRO para Scratch

Controlar el robot Clementoni AIRO desde Scratch (o TurboWarp).

## Como funciona

El navegador no puede hablar BLE con el robot, asi que hay dos piezas:

```
  Scratch (navegador)  --HTTP-->  airo_ble.server  --BLE-->  AIRO
      bloques JS                         Python
```

- `airo.js` — la extension de Scratch 3 (los bloques).
- `../server.py` — el servidor local (`python3 -m airo_ble.server`): habla con
  el robot y mantiene la conexion viva (el firmware devuelve los brazos al
  reposo si deja de recibir paquetes).
- `test.html` — una pagina con botones para probar el servidor sin Scratch.

## Arrancar

```bash
python3 -m airo_ble.server
```

Deberia salir algo como:

```
[airo] conectado a 64:E0:39:2D:90:80
[airo] servidor en http://localhost:8765
```

Abre <http://localhost:8765> para la pagina de pruebas. Si el robot esta
"colgado" (el modulo BLE sigue enganchado a una conexion anterior), apaga y
enciende el robot.

### Si el puerto 8765 esta ocupado

Si el 8765 lo usa otra cosa, se puede arrancar el puente en otro puerto:

```bash
python3 -m airo_ble.server --port 8766
```

Y **no hay que tocar la extension**: esta prueba los puertos 8765, 8766, 8767
y 8768 y se queda con el primero que conteste con el estado del AIRO (un
`/api/status` nuestro trae `brazos` e `izquierda`; el de otro programa no).
Aun asi, la URL que se pone en TurboWarp es la del puerto que se usa:

```
http://localhost:8766/scratch3_airo/airo.js
```

**Ojo**: solo puede haber un cliente BLE conectado al robot. Si la API web
(la de `http://localhost:8100`) esta conectada, el puente de Scratch no
podra conectarse al robot: para usar uno u otro, para el otro.

### Con el puente del ESP32-S3

El servidor de Scratch tambien funciona **a traves del puente** del ESP32-S3
(el chip que esta al lado del robot). Con `AIRO_BRIDGE_URL` puesta, el
servidor habla con la placa por HTTP en vez de por Bluetooth, y el portable
no necesita radio:

```bash
export AIRO_BRIDGE_URL=http://192.168.1.147:8080
python3 -m airo_ble.server
```

El LED RGB de la placa dice en que estado esta el enlace (rojo: nada
conectado, azul: buscando, verde: conectado) y parpadea cuando llegan
comandos.

## Cargar los bloques

En **TurboWarp** (la version modificada de Scratch que si admite extensiones
propias):

1. Abre <https://turbowarp.org> y pulsa "Editar".
2. Menu "Custom Extension" -> "Extension URL" con:
   `http://localhost:8765/scratch3_airo/airo.js`
   (tambien puedes pegar el codigo de `airo.js` directamente en el editor).
3. Añade la extension al proyecto y ya aparecen los bloques.

En la Scratch oficial no se pueden cargar extensiones propias en un proyecto
normal; hace falta TurboWarp o un editor de extensiones.

## Los bloques

| Bloque | Que hace |
|---|---|
| `mover el AIRO hacia delante con velocidad (n)` | ruedas a la velocidad indicada (1-3) |
| `mover el AIRO hacia atras con velocidad (n)` | idem hacia atras |
| `girar el AIRO a la izquierda/derecha con velocidad (n)` | gira sobre si mismo |
| `parar el AIRO` | detiene las ruedas |
| `esperar (n) segundos` | espera (util entre movimientos) |
| `poner la luz del AIRO en (on/off/flash/fade)` | el LED azul |
| `poner el brazo (izquierdo/derecho) en posicion (arriba/abajo/medio/golpe/guardia)` | los brazos |
| `poner el (hombro/codo) del brazo (izquierdo/derecho) a (n) grados (en (n) segundos)` | una articulacion a un angulo exacto; con 0 segundos va de golpe y con un tiempo el movimiento es lento |
| `mover la articulacion (...) a (n) grados` | articulacion suelta |
| `hacer una kata de karate` | la coreografia completa |
| `resetear el AIRO` | brazos al reposo y parar |
| `estado del AIRO` | reporter con un resumen |
| `¿el AIRO esta conectado?` | booleano |

## Ejemplo

```
cuando se pulse la bandera verde
  repetir 4
    girar el AIRO a la izquierda con velocidad 2
    esperar 1 segundos
  hacer una kata de karate
  poner la luz del AIRO en flash
```

## Notas

- El servidor escucha solo en `127.0.0.1` (no es accesible desde la red).
- La extension busca sola el puerto del servidor (8765, 8766, 8767, 8768) y
  se queda con el primero que conteste con el estado del AIRO: **no hay que
  tocar `airo.js` para cambiar de puerto**.
- Scratch y el servidor tienen que estar en el mismo equipo (localhost).
- La velocidad va de 1 a 3 (el robot solo tiene tres niveles).
- Los bloques de accion **esperan** a que el servidor conteste, asi que el
  orden de los bloques es el orden en que llegan los comandos.
