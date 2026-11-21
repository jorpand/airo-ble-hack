# Evidencia — de donde sale cada byte del protocolo

Desensamblado de `libil2cpp.so` (arm64-v8a) del APK oficial de AIRO.
Las direcciones son RVAs del binario; el `Offset` de fichero es RVA - 0x4000.

| Fichero | Método | Qué demuestra |
|---|---|---|
| `RobotStatus_ctor.asm` | `RobotStatus.ctor` | asigna el array: new byte[0x14] = 20 bytes |
| `RobotStatus_SetFixedBytes.asm` | `RobotStatus.SetFixedBytes` | cabecera 0xA5 en data[0] y cola fija en data[10..19] |
| `RobotStatus_set_LeftMotorSpeed.asm` | `RobotStatus.set_LeftMotorSpeed` | data[4]=direccion izq, data[5]=magnitud |
| `RobotStatus_set_RightMotorSpeed.asm` | `RobotStatus.set_RightMotorSpeed` | data[2]=direccion der, data[3]=magnitud |
| `RobotStatus_set_LedBlue.asm` | `RobotStatus.set_LedBlue` | data[1]=estado del LED |
| `RobotStatus_set_ServoMotorOneAngle.asm` | `RobotStatus.set_ServoMotorOneAngle` | data[6]=servo1 |
| `RobotStatus_set_ServoMotorTwoAngle.asm` | `RobotStatus.set_ServoMotorTwoAngle` | data[7]=servo2 |
| `RobotStatus_set_ServoMotorThreeAngle.asm` | `RobotStatus.set_ServoMotorThreeAngle` | data[8]=servo3 |
| `RobotStatus_set_ServoMotorFourAngle.asm` | `RobotStatus.set_ServoMotorFourAngle` | data[9]=servo4 |
| `RobotStatus_set_LeftArmOffset.asm` | `RobotStatus.set_LeftArmOffset` | offset -> campo float, no byte del paquete |
| `BleRobot_SetLeftMotorSpeed.asm` | `BleRobot.SetLeftMotorSpeed` | redondeo Math.Round (banker's) antes de pasar el int |
| `BleRobot_SetBlueLed.asm` | `BleRobot.SetBlueLed` | LED por enum |
| `BleRobot_FixedUpdate.asm` | `BleRobot.FixedUpdate` | envio periodico del paquete + contador packageIdx |
| `BleRobot_ResetStatus.asm` | `BleRobot.ResetStatus` | servos a 0 |
| `AiroControl_set_RightShoulderAngle.asm` | `AiroControl.set_RightShoulderAngle` | hombro derecho -> SetFirstServoMotor |
| `AiroControl_set_RightArmAngle.asm` | `AiroControl.set_RightArmAngle` | brazo derecho -> SetSecondServoMotor |
| `AiroControl_set_LeftArmAngle.asm` | `AiroControl.set_LeftArmAngle` | brazo izquierdo -> SetThirdServoMotor |
| `AiroControl_set_LeftShoulderAngle.asm` | `AiroControl.set_LeftShoulderAngle` | hombro izquierdo -> SetFourthServoMotor |

## El robot real (2026-11-10)

Esto no es desensamblado: es la comprobacion con el **robot delante de la
camara**, para desempatar los dos lados de los brazos.

| Comprobacion | Qué demuestra |
|---|---|
| `session.brazo("derecho", "arriba")` (bytes 6=13, 7=0) | levanta el brazo **derecho** del robot (el que está a su derecha mirándolo de frente, con la cara vista). |
| `session.brazo("izquierdo", "arriba")` (bytes 8=40, 9=23) | levanta el brazo **izquierdo** del robot. |
| Barrido del **codo derecho** (byte 7 = 0, 10, 20, 23) con el hombro arriba | los bytes 23, 30 y 40 dan el mismo resultado (el codo ya está en su tope): el codo solo usa el tramo 0..23. |

En todas, el robot mirando a cámara y con las ruedas paradas (los bytes 2-5 a 0).

## El modelo de acciones (2026-11-10, tarde)

Esto es la traza de los bytes que salen por el BLE con el modelo de acciones
nuevo (movimiento lento en rampa, alcance y paralelismo).
Se obtuvo con un espia sobre `Command.set_joint`, es decir, es exactamente lo
que se manda al robot.

| Qué | Traza de bytes |
|---|---|
| **Movimiento lento** (hombro derecho a "arriba" en 3 s) | byte 6: `20 20 20 19 19 19 … 15 15 14 14 … 13 13` (60 escalones) y byte 7: `20 19 19 18 18 … 1 1 0 0` |
| **De golpe** (el mismo destino, sin tiempo pedido) | byte 6: `13` y byte 7: `0` (un solo salto) |
| **Alcance: solo el codo** a 90° | solo cambia el **byte 7** → `9` |
| **Alcance: solo el hombro** con la pose "arriba" | solo cambia el **byte 6** → `13` |
| **Paralelismo**: derecha "arriba" + izquierda "abajo" | los cuatro en el **mismo paquete**: `{6: 13, 7: 0, 8: 17, 9: 7}` (el 9 con la calibracion del hombro izquierdo: 11 − 4) |

Referencias: byte 6 = hombro derecho, 7 = codo derecho, 8 = codo izquierdo,
9 = hombro izquierdo (guía §2). Detalle en `../protocolo.md` § 8.1 y
`PLAN-MEJORAS.md` § 0.g.

**Lo que falta**: ver la rampa en el robot de verdad (hace falta un *power
cycle*: el HM-10 se duerme a los ~5 min y tarda ~40 s en anunciarse).


## El movimiento lento, comprobado en el robot (2026-11-10, 17:36-17:40)

Con el robot delante de la camara (`/dev/video0`) y las medidas alineadas por
hora de reloj con los comandos (`tools/hardware/medida_final.py`):

| | De golpe | Lento (rampa de 4 s) |
|---|---|---|
| Bytes por BLE | un solo salto (`13`) | `20 19 19 19 18 18 ... 15 15 14 14 ... 13 13` |
| Movimiento en la camara | **1** fotograma (0,8 s), a las 17:36:59 | **5** fotogramas seguidos, de las 17:37:15 a las 17:37:19 |

En el caso lento el brazo esta **a medio camino** en los intermedios: eso es
la rampa, no un salto con una espera detras.

Ademas, el recorrido completo (170 grados del codo) se hace en menos de un
segundo, asi que la velocidad de 150 grados/s que usa el modelo es prudente.

| Script | Que demuestra |
|---|---|
| `tools/hardware/medida_final.py` | el que hace la prueba e imprime las horas para alinear |
| `tools/hardware/verificar_rampa.py` | el que solo mira los bytes que salen por BLE |
| `tools/hardware/comparar_lento_vs_golpe.py` | la version que compara las dos formas en una sola sesion |
| `tools/hardware/medir_velocidad_servo.py` | mide cuanto tarda el servo en llegar de verdad |


## La interfaz grafica (2026-11-10, tarde)

La interfaz se reviso en un Chromium headless de verdad (sin mocks) antes y
despues de los arreglos. Lo que se vio:

| Vista | Que se ve |
|---|---|
| Escritorio | los brazos del robot **salidos de la tarjeta** (a la izquierda y a la derecha del todo) |
| Tablet | la paleta comiendose la pantalla entera |
| Movil | la cabecera rota: el boton "Conectar" fuera de la pantalla y el chip "avanzado" cortado |
| Bloque | los botones ▲▼✕ **encima del deslizador** y el deslizador como barra negra |
| Escritorio, despues | botones en la cabecera del bloque, deslizador legible, duracion por bloque y el robot dentro de su tarjeta |
| Tablet, despues | paleta en rejilla de 5 columnas, cabecera en una fila |
| Movil, despues | cabecera en dos filas, paleta en dos columnas, bloques con deslizador y duracion |
| Movil, bloque del brazo | con el deslizador y los botones en su sitio |
| Arrastre | el programa con un bloque arrastrado desde la paleta |

El script `tools/hardware/capturar_interfaz.py` **comprueba el arrastrar y
soltar de verdad** con Playwright y devuelve un JSON con lo que ha pasado:

```json
{
  "deshacer":            { "antes": 10, "despues": 0 },
  "ctrl_z":              { "bloques": 0 },
  "arrastrar":           { "antes": 10, "despues": 11 },
  "reordenar":           { "antes": ["Avanza", "Luz", ...], "despues": ["Luz", "Avanza", ...] },
  "arrastrar_dentro_de_repetir": { "antes": 2, "despues": 3 },
  "duracion":            "⏱ dura unos 11,1 s"
}
```

Ejecutar: `mise run setup` y luego `.venv/bin/python tools/hardware/capturar_interfaz.py`
(con la API levantada en el puerto 8100).

Nota: el arrastre necesita que el origen y el destino esten **a la vez en
pantalla**. Si el bloque de la paleta queda fuera de la vista, el navegador
hace scroll y el arrastre se pierde: por eso el test del "repetir" usa una
ventana alta (1440x2400).

### La duracion estimada, contra el robot real

`evidencia/medir_duracion.py` lanza un programa que **no mueve el robot**
(luz + espera) y mide con el reloj cuanto tarda de verdad:

```
Lo que dice la API:  3.40 s (por bloque: [0.4, 3.0])
Lo que tarda de verdad: 3.42 s
Diferencia: 0.02 s (OK)
```

Los atajos de teclado tambien se han comprobado en el navegador (Chromium
headless): `Ctrl+Z` deshace el programa (8 bloques → 0), `Alt+↓` mueve el
bloque seleccionado, `Supr` lo borra y `Ctrl+Enter` ejecuta (esta ultima con
el robot conectado, asi que el ejemplo se ejecuto de verdad: el robot levanto
los dos brazos, dio dos golpes de karate, giro a la derecha y dio un paso;
despues quedo parado, con la luz apagada y la cola vacia).


## Guardar programas y funciones (2026-11-10, noche)

El guardado va al **servidor**: un archivo JSON en `~/.airo/guardado.json`
(variable `AIRO_GUARDADO` para cambiarlo). Es un archivo con dos listas,
`programas` y `funciones`.

| Que se ve |
|---|
| la columna "4 · Guardado" a la derecha, con el programa guardado y la funcion "Saludo" |
| dos bloques marcados (clic y Mayusculas) con el contorno oscuro |
| la barra "2 bloques marcados" con el nombre y "Guardar como funcion" |
| en un portatil de 1440 la columna se pasa abajo y "Programas" y "Funciones" quedan en dos columnas |

La prueba (`tools/hardware/probar_guardado.py`, con la API levantada en el 8100):

```json
{
  "bloques_del_ejemplo": 8,
  "marcados": 3,
  "funciones_en_la_lista": 1,
  "nombre_de_la_funcion": "⚡ Saludo",
  "llamadas_en_el_programa": ["Saludo"],
  "resumen": "... → 9. Llama a «Saludo»",
  "editando": "Editando «Saludo»",
  "programas_guardados": ["📄 Mi programa bueno"],
  "tras_recargar": {
    "programas": ["📄 Mi programa bueno"],
    "funciones": ["⚡ Saludo"]
  },
  "bloques_al_cargar": 9
}
```

Lo de "tras recargar" es lo importante: el programa y la funcion **siguen
ahi** despues de recargar la pagina, porque estan en el servidor y no en el
navegador.

Y la semantica de **referencia** (si editas la funcion, cambian todos los
programas que la usan), medida con la API:

```
duracion con la llamada:          4.07 s (por bloque: [3.07, 1.0])
duracion tras editar la funcion:  9.07 s (por bloque: [8.07, 1.0])
```


## Los "repetir" anidados (2026-11-10, noche)

El usuario avisó de que "los repite dentro de los repite no parecen
funcionar". El backend estaba bien (expandia los "repetir" recursivamente y
daba la cuenta correcta); el fallo estaba **solo en la web**: al meter un
bloque dentro de un "repetir" que estaba dentro de otro, no se insertaba
nada, porque `insertarEnArbol` solo buscaba el "repetir" destino en el primer
nivel del arbol.

La prueba en el navegador (`tools/hardware/probar_repetir.py`) muestra un
"Repite 3" > "Repite 2" > "Espera 1 s", con "⏱ dura unos 6 s". Antes y
despues del arreglo:

| Prueba | Antes | Ahora |
|---|---|---|
| Bloques dentro del "repetir" de dentro | **0** (no se metia nada) | **1** ✓ |
| Duracion con repetir 3 > repetir 2 > espera 1 s | — | "⏱ dura unos 6 s" ✓ |
| La misma, con una espera de 3 s | — | "⏱ dura unos 18 s" ✓ |
| La misma, con una espera de 8 s | — | "⏱ dura unos 48 s" ✓ |
| Sacar un bloque del "repetir" de dentro | — | raiz 1 → 2, dentro 2 → 1 ✓ |

En el backend se comprobo aparte que el calculo es exacto: 3 x 2 x 1 s = 6,0 s
y 7 pasos (6 esperas + el "parar" final).
