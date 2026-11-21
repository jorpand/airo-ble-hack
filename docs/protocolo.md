# Programar tu Clementoni AIRO: el protocolo Bluetooth, al descubierto

**Fecha:** 07/11/2026 · **Robot:** Clementoni AIRO (el de plástico blanco con 6 motores, no el AIRO PRO)
**App oficial analizada:** `it.clementoni.robot.airo` (Play Store, Unity + IL2CPP)

---

## 0. TL;DR

La app oficial del AIRO no habla con el robot por una API: le manda **paquetes de 20 bytes** por Bluetooth Low Energy. Aquí está todo:

- **Servicio GATT:** `0000FFF0-0000-1000-8000-00805F9B34FB`
- **Characteristic de escritura:** `0000FFF1-0000-1000-8000-00805F9B34FB`
- **Nombre anunciado por BLE:** `AIRo`
- **Módulo dentro del robot:** HM-10 (puente BLE↔UART), confirmado por el literal de la app *"Scanning for HM10 devices..."*
- **Paquete:** 20 bytes, cabecera `0xA5`, con ruedas, 4 servos y LED

Con esto puedes escribir **tu propio cliente en Python** (`bleak`) y mandar tus comandos sin la app de Clementoni. Todo el material está en este directorio.

Lo más rápido para trastear con el robot delante es la **consola interactiva**:

```bash
python3 -m airo_ble.console
airo> avanzar 2
airo> led flash
airo> pose right_shoulder 30
```

---

## 1. El robot por dentro

| Dato | Valor | De dónde sale |
|---|---|---|
| Tipo | Clementoni AIRO (Artificial Intelligence Robot), 6 motores | Store de Clementoni, SKU 61418 / 55513 |
| Micro-controlador | HM-10 (módulo BLE↔UART) | literal `'Scanning for HM10 devices...'` en la app |
| Nombre BLE | `AIRo` | `const string ROBOT_NAME = "AIRo"` en `BleRobot` |
| Servicio | `0000FFF0-…` | `const string GATT_ROBOT_SERVICE` en `BleRobot` |
| Characteristic | `0000FFF1-…` | `const string GATT_ROBOT_WRITE_CHARACTERISTIC` en `BleRobot` |
| Tipo de escritura | con respuesta (`WRITE_TYPE` 2) | `_writeCharacteristicWithResponse = true` en el plugin Java |
| Ritmo de envío de la app | ~cada 50 ms (`FixedUpdate`), con contador `packageIdx` | `BleRobot.FixedUpdate` |

`FFF0/FFF1` es el par de UUID que usan casi todos los módulos HM-10/CC2541 del mercado. No es un secreto de Clementoni: es el总线 serie estándar de esos módulos.

> **El base UUID del robot puede cambiar.** El mismo robot ha servido `0000fff0-0000-1000-8000-00805f9b34fb` (el base estándar de Bluetooth) en una conexión y `0000fff0-0000-1000-8000-000000000000` (base a ceros) en la siguiente, según cómo se haya reiniciado el módulo. El cliente lo tiene en cuenta: busca el servicio `FFF0` y la characteristic `FFF1` **por su forma corta**, no por el UUID completo.

> **Ojo con la confusion** `AIRo` vs `AIRO`: el robot se anuncia en BLE como `AIRo` (con la "o" en minúscula). Si buscas `AIRO` en mayúsculas no lo encuentras.

---

## 2. El paquete de 20 bytes

Este es el corazón del tema. La clase `RobotStatus` (en el código C# de la app) construye un `byte[20]` y lo escribe tal cual en la characteristic `FFF1`.

| Byte | Campo | Valores | Evidencia (RVAs) |
|---|---|---|---|
| `0` | **Magic** | siempre `0xA5` | `RobotStatus.SetFixedBytes` @ `0x1FBF968` |
| `1` | **LED azul** | `0` off · `1` on · `2` flash · `3` fade | `set_LedBlue` @ `0x1FBCBC4` (`strb w1, [x8, #0x21]`) |
| `2` | **Motor "derecho" de la app** = rueda **izquierda** del robot | dir `0` parado · `1` adelante · `2` atrás | `set_RightMotorSpeed` @ `0x1FBCA9C` |
| `3` | **Velocidad** de esa rueda | `0..3` | ídem (`strb w0, [x20, #0x23]`) |
| `4` | **Motor "izquierdo" de la app** = rueda **derecha** del robot | dir `0` parado · `1` **atrás** · `2` **adelante** | `set_LeftMotorSpeed` @ `0x1FBC8B4` |
| `5` | **Velocidad** de esa rueda | `0..3` | ídem (`strb w0, [x20, #0x25]`) |
| `6` | **Hombro derecho** del robot | posición del servo (byte 13..29) | `set_ServoMotorOneAngle` @ `0x1FBCCE0` |
| `7` | **Codo derecho** del robot | posición del servo (byte 0..23, ver § 2.5) | `set_ServoMotorTwoAngle` @ `0x1FBCF58` |
| `8` | **Codo izquierdo** del robot | posición del servo (byte 17..40, ver § 2.5) | `set_ServoMotorThreeAngle` @ `0x1FBD25C` |
| `9` | **Hombro izquierdo** del robot | posición del servo (byte 13..29) | `set_ServoMotorFourAngle` @ `0x1FBD560` |
| `10..19` | **Cola fija** | `5, 22, 39, 56, 73, 90, 107, 124, 141, 158` | `SetFixedBytes` @ `0x1FBF968` |

> ### ⚠️ Las RUEDAS están CRUZADAS respecto a la app (los brazos no)
>
> La app oficial habla de "motor izquierdo" y "hombro derecho". En este robot
> **las ruedas sí están cruzadas**: el motor que la app llama izquierdo mueve
> la rueda **derecha** del robot.
>
> Verificado en el hardware de tres formas independientes:
>
> 1. Mandando el mismo byte a los dos motores el robot **gira sobre sí mismo**;
>    con los bytes bien cruzados va recto.
> 2. Pidiendo giro a la izquierda con la app el robot gira a la **derecha**.
> 3. Levantando solo el byte del "hombro derecho" de la app se levanta el
>    brazo que, visto **de perfil mientras el robot gira a la izquierda**,
>    queda en el **interior** de la curva (el lado derecho).
>
> Los **hombros y los codos, en cambio, NO están cruzados**: el "hombro
> derecho" de la app es el hombro derecho de verdad (su `set_RightShoulderAngle`
> llama a `SetFirstServoMotor`, el byte 6).
>
> Comprobado con el robot delante el 2026-11-10, con una foto porposeda: el
> byte 6 levanta el brazo que está a la **derecha** del robot mirándolo de
> frente (el robot enseña la cara: los dos ojos azules y el LED del pecho).
> Antes esta tabla tenía los bytes 6/9 y 7/8 cambiados, y por eso
> `airo_ble/protocol.py` llama ahora `Joint.RIGHT_SHOULDER` al byte 6 y
> `Joint.LEFT_SHOULDER` al byte 9. **Los bytes no han cambiado**: lo que
> estaba mal era el nombre.
>
> Reverificado con el robot delante el **2026-11-10** por el camino público
> (`session.brazo("derecho", "arriba")`): el paquete sale con los bytes 6=13 y
> 7=0, y en la foto el brazo levantado es el de la **izquierda de la imagen**,
> o sea el **derecho del robot** (que está mirando a cámara). Al revés para
> `brazo izquierdo arriba` (bytes 8=40 y 9=23, brazo a la derecha de la
> imagen). Las fotos de la comprobacion con el robot delante no se publican
> aqui (son material local de trabajo), pero el desensamblado que lo demuestra
> si: [`docs/desensamblado/`](desensamblado/).
>
> Ojo también con la **cola fija**: los bytes 10..19 que pone `SetFixedBytes` **no** son una rampa arbitraria, sino los **mismos valores que usan los servos**: `5, 22, 39, 56, 73, 90, 107, 124, 141, 158` es una progresión de **5 + 17k**. El `17` es el mismo divisor que usan los servos (§ 2.5). La rampa está ahí a propósito.


### 2.1 La cola fija: qué es

`SetFixedBytes()` escribe una rampa constante en los bytes 10-19: `5 + 17k` para k=0..9. La app **nunca** los vuelve a tocar. Sin más contexto no puedo afirmar qué espera el firmware (posiblemente un checksum o una tabla de IDs de acción), pero **hay que mandarlos tal cual**: si no, el firmware rechaza o desinterpreta el paquete. Mi implementación los copia literalmente.

### 2.1.1 El firmware devuelve los brazos al reposo si dejas de mandar

Comprobado en el robot: si pasan unos segundos **sin recibir ningún paquete**, los servos se van solos a su posición de reposo, aunque el último paquete dijera "brazo arriba".

Por eso la app oficial manda el suyo **cada 50 ms sin parar** (`BleRobot.FixedUpdate`), y por eso el LED en modo `flash`/`fade` parpadea (el firmware lo interpola a partir de los paquetes que llegan).

La consola hace lo mismo: tiene un *keepalive* que refresca el paquete continuamente aunque no hagas nada. Si usas la API directamente, tienes que mandar tú el paquete periódicamente o los brazos se bajarán:

```python
while True:
    await robot.send(robot.command)      # el servo se queda donde lo pongas
    await asyncio.sleep(0.05)
```

### 2.2 El signo de las ruedas va partido en dos bytes

El firmware no usa un byte con signo. La velocidad se manda como **dirección** (byte par) + **magnitud** (byte impar). **Ojo: el byte de dirección es distinto en cada rueda**, porque la izquierda va montada al revés:

```
valor  0.0  ->  dir=0 (parado)   mag=0
valor  1.0  ->  dir=1 (adelante) mag=1     [byte 2: rueda izquierda]
valor -1.0  ->  dir=2 (atrás)    mag=1     [byte 2: rueda izquierda]

valor  1.0  ->  dir=2 (adelante) mag=1     [byte 4: rueda derecha, ¡invertido!]
valor -1.0  ->  dir=1 (atrás)    mag=1     [byte 4: rueda derecha]
```

Y la magnitud es `min(|v|, 3)`: **el robot solo tiene 3 niveles de velocidad**, no 255.

### 2.3 El redondeo es banker's rounding (y importa)

`BleRobot.SetLeftMotorSpeed(float)` llama a `Math.Round(double)` de .NET, que redondea **al par** (`MidpointRounding.ToEven`), no como Python. El orden importa:

```
0.4 -> 0 -> parado
0.5 -> 0 (¡redondeo al par!) -> parado
0.6 -> 1 -> adelante, velocidad 1
1.5 -> 2 -> adelante, velocidad 2
```

Por eso `airo_ble/protocol.py` implementa `round_half_even()` en vez de usar `round()` de Python (que redondea medio hacia arriba). Si no, te desfasas medio grado y medio nivel de velocidad respecto a la app oficial.

### 2.4 Los offsets de calibración

`RobotStatus` guarda 4 offsets (`_leftArmOffset`, `_rightArmOffset`, `_leftShoulderOffset`, `_rightShoulderOffset`) como **campos float**, no como bytes del paquete. Son la calibración de cada servo: la app suma el offset al ángulo antes de mandarlo al servo. Mi `Command.set_joint()` hace lo mismo, con offsets a 0 por defecto.

**Y sí: la app tiene un asistente de calibración.** Se llama `CalibrationManager` y su API (sacada del dump del APK) es:

| Método | Qué hace |
|---|---|
| `Setup(MainPageManager)` | arranca el asistente |
| `SetStep` / `GoNext` / `GoBack` | los pasos (`CalibrationStep` es un enum) |
| `SetLeftArmOffset(int amount)` / `SetRightArmOffset(int amount)` | ajusta el offset de un brazo, en grados |
| `SaveCalibration()` | guarda y aplica |
| `SendCalibration()` (estático) | manda los offsets al robot |
| `ResetPose()` | devuelve los brazos a la posición de reposo |
| `MainPageManager.AiroCalibration()` / `ResetAiroCalibration()` | abre el asistente / lo reinicia |
| `CalibrationButton.OnCalibrationButtonPressed()` | el botón de la interfaz |

Lo importante: **la calibración NO se le manda al robot**. La app guarda los cuatro offsets en las *PlayerPrefs* del móvil, con las claves `leftArmOffset`, `leftShoulderOffset`, `rightArmOffset` y `rightShoulderOffset`, y los aplica en el cliente al calcular el byte del servo. El firmware no sabe nada de calibración.

Por eso `protocol.py` hace exactamente lo mismo: `Command.offsets` es un offset por articulación (en grados de la app) que se suma al ángulo al serializar, truncado a entero (`fcvtzs`), tal y como hace `set_ServoMotor*Angle`.

> Detalle: el asistente solo expone los offsets de **brazos**, no los de hombros, aunque la API y las PlayerPrefs tienen los cuatro.

### 2.5 Los servos NO van en grados: van escalados

**Esto no lo tenía claro el análisis inicial y es la parte que más falla si te la saltas.**

`RobotStatus.set_ServoMotor*Angle(int)` no escribe el ángulo en el byte: escribe una **posición de servo** calculada. El desensamblado (`docs/desensamblado/RobotStatus_set_ServoMotorOneAngle.asm` y compañía) da la cadena exacta:

```
byte = | 170 + signo * (ángulo + offset) | / 8.5      -> redondeo banker's
```

- El ángulo se recorta antes a los límites mecánicos: **hombros −60..77**, **brazos −25..170**.
- El byte resultante va de 0 a 40, y **el 20 es la posición neutra** (ángulo 0). Cada byte son 8,5 grados.
- El signo va con el lado **de la app**, y como las piezas están cruzadas (§ 2), el signo de cada articulación física es el del lado contrario de la app.

Ejemplos (sin offset, en **bytes**):

| Articulación (física) | byte | ángulos → bytes |
|---|---|---|
| hombro derecho (byte 6) | 6 | −60 / 0 / +77 → 13 / 20 / 29 |
| hombro izquierdo (byte 9) | 9 | −60 / 0 / +77 → 27 / 20 / 11 |
| codo derecho (byte 7) | 7 | −25 / 0 / +170 → 23 / 20 / 0 |
| codo izquierdo (byte 8) | 8 | −25 / 0 / +170 → 17 / 20 / 40 |

> ### ⚠️ El codo solo usa el tramo 0..23 (y 17..40 en el otro lado)
>
> Los límites mecánicos del codo (−25..170) y la escala de 8,5 grados por
> byte hacen que **no todo el rango 0..40 signifique algo**:
>
> | Articulación | Byte | Rango con efecto | Fuera, el servo no se mueve |
> |---|---|---|---|
> | codo derecho | 7 | **0..23** | 24..40 (ya está en el tope "recto") |
> | codo izquierdo | 8 | **17..40** | 0..16 (ya está en el tope "recto") |
> | hombro derecho | 6 | **13..29** | 0..12 y 30..40 |
> | hombro izquierdo | 9 | **7..23** | 0..6 y 24..40 |
>
> Comprobado en el robot el 2026-11-10 mandando bytes **crudos** al codo
> derecho con el hombro arriba: los bytes 23, 30 y 40 dan imágenes
> **indistinguibles** (la diferencia de píxeles entre ellas es ruido de
> exposición), mientras que 0, 10 y 20 se ven claramente distintos.
> El barrido (byte 0, 10, 20 y 23 del codo, de izquierda a derecha) se hizo
> con el robot delante; las fotos no se publican, pero el script que lo midio
> esta en [`tools/hardware/`](https://github.com/jorpand/airo-ble-hack/tree/main/tools/hardware).
>
> La app oficial nunca manda esos bytes: `encode_servo()` recorta el ángulo
> **antes** de escalarlo, así que el byte que sale siempre cae dentro del
> rango con efecto. Solo se nota si mandas bytes a pelo con
> `set_raw_servo()`.

**Si mandas el ángulo crudo** (p. ej. 77) el firmware lo lee como 77 unidades = 484° y empuja el servo contra el tope mecánico. Por eso `protocol.py` tiene `encode_servo()` y los límites por articulación.

Y ojo con el **valor por defecto**: los bytes de servo empiezan a 0, que es el tope. La app lo resuelve llamando a `ResetStatus` (que pone los cuatro servos a 0 = byte 20). Mi `Command` arranca directamente en la **posición neutra (20)**, que es lo mismo, pero sin que el robot haga un gesto con los brazos al conectar. Se nota: si ves al robot meter un brazo en alto al empezar, es que estás mandando ceros.

> Los ángulos "positivos" no siempre significan lo mismo en los dos lados: el hombro izquierdo y el derecho giran en sentidos opuestos (son las dos mitades de un cuerpo simétrico). El comando `bruto <art> <byte>` de la consola sirve para calibrar a ojo qué ángulo te sube el brazo.

---

## 3. Cómo se obtuvo esto (cadena reproducible)

Todo sale de la app oficial, sin tocar el robot. Los pasos, por si quieres repetirlos o auditarme:

1. **Descargar el APK.** `apkeep` (EFForg) con el proveedor `apk-pure`:
   ```bash
   apkeep -a it.clementoni.robot.airo -d apk-pure ./out
   ```
   Salen un `.xapk` de 169 MB (APK base de 111 MB + `config.arm64_v8a.apk` de 58 MB).
   *(`apk-pure` y no `google-play`: el proveedor de Google Play de apkeep pide credenciales.)*

2. **Localizar el código.** Es Unity con **IL2CPP**: el C# está compilado a ARM64 en `libil2cpp.so` y los metadatos en `global-metadata.dat`.
   ```bash
   unzip -o out/it.clementoni.robot.airo.xapk config.arm64_v8a.apk -d ext/
   unzip -o ext/config.arm64_v8a.apk "lib/arm64-v8a/libil2cpp.so" -d il2cpp/
   unzip -o ext/it.clementoni.robot.airo.apk "assets/bin/Data/Managed/Metadata/global-metadata.dat" -d x/
   ```

3. **Volcar el IL2CPP.** Con Il2CppDumper v6.7.46 (necesita .NET; en Debian 12 funciona con `DOTNET_ROLL_FORWARD=Major`):
   ```bash
   dotnet Il2CppDumper.dll lib/arm64-v8a/libil2cpp.so \
        x/assets/bin/Data/Managed/Metadata/global-metadata.dat dump/
   ```
   Salen `dump.cs` (32 MB con todas las firmas), `script.json` y `stringliteral.json`.

4. **Desensamblar** los métodos (con `capstone` para ARM64) y leer los `strb` sobre el array. Cada byte del protocolo sale de una instrucción concreta: `strb w9, [x8, #0x24]` = "data[4] = dirección del motor izquierdo".

5. **La capa Java** (jadx 1.5.3 sobre `classes.dex`) confirma el envío real:
   ```java
   bluetoothGattCharacteristic.setValue(bArr);
   bluetoothGattCharacteristic.setWriteType(z ? 2 : 1);  // 2 = con respuesta
   bluetoothGatt.writeCharacteristic(bluetoothGattCharacteristic);
   ```

Todo el desensamblado está en [`docs/desensamblado/`](desensamblado/) (18 ficheros
`.asm` + [`RESUMEN.md`](desensamblado/RESUMEN.md) con qué prueba cada uno). Los
scripts que lo generaron estan en [`tools/rev/`](https://github.com/jorpand/airo-ble-hack/tree/main/tools/rev/).

### 3.1 Trampa: hay dos clases `RobotStatus`

La app contiene **dos** implementaciones distintas de `RobotStatus`: la de AIRO 1.x (la que nos interesa, con 4 servos y LED azul) y la de **AIRO PRO** (LEDs RGB, motor de pecho, efectos de sonido). Viven en el mismo APK y comparten nombre, así que es fácil desensamblar la equivocada: la 1.x está en RVAs `0x1FBC8xx`–`0x1FBF9xx`, la PRO en `0x201D3xx`–`0x201D8xx`.

**Si tienes el AIRO PRO** (el de 2025, con LED RGB y modo "A.I. Pilot"), el layout es otro: `cmd[4]`=dirección izq, `cmd[5]`=velocidad izq, `cmd[6]`/`[7]`=derecha, y añade color RGB, motor de pecho y SFX. Dímelo y te lo adapto.

---

## 4. Instalación

```bash
cd airo
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                  # la libreria (con bleak)
# o, si solo quieres el cliente BLE: pip install bleak
```

En Linux, `bleak` necesita soporte de BlueZ: `sudo apt install python3-bleak bluez`. Y el robot debe tener las **pilas puestas** (es un módulo HM-10: se apaga solo si no detectas pila).

**Dos trampas de `bleak` que ya están resueltas en el código** (probado con bleak 3.0.2):

- `characteristic.write_value(...)` **ya no existe** en bleak 3.x. El cliente usa `client.write_gatt_char(char, data, response=...)`, que es la API estable de la 0.19 a la 3.x.
- `BleakScanner.discover(return_adv=True)` cambió de forma: hasta bleak 2.x devolvía `dict[BLEDevice, AdvertisementData]` y en 3.x devuelve `dict[str, tuple[BLEDevice, AdvertisementData]]`. El cliente supports las dos.

## 5. Uso

### 5.0 La consola interactiva (lo más cómodo para trastear)

```bash
python3 -m airo_ble.console                       # busca el robot 'AIRo'
python3 -m airo_ble.console --address AA:BB:...   # MAC concreta
python3 -m airo_ble.console --dry-run             # no conecta: solo muestra los paquetes
python3 -m airo_ble.console --exec "avanzar 2" --exec "parar"
```

Es una consola tipo shell donde escribes comandos y ves el paquete que sale:

```
airo> avanzar 2            # ambas ruedas hacia delante (velocidad -3..3)
airo> izquierda 1          # gira sobre sí mismo a la izquierda
airo> led flash            # off | on | flash | fade
airo> brazo izq arriba     # brazo izquierdo arriba (sin tocar ángulos)
airo> brazo der golpe     # brazo derecho estirado hacia delante
airo> brazo ambos guardia  # los dos brazos en posición de guardia
airo> brazo der arriba 3   # la misma pose, pero LENTA (3 s, en rampa)
airo> brazo der codo 90    # solo el codo derecho, a 90 grados
airo> brazo der codo 90 3  # ... y despacio (3 s)
airo> kata                 # kata de karate: pasos, golpes y giros (20 s)
airo> pose right_shoulder 30      # una articulación, en ángulos
airo> pose l_arm=10 r_sh=20      # varias de golpe
airo> bruto left_arm 7            # byte crudo, para experimentar
airo> estado / dump / hex A5 00 …
airo> parar; salir
```

Se pueden encadenar con `;`. Mantiene la conexión y el estado entre comandos, refresca el paquete cada 50 ms como la app oficial y **para las ruedas si dejas de escribir 5 segundos** (`--watchdog`). Si el módulo se duerme a mitad de sesión, se reconecta solo.

**Historial**: la consola usa `readline`, así que tienes edición de línea completa: **↑/↓** para recuperar comandos antiguos, **Ctrl+R** para buscar, **Ctrl+A/E** para moverte, **Tab** para autocompletar. El historial se guarda en `~/.airo_history` y se recupera al abrir el programa; el comando `historial` te lo lista.

### 5.0.1 Posas de los brazos

Cada brazo tiene **dos servos** (hombro y codo), así que una pose son dos ángulos:

| Pose | hombro | codo | byte hombro der / izq | byte codo der / izq |
|---|---|---|---|---|
| `arriba` | −60 | +170 | 13 / 23 | 0 / 40 |
| `golpe` | −60 | −25 | 13 / 23 | 23 / 17 |
| `guardia` | −60 | +90 | 13 / 23 | 9 / 31 |
| `abajo` | +77 | −25 | 29 / 7 | 23 / 17 |
| `medio` | 0 | 0 | 20 / **16** | 20 / 20 |

Los bytes son de los lados **físicos** del robot (el hombro derecho es el byte 6). Los de la izquierda (hombro y codo) son con el cero calibrado en 16 (§ 5.0.3); sin calibrar serían 20.

**El lado izquierdo es el espejo del derecho, pero con el MISMO ángulo**: el signo de cada servo (que sale del desensamblado) ya invierte el sentido del giro, así que el byte sale simétrico alrededor del cero de cada brazo. Por eso la pose `medio` lleva cada brazo a **su** posición de reposo.

### 5.0.2 Calibración

La app oficial tiene un asistente de calibración (§ 2.4) que ajusta un offset por articulación. Aquí está lo mismo:

```
airo> calib                      # ver los offsets actuales
airo> calib left_arm +3          # sumar 3 grados al offset del brazo izquierdo
airo> calib right_shoulder = -5  # poner el offset exacto
airo> calib guardar              # guardar en ~/.config/airo-ble/calibration.json
airo> calib cargar               # recuperar los offsets guardados
airo> calib reset                # a cero
```

El offset se suma al ángulo al serializar (igual que en la app), así que puedes recalibrar sin volver a mover las articulaciones. Cada cambio **reeenvía el paquete al robot**, así que se ve al instante.

**Ojo con la resolución**: el byte del servo es la posición real, y un byte son **8,5 grados** (§ 2.5). Un offset de +3 grados no cambia el byte y no se nota nada: para mover un byte hay que ir a +9 (o +17 para dos bytes). El comando te avisa del byte resultante:

```
airo> calib left_arm +3
left_arm: offset +3 grados -> byte 20 (casi no se nota: 1 byte = 8.5 grados)
airo> calib left_arm +9
left_arm: offset +12 grados -> byte 21
```

### 5.0.3 Poner los brazos en la posición original (calibrar el "cero")

El firmware **no dice en qué posición está el servo**: no hay forma de leerlo (la characteristic `FFF2` no envía nada). Pero como los servos **se quedan donde los dejes con el robot apagado**, puedes marcar en el propio robot la posición de reposo que quieres y convertirla en el "cero" de cada articulación.

El "cero" es el byte que corresponde al ángulo 0. Por defecto es el 20 (el que usa la app oficial), pero se puede cambiar por articulación con el asistente:

```
airo> calibrar               # recorre las cuatro articulaciones
airo> calibrar left_arm      # o solo una

Coloca los brazos donde quieras y ajusta con +1 / -1.
  'ok' acepta el byte, 'skip' lo deja como estaba, 'q' sale.

== left_arm (byte 20) ==
  bra> +1
  byte 21
  bra> ok
  -> left_arm: cero en el byte 21
```

El asistente mueve el brazo **byte a byte** (y cada movimiento va al robot, que se ve al instante) hasta que la posición te cuadre. Al aceptar, ese byte pasa a ser el "cero" de la articulación: a partir de ahí, `pose left_arm 0` pone el brazo en esa posición.

El flujo completo sería:

1. Robot **apagado**: coloca los brazos en la posición de reposo que quieres y **márcalos** (un trocito de cinta en la articulation).
2. Robot **encendido**: arranca la consola y `calibrar`.
3. Ve ajustando con `+1`/`-1` hasta que el brazo coincida con la marca.
4. `calib guardar` para conservarlo (offsets + ceros) en
   `~/.config/airo-ble/calibration.json`. La calibración que viene con el
   paquete (`airo_ble/calibration.json`) es solo el valor por defecto: la
   tuya tiene prioridad.

También a mano:

```
airo> neutro                  # ver los ceros de cada articulación
airo> neutro left_arm 21      # poner el cero a mano
```

El offset se suma al ángulo al serializar (igual que en la app), así que puedes recalibrar sin volver a mover las articulaciones.

### 5.1 API

```python
import asyncio
from airo_ble import AiroRobot, Joint, Led

async def main():
    async with AiroRobot() as robot:              # escanea, conecta, localiza FFF0/FFF1
        await robot.drive(left=1.0, right=1.0)     # adelante
        await asyncio.sleep(2)
        await robot.servo(Joint.RIGHT_SHOULDER, 45)
        await robot.servo(Joint.LEFT_ARM, -20)
        await robot.led(Led.FLASH)
        await robot.stop()

asyncio.run(main())
```

Si prefieres no escanear, pásale la MAC: `AiroRobot(address="AA:BB:CC:DD:EE:FF")`.

### 5.2 CLI

```bash
python -m airo_ble.commands scan                              # ver qué se ve por BLE
python -m airo_ble.commands drive --left 1 --right 1 --seconds 3
python -m airo_ble.commands pose --left-arm 30 --right-shoulder 45
python -m airo_ble.commands led flash
python -m airo_ble.commands dump --left 2 --right -1 --led flash --left-arm 30   # paquete offline
python -m airo_ble.commands console                          # la consola de 5.0
```

`dump` es el que más útil es para depurar: imprime el paquete byte a byte **sin necesidad del robot**.

### 5.3 Tests

```bash
python3 tests/test_protocol.py   # 19 tests del layout byte a byte
python3 tests/test_client.py     # test del cliente con un BLE simulado
python3 tests/test_console.py    # 10 tests de la consola, sin hardware
```

Los primeros fijan el layout byte a byte contra lo que dice el desensamblado (incluido el golden packet, el banker's rounding, el escalado de los servos y la inversión de la rueda izquierda). El segundo inyecta un `bleak` falso y comprueba que el escaneo encuentra el `AIRo`, que se localiza FFF0/FFF1 y que cada comando sale con 20 bytes por characteristic.

## 6. Limitaciones — léelo antes de fiarte al 100%

1. **Ya está probado contra el robot físico** (07/11/2026): LED (off/on/flash/fade), ruedas (adelante, atrás y giros) y el escalado de los servos salen del desensamblado **y** se han confirmado con el robot delante. Pero **el rango de los servos no se ha barrido de extremo a extremo**: los límites vienen de los clamps de la app, no de medir el tope mecánico, y el signo "hacia arriba" de cada brazo hay que calibrarlo a ojo.
2. **Los ángulos de servo son "grados de la app"**, no necesariamente los grados mecánicos reales: la app los recalibra con los offsets; si tu robot tiene los brazos en otra posición, calibrar es cosa tuya.
3. **La app manda el paquete cada ~50 ms.** En la práctica, con `bleak` sobre BlueZ, **cada escritura con respuesta tarda ~150-200 ms**, así que el refresco real es de ~5 Hz, no de 20. Y no es opcional: **si dejas de mandar, el firmware devuelve los brazos a su reposo** (§ 2.1.1). La consola lo hace con un keepalive; si usas la API, mándalo tú.
4. **El módulo BLE del robot se duerme.** Tras un rato sin conexión el HM-10 deja de anunciar y hay que **apagar y encender el robot** para volver a conectarlo. Si el programa muere sin cerrar el BLE, el enlace se queda "zombi" en BlueZ y el robot no admite conexiones nuevas: `bluetoothctl disconnect 64:E0:39:2D:90:80` (o `remove` + `scan on`) lo arregla. El cliente ya hace reintentos y mantiene el escaneo activo durante la conexión (BlueZ borra el dispositivo del árbol si paras el descubrimiento antes de conectar).
5. **Los bytes 10-19** son los más específicos: los copio literalmente, pero no sé qué hace el firmware con ellos. No los toques salvo que sepas lo que haces.
6. **La app oficial y tu robot siguen siendo válidos.** Nada de esto modifica el firmware; es solo hablar el idioma que el robot ya entiende.

## 7. Scratch (plugin)

Hay un **plugin de Scratch 3** para manejar el robot con bloques:

```
  Scratch (navegador)  --HTTP-->  airo_ble/server.py  --BLE-->  AIRO
```

El navegador no puede hablar BLE, así que el plugin llama a un **servidor local en Python** que sí puede.

```bash
python3 -m airo_ble.server       # http://localhost:8765
```

- `airo_ble/scratch3_airo/airo.js` — la extensión con los bloques (mover, girar, LED, brazos, kata, estado).
- `airo_ble/scratch3_airo/test.html` — una página con botones para probar el servidor sin Scratch.
- `airo_ble/scratch3_airo/README.md` — cómo cargarlo en TurboWarp.

Bloques: `mover el AIRO hacia delante/atras`, `girar a la izquierda/derecha`, `parar`, `esperar`, `poner la luz en on/off/flash/fade`, `poner el brazo en posicion arriba/abajo/medio/golpe/guardia`, `poner el (hombro/codo) del brazo a N grados (en N segundos)`, `mover la articulacion a N grados`, `hacer una kata de karate`, `resetear`, `estado del AIRO` y `¿está conectado?`.

**Dos cosas pratiques**:

- **El puerto**: por defecto es el 8765, pero puede estar ocupado por otra
  cosa. Se puede arrancar en otro (`python3 -m airo_ble.server
  --port 8766`) y **no hay que tocar la extension**: esta prueba los puertos
  8765-8768 y se queda con el primero que conteste con el estado del AIRO
  (el `API` fijo se sustituyo por esa deteccion, porque el puerto de por
  defecto no siempre esta libre).
- **Solo un cliente BLE**: el robot solo admite una conexion. Si la API web
  (`:8100`) esta conectada, el puente de Scratch no puede conectarse al
  robot. Para usar uno u otro, hay que dejar el otro apagado.

---

## 8. La interfaz web (para programar en bloques)

Hay una interfaz gráfica en <http://localhost:8100> para **programar al robot con bloques**, pensada para niños: nada de grados, bytes ni velocidades raras.

```bash
pip install -e ".[api]"
cd web && npm install && npm run build     # compila la interfaz (React + Vite)
python3 -m uvicorn airo_ble.api.main:app --port 8100
```

Tres columnas:

| Columna | Qué hay |
|---|---|
| **1 · Elige los bloques** | toca un bloque y se añade al programa |
| **2 · Tu programa** | el orden, las opciones y el botón **¡Vamos!** |
| **3 · Mira al robot** | un robot dibujado que se mueve con el estado real |

Los bloques son: `Avanza`, `Atras`, `Gira`, `Mueve el brazo`, `Luz`, `Espera`, `Kata de karate`, `Para` y `Repite`. Las opciones van en palabras: la velocidad es *poquito / normal / mucho* (los tres únicos niveles que tiene el robot) y el tiempo es *un instante / un segundo / dos segundos / tres segundos / cinco segundos / un buen rato*.

Hay dos modos, en la cabecera:

- **normal**: lo de siempre. En el bloque del brazo eliges el lado y la pose.
- **avanzado**: además puedes elegir **qué articulación** mover (hombro, codo o
  las dos), si el destino es una pose o un **ángulo exacto**, y el **tiempo** del
  movimiento (de golpe, o lento en rampa durante X segundos). Lo que elijas se
  ve en el resumen de "Lo que va a hacer".

El bloque del brazo tiene su propio deslizador de tiempo, con la opcion
*de golpe* al principio (0 segundos: el servo va a su velocidad) y el resto de
movimientos lentos. En modo normal tambien se puede elegir el tiempo.

### 8.1 El modelo de acciones (como se mueve el robot)

El protocolo no tiene ni "velocidad de brazo" ni "movimiento lento": solo hay
un byte por articulacion con el destino. Todo lo de "ir despacio", "esperar" o
"parar" lo pone la libreria por encima. Estas son las reglas que se siguen
(`airo_ble/arms.py` y `airo_ble/session.py`):

| Regla | Que hace | Por que |
|---|---|---|
| **Duracion minima: 1 s** | ninguna accion de brazo dura menos de 1 segundo | si se manda el destino nuevo antes de tiempo, el servo cambia de destino a medio camino y el primer movimiento **no llega a verse nunca**: los movimientos se confunden y uno se come al siguiente |
| **Movimiento lento = rampa** | con `segundos` > 0, el destino va viajando hasta el servo (20 escalones por segundo) durante ese tiempo | el servo no sabe que le estan dando una rampa: simplemente persigue un destino que se mueve. El tope de lo fino lo pone la resolucion del byte (uno son 8,5 grados) |
| **De golpe** | con `segundos` = 0, un solo salto al destino y se espera lo que tarde el servo | es el servo a su velocidad natural |
| **Parar siempre** | cada bloque de movimiento emite un `parar` detrás, y el programa entero termina parando | si no, el robot se queda andando o girando para siempre |
| **Alcance** | una accion puede ser de `todo`, solo el `hombro` o solo el `codo` | para mover una articulacion suelta |
| **Objetivo** | una pose nombrada (`arriba`, `abajo`...) **o** un angulo exacto | el angulo manda sobre la pose; con las dos articulaciones (`todo`) hace falta una pose, porque un solo angulo para hombro y codo no significaria nada (se rechaza con un 422) |
| **Paralelismo** | los dos brazos se mueven en el **mismo paquete** (destinos distintos permitidos) | es lo unico que el protocolo permite: un byte por articulacion, todos a la vez |
| **Cola FIFO** | los programas se ejecutan uno detras de otro; el segundo **no cancela** al primero | antes pulsar "ejecutar" dos veces dejaba al robot a mitad de un movimiento |

Las **tres entradas** (la API web, la consola y el puente de Scratch) usan el
mismo modelo y la misma rampa (`arms.pasos_rampa()`):

| Entrada | Como se pide |
|---|---|
| API web | `{"tipo": "brazo", ..., "articulacion": "codo", "angulo": 90, "segundos": 3}` |
| Consola | `brazo der codo 90 3` (para una pose: `brazo der arriba 3`) |
| Scratch | `{"type": "arm", "side": "left", "joint": "codo", "angle": 90, "duration": 3}` |

Ejemplo de una accion de brazo en la API:

```json
{"tipo": "brazo", "lado": "derecho", "pose": "arriba",
 "articulacion": "codo", "angulo": 90, "segundos": 3}
```

Lo que sale por BLE (byte del hombro derecho, byte 6) con `segundos: 3` frente
a `segundos: 0`:

```
lento (3 s):  20 20 20 19 19 19 19 19 19 19 18 18 ... 15 15 14 14 ... 13 13
de golpe:     13
```

Y el alcance se ve en que bytes se tocan: solo el codo -> solo cambia el byte 7;
solo el hombro -> solo el byte 6.

### 8.1.1 Comprobado con el robot delante (2026-11-10)

Dos medidas, con el robot real y la camara:

| | De golpe | Lento (rampa de 4 s) |
|---|---|---|
| Bytes que salen | un solo salto: `13` | escalon a escalon: `20 19 19 19 18 18 ... 15 15 14 14 ... 13 13` |
| Lo que ve la camara | **un** fotograma (0,8 s): todo el recorrido | **cinco** fotogramas seguidos (4 s): el brazo sube poco a poco |

El "de golpe" se ve entero en la foto de las 17:36:59 y en la siguiente
(17:37:08) el brazo ya no se ha movido. La rampa se mueve entre las 17:37:15
y las 17:37:19, con el brazo a medio camino en las fotos intermedias.

De la segunda medicion sale tambien la **velocidad real del servo**: el
recorrido completo (170 grados del codo) se hace en **menos de un segundo**,
asi que los 150 grados/s que usa el modelo (`arms.SERVO_VELOCIDAD`) son una
estimacion prudente.

Evidencia: las fotos del barrido (no se publican) y el script
`tools/hardware/medida_final.py` (el que imprime las horas de reloj, para alinear
las fotos con los comandos).

### 8.1.2 La interfaz: bugs, móvil y control (2026-11-10, tarde)

La interfaz se reviso entera con capturas reales (Chromium headless) y se
arreglaron cuatro cosas que estaban **claramente rotas**, mas un monton de
comodidades para quien programa:

| Que estaba roto | Como se ha resuelto |
|---|---|
| Los botones ▲▼✕ **tapaban el deslizador** del tiempo (estaban en `position: absolute` en la esquina del bloque) | los botones se han movido **a la cabecera del bloque**, en su sitio, con el numero al lado |
| El deslizador se veia como **una barra negra** sobre el bloque de color (`accent-color: #fff` no sirve sobre color) | el deslizador se dibuja a mano: pista semitransparente y boton blanco con borde (webkit y firefox) |
| La cabecera **se rompia en el movil**: el boton "Conectar" se salia de la pantalla | la cabecera es `flex-wrap` con dos filas (marca + estado / modo + boton) y en el movil se compacta |
| Los **brazos del robot se salian de su tarjeta** al girar | el robot se dibuja dentro de un marco con escala (0,78 en el escritorio, 1 en una sola columna) |

Y estas son las comodidades nuevas:

- **Arrastrar y soltar**: los bloques de la paleta se arrastran al programa (y
  se pueden soltar **dentro** de un "repetir"), y los bloques del programa se
  reordenan cogiendolos por el asa ⠿. Las franjas de soltado se ven mientras
  se arrastra.
- **Deshacer**: boton "↩ Deshacer" y <kbd>Ctrl</kbd>+<kbd>Z</kbd>, con un
  historial de estados (los cambios seguidos de un deslizador se funden en
  uno solo, para no tener que pulsar quince veces).
- **Ejemplo**: el boton "💡 Ejemplo" carga un programa que funciona a la
  primera (saludo con los dos brazos, dos golpes de karate, un giro y un paso).
- **Duracion estimada**: antes de darle a "Vamos!" se ve cuanto va a durar el
  programa, y cada bloque lleva su propio tiempo debajo.
- **Atajos de teclado**: <kbd>Ctrl</kbd>+<kbd>Enter</kbd> ejecutar,
  <kbd>Ctrl</kbd>+<kbd>Z</kbd> deshacer, <kbd>Esc</kbd> parar, y con un bloque
  seleccionado <kbd>Alt</kbd>+<kbd>↑</kbd>/<kbd>↓</kbd> para moverlo y
  <kbd>Supr</kbd> para borrarlo.
- **Paleta compacta**: en tablet y movil los bloques de la paleta pasan a
  rejilla (2-5 columnas) en vez de una columna que se comia la pantalla.

La duracion la dice el backend, no la interfaz: `POST /api/duracion` **simula**
el programa (igual que hace la ejecucion) y devuelve el total **y la duracion
de cada bloque**. La interfaz solo la pide y la enseña; si el servidor no
contesta, usa una estimacion rapida.

### 8.1.3 Guardar programas y funciones (2026-11-10, noche)

La cuarta columna ("4 · Guardado") guarda dos cosas en el **servidor**, en un
archivo JSON (`~/.airo/guardado.json`, se puede cambiar con la variable de
entorno `AIRO_GUARDADO`):

- **Programas**: el programa entero, con su nombre. "💾 Guardar" lo actualiza
  si ya estaba guardado; "Guardar como" crea una copia nueva.
- **Funciones**: un **trozo de bloques con nombre**, que se puede reutilizar.

Como se guarda en el servidor (y no en el navegador), no se pierde al recargar
la pagina, y se ve igual desde cualquier navegador de la misma maquina.

#### Como se hace una funcion

1. En el programa, se marca un bloque (clic en su cabecera) o varios
   (clic y **Mayusculas** en el ultimo).
2. Sale la barra "N bloques marcados": se le pone un nombre y se le da a
   "⚡ Guardar como funcion".
3. La funcion aparece en la columna de la derecha y se puede **arrastrar** al
   programa (o darle a "Usar").
4. "Editar" abre sus bloques en la columna del programa; al guardar, la
   funcion cambia **para todos los programas que la usan**.

#### Las llamadas son referencias, no copias

El bloque que aparece en el programa (el rayo) es una **referencia**: lleva
solo el id de la funcion, no sus pasos. El backend la **despliega** al
traducir el programa a pasos (`Traductor.bloque_a_pasos`).

Esto quiere decir que:

- si editas la funcion, **todos** los programas que la usan ejecutan la version
  nueva (no hay que volver a pegarla);
- si borras la funcion, los programas que la usan avisan ("esta funcion ya no
  existe") en vez de fallar en silencio;
- las funciones viajan **con** el programa en la peticion (`{"programa": ...,
  "funciones": {...}}`), porque el backend necesita sus bloques para
  desplegarla.

Y hay un **guard contra el bucle infinito**: si una funcion se llama a si
misma, se corta al quinto nivel y se avisa ("la funcion X se llama a si
misma"), en vez de dejar al servidor colgado.

### 8.1.4 Los "repetir" anidados (repetir dentro de repetir)

Un bloque "Repite" puede ir dentro de otro "Repite", y las veces se
multiplican: "repite 3" con dentro un "repite 2" que espera 1 segundo son
**6 segundos** (3 x 2 x 1).

En la interfaz:

- la mini paleta de dentro de un "Repite" ofrece **todos** los bloques,
  incluido el propio "Repite";
- se pueden arrastrar bloques dentro y fuera de un "Repite" que este dentro de
  otro;
- la duracion que se ve debajo de cada bloque ya tiene en cuenta todo el
  anidamiento (la calcula el backend, que expande los "repetir" al simular).

Ojo con el tope: tres niveles de "repite 50" son 125.000 pasos, asi que el
backend lo corta y avisa (tope de 1000 pasos).

### 8.2 La API

`api/` es un backend **FastAPI + Pydantic**. Los bloques son modelos Pydantic con discriminador (`api/models.py`), y `api/service.py` los traduce a los pasos que entiende la libreria.

| Ruta | Que hace |
|---|---|
| `GET /api/bloques` | el catalogo de bloques con su nombre bonito y sus opciones |
| `GET /api/estado` | el estado del robot (incluye `cola`: quantos programas esperan turno) |
| `POST /api/programa` | ejecuta un programa entero (devuelve `pasos`, `duracion` y `cola`) |
| `POST /api/bloque` | ejecuta un bloque suelto |
| `POST /api/duracion` | **no ejecuta nada**: dice cuanto duraria el programa y cada bloque |
| `GET /api/guardado` | lo guardado: los programas y las funciones |
| `POST /api/guardado/programa` | guarda (o actualiza) un programa |
| `DELETE /api/guardado/programa/{id}` | borra un programa guardado |
| `POST /api/guardado/funcion` | guarda (o actualiza) una funcion |
| `DELETE /api/guardado/funcion/{id}` | borra una funcion guardada |
| `POST /api/mover` | control manual de las ruedas |
| `POST /api/parar` | para el robot, el programa en curso **y vacia la cola** |
| `POST /api/conectar` / `api/desconectar` | gestion de la conexion |
| `WS /ws` | el estado en vivo (para la animacion) |

La `duracion` que devuelve la API **se simula**: se recorre el programa entero
calculando cuanto tarda cada movimiento (lo que tarde el servo en llegar, o el
tiempo pedido si el movimiento es lento), en vez de sumar tiempos a ciegas. Asi
la interfaz sabe cuando ha terminado el programa en vez de adivinarlo.

`POST /api/duracion` hace **la misma simulacion sin ejecutar nada**, y además
devuelve la duracion **de cada bloque** (`bloques: [2.0, 0.4, 1.0]`), que es lo
que la interfaz pone debajo de cada bloque. Los bloques se simulan uno detras de
otro, igual que se ejecutan: el segundo brazo tarda menos si el primero ya ha
dejado el servo cerca. No hace falta que el robot este conectado.

### 8.3 Como se dibuja el robot (el mapeo de angulos)

El robot de la tercera columna se dibuja con los **bytes de servo** que van al
firmware, asi que hay que deshacer el escalado de § 2.5. Eso vive en
`web/src/angulos.js`, que es el **espejo de `protocol.py`**:

```
byte   = |neutral + signo * angulo / 8.5|
angulo = signo * (byte - neutral) * 8.5
```

Tres cosas hacen que no valga una formula unica para las cuatro articulaciones:

| articulacion (fisica) | byte | signo | limites | neutral |
|---|---|---|---|---|
| `right_shoulder` | 6 | +1 | −60 .. 77 | 20 |
| `right_arm` | 7 | −1 | −25 .. 170 | 20 |
| `left_arm` | 8 | +1 | −25 .. 170 | 20 |
| `left_shoulder` | 9 | −1 | −60 .. 77 | **16** |

- el **signo**: los dos lados giran en sentidos opuestos,
- los **limites**: los hombros van de −60 a 77 y los codos de −25 a 170,
- el **neutral**: el byte que es "angulo 0" no siempre es el 20 (el hombro
  izquierdo, byte 9, va calibrado en 16, § 5.0.3). Por eso el estado de la API
  publica el cero de cada articulacion en `brazos.<articulacion>.neutral`.

El dibujo reparte los 137° mecanicos del hombro en 180° de pantalla (abajo =
colgando, arriba = en vertical) y el codo gira respecto al brazo (recto = −25°,
plegado = +170°). El lado izquierdo se dibuja al reves que el derecho.

> Antes la web usaba `angulo = ((byte - 20) / 20) * 60` para todo, lo que
> daba hasta 230° de error en los codos y ni siquiera dibujaba el codo.

**Las pruebas** de este mapeo estan en dos sitios:

```bash
cd web && npm test        # 30 tests de vitest (tabla de poses, espejo, limites)
python3 -m pytest tests/  # incluye test_web_angulos.py: el JS y protocol.py
                          # tienen que dar el MISMO byte en todo el rango
```

### 8.4 La libreria sigue siendo independente

`airo_ble` **no importa nada de la web**: es la libreria pura (protocolo, cliente BLE y sesion) y se puede instalar en cualquier proyecto:

```bash
pip install airo-ble
```

```python
from airo_ble.session import RobotSession

sesion = RobotSession()
await sesion.conectar()
await sesion.mover(izquierda=2, derecha=2, segundos=2)
```

La API web, la consola y el plugin de Scratch son *consumidores* de esa libreria, nada más.

---

## 9. Con qué versión funciona esto

- `it.clementoni.robot.airo` — la app oficial de AIRO 1.x (analizada el 07/11/2026).
- Funciona con cualquier build del firmware que acepte el mismo paquete de 20 bytes (es el formato desde la salida del robot).
- **AIRO PRO**: layout distinto, no aplica. Pídemelo y lo hago.

## 10. Estructura

```
airo/
├── airo_ble/
│   ├── protocol.py     # el protocolo en sí, sin dependencias (testeable)
│   ├── client.py       # cliente BLE con bleak
│   ├── console.py      # consola interactiva de comandos
│   ├── commands.py     # CLI de una vez (scan, drive, pose, led)
│   ├── arms.py         # poses de los brazos y qué lado se mueve
│   ├── server.py       # servidor local para el plugin de Scratch
│   ├── api/            # backend de la interfaz web (FastAPI + Pydantic)
│   ├── scratch3_airo/  # extension de Scratch 3 + pagina de pruebas
│   ├── calibration.json # calibracion por defecto de los brazos
│   └── py.typed        # la libreria viene con los tipos
├── web/                # interfaz React (Vite) — src/servos.js se GENERA desde protocol.py
├── tests/              # tests del protocolo, la consola, los brazos y el servidor
├── docs/               # esta guia + el desensamblado que prueba cada byte
├── tools/              # scripts de ingeniería inversa y de medicion con el robot
└── pyproject.toml      # las dependencias y los scripts de consola
```

> Todo lo que se instala (`pip install .`) vive dentro de `airo_ble/`. La
> calibración que se guarda con `calib guardar` va a
> `~/.config/airo-ble/calibration.json`; la del paquete es solo el valor por
> defecto.
>
> Los números del protocolo están **una sola vez**, en `airo_ble/protocol.py`.
> La web los usa también, así que `tools/gen_servos.py` genera
> `web/src/servos.js` a partir de ahí y `tests/test_web_angulos.py` comprueba
> que las dos copias dicen lo mismo.

## 11. Atribución

- El análisis es de la app de Clementoni/Ubisive, que es código propietario. Aquí solo se documenta el **protocolo de comunicación** para que puedas controlar tu propio robot: es el mismo tipo de trabajo que hacer un cliente propio para un dispositivo Bluetooth.
- La lib de BLE del plugin es `com.shatalmic.unityandroidbluetoothlelib.UnityBluetoothLE` (open source).
- `bleak` (MIT).
