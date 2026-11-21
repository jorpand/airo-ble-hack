# AIRO para Scratch

Controlar el robot Clementoni AIRO desde Scratch (o TurboWarp).

## Como funciona

El navegador no puede hablar BLE con el robot, asi que hay dos piezas:

```
  Scratch (navegador)  --HTTP-->  airo_server.py  --BLE-->  AIRO
      bloques JS                        Python
```

- `airo.js` — la extension de Scratch 3 (los bloques).
- `../airo_server.py` — el servidor local: habla BLE con el robot y mantiene
  la conexion viva (el firmware devuelve los brazos al reposo si deja de
  recibir paquetes).
- `test.html` — una pagina con botones para probar el servidor sin Scratch.

## Arrancar

```bash
cd airo
python3 airo_server.py
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

En esta maquina el 8765 lo usa `mantra-ble`. Se puede arrancar el puente en
otro puerto:

```bash
python3 airo_server.py --port 8766
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
- La extension se comunica con `http://localhost:8765`; si cambias el puerto
  del servidor, cambialo tambien en `airo.js` (constante `API`).
- Scratch y el servidor tienen que estar en el mismo equipo (localhost).
- La velocidad va de 1 a 3 (el robot solo tiene tres niveles).
