# Plan de mejoras y lista de tareas — repo `airo`

> **Nota:** este documento es un **log de trabajo histórico**: cuenta lo que se
> hizo, con sus decisiones y sus errores. No es la guía de uso (eso está en
> [`protocolo.md`](protocolo.md)) ni la estructura actual del repo (eso está
> en el README). Los nombres de fichero que se mencionan son los de cuando se
> escribió cada entrada.

> **Estado: Fases 1, 2 (A+B+2.8+2.9+2.6), la tanda "roto y verificado" y el
> modelo de acciones APLICADAS.**
> El 2026-11-10, con el robot delante y una cámara, se ha corregido el lado
> físico de los brazos: la tabla de la guía tenía el byte 6 y el 9 cambiados.
> Revisión realizada sobre la rama de trabajo actual de `/home/jordi/airo`.
> Las ruedas han sido verificadas contra el desensamblado ARM64 y **son correctas**:
> **no se ha tocado `protocol.py`**, así que el encoding de motores sigue siendo
> byte a byte el que coincide con el firmware.
>
> **Decisiones ya tomadas por el usuario (2026-11-10):**
> - El robot tiene **4 servos**: hombro + codo por cada brazo. El enum `Joint`
>   completo es válido.
> - El enum `Joint` usa los nombres **físicos** del robot, verificados con
>   el robot delante (tarea 2.9): byte 6 = hombro **derecho**, 7 = codo
>   derecho, 8 = codo izquierdo, 9 = hombro izquierdo. Las **ruedas** sí
>   están cruzadas respecto a la app; los brazos no.
> - Tope de **1000 pasos** por programa en la API web.
>
---

## 0.k. El puente BLE con un ESP32-S3 — resumen

**`firmware/esp32/*` (nuevo), `airo_ble/bridge.py` (nuevo), `tests/test_bridge.py`
(nuevo), `tests/test_firmware_esp32.py`, `docs/plan-esp32.md` (nuevo).**

El plan completo, con las fases y las cuentas, está en
[`plan-esp32.md`](plan-esp32.md). Aquí solo el resumen de **qué se ha hecho y
qué queda**.

### La decisión

El robot se puede hablar **a través de un ESP32-S3** en vez de por el Bluetooth
del portátil. El chip va al lado del robot, habla BLE con él, y el portátil le
manda los bytes por HTTP.

Lo importante es que **el ESP32 no sabe nada del protocolo AIRO**: solo escribe
bytes en la characteristic `FFF1`. Los 20 bytes los sigue construyendo
`airo_ble/protocol.py`, así que hay **una sola fuente de la verdad** y el
firmware no se queda obsoleto cuando el protocolo cambie.

| | Antes | Después |
|---|---|---|
| Quién habla BLE | el portátil | el ESP32 |
| Quién construye el paquete | el portátil | el portátil (igual) |
| Bluetooth en el portátil | obligatorio | opcional (`AIRO_BRIDGE_URL`) |

### Lo que hay

- **Firmware** (MicroPython 1.29.0, build `SPIRAM_OCT` para la PSRAM octal de la
  N16R8): cliente BLE, servidor HTTP mínimo, WiFi y refresco del paquete.
- **Cliente Python** (`airo_ble/bridge.py`): `BridgeRobot`, con la misma interfaz
  que `AiroRobot`, y la fábrica `crear_robot()` que decide el camino según
  `AIRO_BRIDGE_URL`. Es el **único** punto donde se decide, así que la consola,
  la API web, el plugin de Scratch y la CLI se comportan igual sin tocar su
  código.
- **Tests**: el servidor HTTP del firmware de verdad (con un BLE de mentira)
  contra el cliente de verdad. Sin placa y sin robot.

### Las rarezas de MicroPython (todas comprobadas contra la placa)

No salen en la documentación y hay que tenerlas en el bolsillo:

| Lo que parece | Lo que hay |
|---|---|
| `bluetooth.UUID16(0xFFF0)` | No existe: es `bluetooth.UUID(0xFFF0)` |
| `str(uuid)` → `"0000fff0-…"` | Es `"UUID(0xfff0)"`: mejor comparar con `bytes(uuid)` |
| `bluetooth._IRQ_SCAN_RESULT` | Las constantes `_IRQ_*` no existen: los eventos van numerados |
| Conexión hecha → IRQ 1 | En el port NimBLE, `gap_connect` avisa con el **7** |
| `gap_scan(0)` para parar | No: `gap_scan(0)` deja el escaneo para siempre. Se para con `gap_scan(None)` |
| Descubrir `UUID(0xFFF0)` | El robot lo registra con UUID de 128 bits: hay que descubrir **todo** y filtrar |
| Dos escaneos a la vez | NimBLE contesta `EALREADY`: solo se admite uno |
| `print(..., flush=True)` | No existe en MicroPython |

### Lo que falta

**El robot no se ha movido todavía.** La placa lo ve (`AIRo` =
`64:E0:39:2D:90:80`), se conecta a él y descubre `FFF0`/`FFF1`, pero **falta la
escritura real de los 20 bytes**: el robot estaba apagado (su módulo HM-10 solo
se anuncia unos segundos tras encenderlo) y no se ha podido comprobar que se
mueve.

También falta: un job de CI propio del firmware (aunque `ruff` y `pyright`
ya lo cubren, porque `firmware/` está en la configuración) y comprobar el
mDNS: el port del ESP32 ya lo trae (el nombre se pone antes de activar la
interfaz), pero en la red de pruebas el tráfico mDNS entero no pasaba, así que
el camino que funciona es la IP.

---

## 0.j. Los "repetir" anidados no funcionaban — resumen

**Reportado por el usuario el 2026-11-10, noche: "los repite dentro de los repite no parecen funcionar".**

### El diagnostico

El backend **ya estaba bien**: `Traductor.bloque_a_pasos` expande los "repetir"
recursivamente, y el API hacia la cuenta correcta (3 x 2 x 1 s = 6 s, 7 pasos).
El fallo estaba **solo en la web**:

`insertarEnArbol(bloques, padreId, ...)` (en `web/src/bloques.js`) buscaba el
"repetir" destino **solo en el primer nivel** del arbol:

```js
return bloques.map((b) => {           // <-- solo la raiz
  if (b.id !== padreId) return b;     // <-- si el repetir estaba dentro de
  ...                                 //     otro, nunca se encontraba
});
```

Consecuencia: al meter un bloque dentro de un "repetir" **anidado** (dentro de
otro "repetir"), no se insertaba nada y no pasaba nada visible. Por eso parecia
que los "repetir" de dentro no funcionaban: en realidad no se podia meter nada
dentro.

Ademas, la mini paleta de dentro de un "repetir" **excluia** el propio bloque
"Repite", asi que un "repetir" dentro de otro solo se podia hacer arrastrando
(no con un clic).

### El arreglo

| # | Arreglo | Donde |
|---|---|---|
| RJ-01 | `insertarEnArbol` recorre **todo** el arbol (y si no encuentra el destino, devuelve la lista sin tocar) | `web/src/bloques.js` |
| RJ-02 | La mini paleta ofrece tambien "Repite" | `web/src/main.jsx` |
| RJ-03 | Al soltar, se limpia el estado de arrastre (el `dragend` no llegaba porque React redibuja el nodo del que se arrastra) | `web/src/main.jsx` |

### Evidencia (`tools/hardware/probar_repetir.py`, con el navegador)

| Prueba | Resultado |
|---|---|
| Meter un "repetir" dentro de otro | repetir > repetir ✓ |
| Meter una "Espera" en el "repetir" de dentro | antes: **0 bloques** (nada) → ahora: **1** ✓ |
| Duracion con repetir 3 > repetir 2 > espera 1 s | "⏱ dura unos 6 s" (3 x 2 x 1) ✓ |
| La misma con una espera de 3 s | "⏱ dura unos 18 s" ✓ |
| La misma con una espera de 8 s | "⏱ dura unos 48 s" ✓ |
| Sacar un bloque del "repetir" de dentro (arrastrando) | raiz 1 → 2, dentro 2 → 1 ✓ |

Y en el backend, un test nuevo: `test_los_repetir_anidados_se_multiplican`
(6,0 s y 7 pasos).

---

## 0.i. Guardar programas y funciones — resumen

**`airo_ble/api/guardado.py` (nuevo), `airo_ble/api/models.py`, `airo_ble/api/service.py`, `airo_ble/api/main.py` + `web/src/*`.**

Decisiones del usuario (2026-11-10, noche): guardar en el **servidor** (un
archivo JSON), las funciones como **referencia** (no copias) y los programas
guardados y las funciones en una **columna nueva a la derecha**.

### Lo que hay

| # | Lo hecho | Donde |
|---|---|---|
| GU-01 | Archivo JSON con los programas y las funciones (`~/.airo/guardado.json`, variable `AIRO_GUARDADO`) | `airo_ble/api/guardado.py` |
| GU-02 | Escritura **atomica** (a un temporal y renombrar) y archivo roto no rompe la interfaz | `guardado._escribir_crudo` |
| GU-03 | Bloque `llamada`: una **referencia** al id de la funcion | `api/models.py` (`BloqueLlamada`) |
| GU-04 | El backend **despliega** la llamada al traducir a pasos | `service.Traductor.bloque_a_pasos` |
| GU-05 | Guard anti-bucle: una funcion que se llama a si misma se corta al 5º nivel | `MAX_PROFUNDIDAD_FUNCIONES` |
| GU-06 | Las funciones viajan **con** el programa (`{"programa":..., "funciones":...}`) | `PeticionPrograma` |
| GU-07 | Endpoints: listar, guardar, actualizar y borrar programas y funciones | `POST/DELETE /api/guardado/...` |
| GU-08 | Columna "4 · Guardado" con la lista de programas y de funciones | `web/src/main.jsx` |
| GU-09 | Marcar un trozo de bloques (clic y Mayusculas) y guardarlo como funcion | `web/src/main.jsx` |
| GU-10 | Editar una funcion en la columna del programa (y que cambien todos sus usos) | `web/src/main.jsx` |
| GU-11 | Arrastrar una funcion al programa = añadir una llamada | `web/src/main.jsx` |

### Evidencia

`tools/hardware/probar_guardado.py` lo prueba **en el navegador** (Playwright), de
punta a punta:

| Paso | Resultado |
|---|---|
| Programa de ejemplo | 8 bloques |
| Marcar clic + Mayusculas | 3 bloques marcados |
| Guardar como funcion | 1 funcion en la lista ("⚡ Saludo") |
| Usarla en el programa | un bloque "Saludo" y el resumen dice "9. Llama a «Saludo»" |
| Editar la funcion | "Editando «Saludo»" |
| Guardar el programa | "📄 Mi programa bueno" |
| **Recargar la pagina** | siguen ahi el programa y la funcion (se guardan en el servidor) |
| Cargar el programa | 9 bloques |

Y la semantica de referencia, con la API:

```
duracion con la llamada:                4.07 s (por bloque: [3.07, 1.0])
duracion tras editar la funcion:        9.07 s (por bloque: [8.07, 1.0])
```

### Decisiones que se tomaron por el camino

- La llamada lleva el **id** de la funcion, no su nombre: asi se puede
  renombrar la funcion sin romper los programas que la usan.
- Las funciones se despliegan **en el backend**, no en la interfaz: asi la
  consola, Scratch y la web ejecutan exactamente lo mismo.
- El boton "Guardar" **actualiza** el programa guardado (si el programa
  venia de "Cargar"), y "Guardar como" crea una copia nueva.

---

## 0.h. La interfaz grafica — resumen

**`web/src/main.jsx`, `web/src/styles.css`, `web/src/bloques.js`, `web/src/Robot.jsx`, `web/src/api.js` + `airo_ble/api/*`.**

Decisiones del usuario (2026-11-10): alcance "bugs + interaccion" (los cuatro
bugs, cabecera responsive, paleta compacta, arrastrar y soltar, deshacer,
boton de ejemplo y duracion estimada) y publico "ninos mayores (10+)": se
mantienen las palabras tecnicas (angulos, articulacion) y se anaden atajos de
teclado.

### Los cuatro bugs (todos confirmados en el navegador)

| # | Bug | Arreglo |
|---|---|---|
| UI-01 | Los botones ▲▼✕ (`position: absolute`) **tapaban el deslizador** | los botones pasan a la cabecera del bloque, en su sitio |
| UI-02 | El deslizador se veia como **barra negra** (`accent-color: #fff` sobre color) | pista y boton dibujados a mano (webkit + firefox) |
| UI-03 | La cabecera se rompia en movil (**"Conectar" fuera de pantalla**) | cabecera `flex-wrap` a dos filas, compacta en movil |
| UI-04 | Los **brazos del robot se salian de la tarjeta** al girar | el robot se dibuja en un marco con escala (0,78 / 1) |

### Lo nuevo

| # | Lo nuevo | Donde |
|---|---|---|
| UI-05 | Arrastrar y soltar (paleta → programa, reordenar, entrar y salir de un "repetir") | `bloques.js` (`quitarEnArbol`, `insertarEnArbol`, `moverBloque`) + `main.jsx` |
| UI-06 | Deshacer (boton + Ctrl+Z) con historial y fusion de cambios seguidos | `bloques.js` (`historialAplica`, `historialDeshace`) |
| UI-07 | Boton de ejemplo (programa que funciona a la primera) | `bloques.js` (`programaDeEjemplo`) |
| UI-08 | Duracion estimada antes de ejecutar (total y por bloque) | `POST /api/duracion` + `Traductor.duracion_por_bloque` |
| UI-09 | Atajos de teclado (Ctrl+Enter, Ctrl+Z, Esc, Alt+↑/↓, Supr) | `main.jsx` |
| UI-10 | Paleta compacta en tablet y movil (rejilla) | `styles.css` |

### Evidencia

El script `tools/hardware/capturar_interfaz.py` **comprueba el arrastrar y
soltar de verdad** con el navegador (Playwright) y escribe lo que
ha pasado en un JSON.

Comprobado con el navegador (Chromium headless, 2026-11-10):

| Prueba | Resultado |
|---|---|
| Deshacer (boton) | 10 bloques → 0 |
| Ctrl+Z | funciona |
| Arrastrar de la paleta al programa | 10 → 11 bloques |
| Reordenar un bloque | la lista cambia de orden |
| Arrastrar dentro de un "repetir" | 2 → 3 bloques dentro |
| Duracion mostrada | "⏱ dura unos 11,1 s" |
| Atajos | Ctrl+Z (8 → 0 bloques), Alt+↓ mueve el bloque seleccionado, Supr lo borra (8 → 7), Ctrl+Enter ejecuta |

Ademas, la duracion estimada se ha **comprobado contra el robot real**
(`tools/hardware/medir_duracion.py`, programa de luz + espera, que no mueve nada):

```
Lo que dice la API:  3.40 s (por bloque: [0.4, 3.0])
Lo que tarda de verdad: 3.42 s
Diferencia: 0.02 s (OK)
```

### Una trampa que costo tiempo

El arrastre se rechazaba siempre con un error invisible en consola:
`effectAllowed = 'copy'` en el origen y `dropEffect = 'move'` en el destino son
**incompatibles** (el navegador solo acepta el drop si el efecto pedido esta
permitido por el origen). Con `copyMove` en los dos sitios, el drop funciona.
La pista: registrar `dragstart`/`drop` con `page.on(...)` y ver que el `drop`
**no llegaba**.

---

## 0.g. El modelo de acciones — resumen

**`airo_ble/arms.py` + `airo_ble/session.py` + `airo_ble/api/*` + `web/src/*`.**

Lo que pidió el usuario, y como quedó:

| # | Lo pedido | Donde esta | Estado |
|---|---|---|---|
| 1 | Cada acción con **tiempo mínimo** | `arms.ESPERA_MINIMA = 1.0` (era 0,5) | ✅ |
| 2 | **Movimientos lentos** (que tarde X segundos) | `session._rampa()`: el destino viaja; `PASOS_POR_SEGUNDO = 20` | ✅ |
| 3 | **Parar** implícito al final de cada movimiento y del programa | `Traductor.bloque_a_pasos()` emite `parar` tras cada bloque de movimiento; `a_pasos()` añade el `parar` final | ✅ |
| 4 | **Paralelismo** entre brazos en una misma acción | `resolver_brazos()`: los dos lados (incluso con poses distintas) en el mismo paquete | ✅ |
| 5 | **Alcance** (hombro / codo / todo) y **objetivo** (pose o ángulo exacto) | `resolver_objetivos(lado, pose, articulacion, angulo)` + `BloqueBrazo` | ✅ |
| 6 | **Cola FIFO** de programas en vez de cancelar el anterior | `session._cola` + `_trabajador()`; `cola` en las respuestas de la API | ✅ |
| 7 | Interfaz con **modo normal / modo avanzado** | `web/src/main.jsx` (interruptor en la cabecera) + `web/src/bloques.js` (lógica pura, testeada) | ✅ |
| 8 | El bloque de brazo con **slider de tiempo** y opción "de golpe" | `DeslizadorTiempo` con `TIEMPOS_BRAZO` (0 = de golpe) | ✅ |

Decisiones que se tomaron al implementarlo:

- **El minimo es de 1 s, no de 0,5 s** (que es lo que usa la app oficial en su
  kata): con medio segundo los movimientos seguidos se confunden y uno se come
  al siguiente, que es justo lo que reportó el usuario.
- **Movimiento lento = rampa de bytes**, no "un salto y luego esperar": el
  servo no sabe que le estan dando una rampa, simplemente persigue un destino
  que se mueve. El tope de suavidad lo pone el byte (8,5 grados).
- **El ángulo exacto necesita una sola articulación**: con las dos, un ángulo
  no significaria nada (el hombro se movería al ángulo del codo). Se rechaza
  en el modelo (422), no a mitad del movimiento.
- **`duracion_de()` simula** el programa en vez de sumar tiempos a ciegas: la
  interfaz dice la verdad sobre cuando va a acabar.
- **La cola cuenta los que esperan**, no el que se está ejecutando.

### Evidencia

- Rampa: el byte del hombro derecho (byte 6) hacia "arriba" en 3 s es
  `20 20 20 19 19 19 ... 15 15 14 14 ... 13 13` (60 escalones); "de golpe" es
  un solo `13`.
- Alcance: "solo el codo" solo toca el byte 7; "solo el hombro" solo el 6.
- Paralelismo: derecha "arriba" + izquierda "abajo" sale en el mismo paquete
  como `{6: 13, 7: 0, 8: 17, 9: 7}` (con la calibracion del hombro izquierdo).
- Suites: **161 pytest + 56 vitest** en verde.

### Verificado en el robot (2026-11-10, 17:36-17:40)

Con el robot delante de la camara y las medidas alineadas por hora de reloj:

| | De golpe | Lento (rampa de 4 s) |
|---|---|---|
| Bytes por BLE | un solo salto (`13`) | `20 19 19 19 18 18 ... 15 15 14 14 ... 13 13` |
| Movimiento en la camara | **1** fotograma (0,8 s) | **5** fotogramas seguidos (4 s), con el brazo a medio camino en los intermedios |

Ademas: el recorrido completo (170 grados del codo) se hace en **menos de un
segundo**, asi que los 150 grados/s del modelo (`arms.SERVO_VELOCIDAD`) son
prudentes.

Evidencia: `tools/hardware/medida_final.py`, `tools/hardware/verificar_rampa.py`,
`tools/hardware/comparar_lento_vs_golpe.py`.

### Lo que falta

- Nada del modelo de acciones: esta todo verificado (por software y en el
  robot).

---

## 0.f. El lado físico de los brazos, verificado con el robot — resumen

**`airo_ble/protocol.py` + `airo_ble/calibration.json` + la guía + los tests.**

La guía decía que el byte 6 era el hombro **izquierdo** del robot (y el 9 el
derecho), y el enum `Joint` se renombró en la tarea 2.8 para seguirla. Con el
robot delante eso era **al revés**, y hacía que "brazo derecho" moviera el
brazo **izquierdo** del robot.

### La evidencia (tres fuentes independientes)

1. **La cámara** (2026-11-10). El robot estaba en la mesa, delante del
   ordenador. Se ve su **cara** (la pantalla oscura con los dos ojos azules) y
   el **LED del pecho**, que se enciende con el byte 1 del paquete: o sea que
   el robot **mira a la cámara**. Mirándolo de frente, su brazo derecho es el
   que queda a la **izquierda** de quien lo mira. Y el byte 6 levanta
   **precisamente** ese brazo.
2. **El desensamblado.** `docs/desensamblado/AiroControl_set_RightShoulderAngle.asm`:
   el "hombro derecho" de la app llama a `SetFirstServoMotor` → **byte 6**.
   Los hombros y los codos de la app **no** están cruzados con los del robot.
3. **La propia guía**, que se contradecía: su §2 verificaba en el hardware que
   el byte 6 levanta el brazo del lado derecho, pero su tabla de bytes lo
   ponía en el izquierdo. La tabla era lo que estaba mal.

### El arreglo

**Solo nombres.** Los bytes no se han movido ni un bit:

| Byte | Antes (mal) | Ahora | Signo | Límites |
|---|---|---|---|---|
| 6 | `LEFT_SHOULDER` | **`RIGHT_SHOULDER`** | +1 | −60 .. 77 |
| 7 | `LEFT_ARM` | **`RIGHT_ARM`** | −1 | −25 .. 170 |
| 8 | `RIGHT_ARM` | **`LEFT_ARM`** | +1 | −25 .. 170 |
| 9 | `RIGHT_SHOULDER` | **`LEFT_SHOULDER`** | −1 | −60 .. 77 |

| Fichero | Cambio |
|---|---|
| `airo_ble/protocol.py` | Los nombres del enum `Joint` (y sus valores) se intercambian; `SERVO_LIMITS` y `SERVO_SIGN` siguen a su byte. |
| `airo_ble/calibration.json` | El cero en 16 se queda en el byte 9, que ahora se llama `left_shoulder`. |
| `airo_ble/arms.py`, `console.py`, `session.py` | Comentarios y textos de ayuda. |
| `web/src/angulos.js` | La tabla de articulaciones (byte ↔ nombre ↔ signo ↔ lado). |
| `web/src/styles.css` | `.robot-brazo-der` sale ahora a la **izquierda** de la pantalla: el robot se dibuja de frente, así que su brazo derecho se ve a la izquierda. El dibujo **no cambia** de aspecto: antes ya coincidía por casualidad. |
| `protocolo.md`, `README.md` | La tabla de bytes, la nota del cruce (las ruedas sí están cruzadas; los brazos no) y la tabla de poses. |
| `tests/*` | Los tests fijan los **bytes**, no los nombres: se adaptan y siguen fijando lo mismo. |

La suite sigue en **138 tests** (pytest) + **31** (vitest), y los bytes de cada
pose son los de siempre: `arriba` → bytes 6/7 = 13/0 y 8/9 = 40/23.

### Reverificación final en el robot (2026-11-10, tarde)

Con el robot otra vez delante de la cámara se hizo la comprobación **por el
camino público** (lo que ve el usuario cuando dice "brazo derecho arriba"), con
el paquete **interceptado** para ver los bytes que salen de verdad:

| Orden | Bytes que salen | ¿Qué brazo sube? |
|---|---|---|
| `brazo derecho arriba` | 6=`0x0d` (13), 7=`0x00` (0) | el **derecho del robot** (el de la izquierda de quien lo mira) |
| `brazo izquierdo arriba` | 8=`0x28` (40), 9=`0x17` (23) | el **izquierdo del robot** |

El robot enseña la cara (visor turquesa), así que el lado se lee sin
ambigüedad. **El fix queda verificado en el hardware.**

Las 5 poses de la app se comprobaron igual contra el robot y coinciden
**exactamente** con la tabla de la guía:

```
medio    -> hombroDer=20  codoDer=20  codoIzq=20  hombroIzq=16
arriba   -> hombroDer=13  codoDer=00  codoIzq=40  hombroIzq=23
abajo    -> hombroDer=29  codoDer=23  codoIzq=17  hombroIzq=07
golpe    -> hombroDer=13  codoDer=23  codoIzq=17  hombroIzq=23
guardia  -> hombroDer=13  codoDer=09  codoIzq=31  hombroIzq=23
```

### Hallazgo nuevo: el codo solo usa el tramo 0..23 (y 17..40 en el otro lado)

Mandando bytes **crudos** al codo derecho con el hombro arriba, los bytes
**23, 30 y 40 dan el mismo resultado** (el codo ya está en su tope), mientras
que 0, 10 y 20 se ven claramente distintos:

| Byte del codo | Rango con efecto | Fuera no se mueve |
|---|---|---|
| 7 (derecho) | **0..23** | 24..40 |
| 8 (izquierdo) | **17..40** | 0..16 |

Es consecuencia de los límites del codo (−25..170) con la escala de 8,5° por
byte. La app oficial nunca manda esos bytes (recorta el ángulo **antes** de
escalar), así que no es un bug: solo importa si se mandan bytes a pelo con
`set_raw_servo()`. Documentado en `protocolo.md` § 2.5.

### Lo que sigue SIN resolver (tarea 2.11)

La **geometría visual** exacta (con qué ángulo se ve el antebrazo para un byte
dado del codo, y con qué ángulo real gira el hombro) no se ha podido cerrar:
la escena estaba a contraluz y las piezas del brazo medían 30-60 px en
pantalla. Las medidas dan un **desvío constante de ~30°** en el codo (el
antebrazo real no queda alineado con el brazo superior ni en el "recto" de la
app) y sugieren que el hombro llega a "colgado" antes del ángulo +77 de la
app, pero con ±20-30° de margen.

**No se ha tocado el dibujo de la web** por eso: hoy implementa el modelo de
ángulos de la app oficial (que es la mejor referencia disponible) y cambiarlo
con una medición dudosa lo dejaría peor. Queda como tarea abierta, con la
condición de repetir la medición con luz decentemente y el robot más cerca.

---

## 0.e. El mapeo de angulos de la web — resumen

**`web/src/angulos.js` (nuevo) + `web/src/Robot.jsx` + `web/src/styles.css` + `airo_ble/session.py`.**

Antes, `Robot.jsx` pasaba el byte del servo a grados con una formula fija para
las cuatro articulaciones:

```js
const angulo = (byte) => Math.round(((byte - 20) / 20) * 60);
```

Esa formula solo valia para un caso, y el dibujo se equivocaba:

| articulacion | angulo real | byte | lo que se dibujaba | error |
|---|---|---|---|---|
| hombro izquierdo | −60° | 13 | −21° | +39° |
| hombro izquierdo | +77° | 29 | +27° | −50° |
| codo izquierdo | −25° | 23 | +9° | +34° |
| codo izquierdo | +170° | 0 | −60° | −230° |

Y ademas **el codo no se dibujaba**: `Robot.jsx` solo leia los dos hombros.

Ahora el mapeo vive en `web/src/angulos.js`, que es el espejo de
`airo_ble/protocol.py`:

```
byte   = |neutral + signo * angulo / 8.5|
angulo = signo * (byte - neutral) * 8.5
```

con el **signo** y los **limites** de cada articulacion (hombros −60..77, codos
−25..170) y el **neutral** de la calibracion, que ya no es 20 en todas: el
hombro derecho viene calibrado en 16, y sin ese dato el hombro derecho se
dibujaba con 34° de error. Por eso el estado de la API publica ahora el cero
de cada articulacion (`brazos.<articulacion>.neutral`): es lo que la web
necesita para deshacer el escalado del servo.

**El dibujo.** El hombro reparte sus 137° mecanicos en 180° de pantalla (abajo
= colgando, arriba = en vertical) y el codo gira respecto al brazo (recto =
−25°, plegado = +170°). El lado izquierdo se dibuja al reves que el derecho.

| Fichero | Cambio |
|---|---|
| `web/src/angulos.js` | **Nuevo**: tabla de articulaciones, `byteAAngulo()`, `anguloAByte()`, `anguloDeEstado()` y las rotaciones de pantalla. |
| `web/src/Robot.jsx` | Usa el modulo y dibuja **hombro y codo** de los dos lados. |
| `web/src/styles.css` | `.robot-antebrazo`: el antebrazo que cuelga del codo. |
| `airo_ble/session.py` | El estado publica el `neutral` de cada articulacion. |

**Las pruebas** (30 de vitest + 4 de pytest):

- `web/src/angulos.test.js` (**vitest**, `cd web && npm test`): la tabla de
  poses de la guia § 5.0.1 byte a byte, el espejo de los dos lados, los limites
  mecanicos, la ida y la vuelta (byte → angulo → byte) y las rotaciones.
- `tests/test_web_angulos.py` (**pytest**): el JS y `airo_ble.protocol` tienen
  que dar **el mismo byte** para los cuatro brazos y todo su rango mecanico, y
  el estado tiene que publicar el `neutral` de cada articulacion. Se salta si
  no hay `node` instalado.

Comprobado que las pruebas **muerden**: cambiando el signo del hombro derecho
en el modulo JS, las dos pruebas de pytest fallan al instante.

**Mirado en el navegador** (chromium headless sobre la web real): las poses
`arriba`, `abajo`, `guardia`, `golpe` y `medio` salen con el hombro y el codo
en su sitio y los dos lados simetricos.

---

## 0.d. Migración a `lifespan` — resumen

**`airo_ble/api/main.py` + `pyproject.toml`.**

```python
@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    tarea = asyncio.create_task(_conectar_en_segundo_plano())
    try:
        yield
    finally:
        tarea.cancel()
        await asyncio.gather(tarea, return_exceptions=True)
        await servicio.desconectar()

app = FastAPI(..., lifespan=lifespan)
```

Tres cosas, no solo el `deprecated`:

1. **Los avisos desaparecen.** La suite pasa a **0 avisos** de deprecación.
2. **La tarea de reconexión ya no se fuga.** Con `@app.on_event("startup")` se
   creaba con `asyncio.create_task()` sin guardar la referencia y **nadie la
   cancelaba**: se quedaba reintentando la conexión para siempre, incluso
   después de apagar el servidor. Ahora el apagado la cancela.
3. **La suite va 17× más rápido**: de **53 s a 3 s**. Ese tiempo era,
   literalmente, esperar a que el `TestClient` se apagara con la tarea
   colgada.

**Guarda permanente** en `pyproject.toml`:

```toml
filterwarnings = [
    "error::DeprecationWarning:airo_ble.*",
    "error::PendingDeprecationWarning:airo_ble.*",
]
```

Los avisos que salen del **nuestro** código son un error de test; los de
terceros siguen siendo avisos (para no depender de ellos). Comprobado:
reintroducir un `@app.on_event` hace fallar la suite al instante.

---

## 0.c. Robustecimiento BLE del cliente — resumen

**Errores verificables, escaneo que no crece, ritmo de escritura correcto y reconexión.**

| Fichero | Cambio |
|---|---|
| `airo_ble/client.py` | Jerarquía de errores tipada: `AiroError` → `AiroNotFound`, `AiroNotConnected`, `AiroConnectionError`, `AiroWriteError`. |
| `airo_ble/client.py` | `_seen` pasa de lista a dict `direccion -> (dispositivo, rssi, momento)`. Se queda con el mejor RSSI y descarta anuncios viejos. |
| `airo_ble/client.py` | El ritmo de escritura se aplica **dentro** del lock y `_last_write` se actualiza **después** de escribir. `send()` y `send_raw()` comparten `_escribir()`. |
| `airo_ble/client.py` | `connect()` es idempotente y comprueba `is_connected` al conectar. Nuevo `reconnect()`: cierre limpio + volver a escanear. |
| `tests/test_client_robusto.py` *(nuevo)* | 19 tests con un `bleak` falso: errores por tipo, escaneo acotado, ritmo con envíos concurrentes, `send_raw`, reconexión. |

**Por qué importa.** Todo se lanzaba como `RuntimeError` con el mensaje en
español, así que no se podía distinguir "el robot no está" de "no conecté" de
"se colgó la escritura" sin leer el texto. Y el ritmo de escritura se
calculaba **antes** de escribir, de modo que dos envíos concurrentes creían
que podían escribir los dos seguidos: el HM-10 del robot se quejaba y el
enlace se caía.

```python
from airo_ble import AiroRobot, AiroNotFound, AiroNotConnected, AiroWriteError

try:
    await robot.send(cmd)
except AiroNotConnected:
    ...   # no se ha conectado
except AiroWriteError:
    ...   # el módulo se ha dormido: apagar y encender
```

---

## 0.b. Tanda "roto y verificado" — resumen

**Empaquetado, tope de pasos y bucle de reconexión. Sin robot.**

| Fichero | Cambio |
|---|---|
| `pyproject.toml` | `packages = ["airo_ble", "airo_ble.api", "airo_ble.scratch3_airo"]`. Entry points a `airo_ble.console:main` y `airo_ble.server:main`. `calibration.json` y la extensión de Scratch como *package data*. |
| `airo_ble/api/` *(movido desde `api/`)* | La API web ahora es parte del paquete: `uvicorn airo_ble.api.main:app`. |
| `airo_ble/server.py` *(movido desde `airo_server.py`)* | El puente de Scratch, dentro del paquete. `scratch3_airo/` también. |
| `airo_ble/scratch3_airo/` *(movido)* | La extensión de Scratch viaja con el paquete (se sirve por HTTP al instalarlo). |
| `airo_ble/calibration.json` *(movido)* | La calibración por defecto es *package data*. La del usuario va a `~/.config/airo-ble/calibration.json` y tiene prioridad. |
| `airo_ble/api/service.py` | `MAX_PASOS = 1000`. El corte se comprueba **dentro** del bucle de "repetir". `ProgramaDemasiadoLarga` con un mensaje claro. |
| `airo_ble/api/main.py` | Los endpoints `/api/programa` y `/api/bloque` devuelven ese error con `ok: false` en vez de un 500. |
| `airo_ble/session.py` | `_reconectar()` desconecta **una vez** y guarda el error **más reciente**. `espera_reconexion` configurable. |
| `airo_server.py` | Queda como atajo en la raíz (no se instala): `python3 airo_server.py`. |
| `tests/test_session.py` *(nuevo)* | 4 tests del bucle de reconexión. |
| `tests/test_api.py` | 5 tests del tope de pasos. |

**Antes** (verificado construyendo un wheel e instalándolo en un venv limpio):

```
$ airo-server --help
ModuleNotFoundError: No module named 'airo_server'
```

**Ahora:**

```
airo-console  OK
airo-server   OK
calibracion desde el paquete -> {LEFT_SHOULDER: 20, LEFT_ARM: 20, RIGHT_ARM: 20, RIGHT_SHOULDER: 16}
import airo_ble.api.main -> OK
/scratch3_airo/airo.js -> HTTP 200, 7209 bytes
```

Y el tope de pasos, en vivo contra la API:

```
POST /api/programa (3x "repetir 50")
-> {"ok": false, "mensaje": "El bloque 'repetir' genera más de 1000 pasos. Quita repeticiones o quita el anidamiento."}
```

Antes generaba **125.000 pasos = 34,7 horas** de robot en una sola petición.

---

## 0. Fase 2 A+B aplicada — resumen

**6 archivos tocados + 1 nuevo módulo + 1 suite de tests nueva. 0 cambios en el protocolo.**

| Fichero | Cambio |
|---|---|
| `airo_ble/arms.py` *(nuevo)* | **Fuente única de verdad** de los brazos: `ARM_POSES`, `LADOS`, `resolver_lado()`, `resolver_brazo()`, `BrazoError`. |
| `airo_ble/console.py` | `_cmd_brazo` usa el resolver. Se borra su copia de la lógica y el código muerto `_ARM_SIDE`. `ARM_POSES` se re-exporta para no romper a quien lo importaba. |
| `airo_ble/session.py` | `brazo()` usa el resolver → **"ambos" mueve las cuatro articulaciones**. Además carga `calibration.json` al construirse y al conectar. |
| `airo_server.py` | `_apply` y `_kata` usan el resolver → **`side="left"` mueve el brazo izquierdo** (antes movía el derecho) y `"ambos"` mueve los dos. |
| `tests/test_arms.py` *(nuevo)* | **49 tests**: los bytes exactos de cada pose y cada lado, el vocabulario de "lado", y que las tres entradas (consola, API, Scratch) muevan **igual**. |

**Tests: 103 pasan** (54 tras la Fase 1 → 103).

### Por qué importa tener una sola fuente de verdad

La lógica de "qué lado se mueve" estaba **copiada en cuatro sitios** y cada
copia entendía "izquierda" de forma distinta:

| Sitio | Predicado | Se rompía con |
|---|---|---|
| `session.brazo` | `lado.startswith(("izq","left"))` | `"ambos"` → solo un brazo |
| `airo_server._apply` | `lado.startswith("i")` | `"left"` → el brazo **equivocado** |
| `airo_server._kata` | `lado.startswith("izq")` | incoherente con el resto |
| `console._cmd_brazo` | tabla de sinónimos | ✅ el único correcto |

Ahora las cuatro llaman a `resolver_brazo()`, que acepta los dos vocabularios
(`izq`/`izquierda`/`left`, `der`/`derecha`/`right`, `ambos`/`both`).

### Lo que NO se ha tocado (a propósito)

- **Los ángulos y el espejo.** La estrategia "el otro lado es el espejo con los
  MISMOS ángulos" es correcta: los bytes de los dos lados suman 40 (= 2 × centro)
  en las cinco poses. Solo estaba mal la detección del lado.
- **`protocol.py`.** Ni el enum, ni los signos, ni el escalado. El renombrado
  del enum (2.8) está pendiente, pero `tests/test_arms.py` fija los bytes de
  cada pose para que ese cambio sea mecánico y verificable.

### Un bug nuevo que salió al implementarlo

**La web no cargaba la calibración.** `load_calibration()` solo se llamaba en la
consola y en el puente de Scratch; la API web nunca la cargaba. Con el
`left_shoulder` en el byte 16, el mismo comando ponía el hombro izquierdo en el
byte **27** por la web y en el **23** por la consola — el robot se movía de
forma distinta según por dónde le mandaras la orden.

Ahora la calibración se carga al construir la sesión (es del **comando**, no de
la conexión) y también al conectar, por si se editó el fichero con el robot
encendido. Verificado en vivo: `/api/estado` devuelve `left_shoulder byte=16`
con el robot apagado, igual que la consola.

---

## 0.b. Fase 1 aplicada — resumen

**7 archivos tocados, 0 cambios en el protocolo (las ruedas no se han movido).**

| Fichero | Cambio |
|---|---|
| `airo_ble/console.py` | El watchdog **para** las ruedas (antes solo reenviaba el paquete). Nuevo `Console.parar()`. El watchdog no interrumpe un comando en marcha (kata). Apagado ordenado: para el robot antes de morir. |
| `airo_ble/session.py` | `_ejecutar` termina **siempre** con el robot parado (éxito, error o cancelación). `desconectar()` manda las ruedas a 0 antes de soltar el BLE. |
| `api/main.py` | `/api/mover` para el robot al acabar el tiempo (con `segundos=0` sigue siendo movimiento sostenido). |
| `api/service.py` | `Traductor.duracion_de()`: la duración real del programa. `RobotService.ejecutar()` devuelve `Resultado(pasos, duracion)`. |
| `api/models.py` | `RespuestaEjecucion.duracion`. |
| `web/src/main.jsx` | Usa la duración real en vez de los 1 500 ms fijos. `web/dist` reconstruido. |
| `airo_server.py` | Al apagar el servidor de Scratch, el robot se para antes de soltar el BLE. |
| `pyproject.toml` | `pytest-asyncio` + `asyncio_mode = "auto"`. |
| `tests/test_safety.py` | **Nuevo**: 15 tests de regresión de todo lo anterior. |

**Tests: 54 pasan** (antes 29 pasaban y 10 fallaban por falta de `pytest-asyncio`).

### Errores del análisis original que se han corregido

Al implementar la Fase 1 aparecieron **dos falsos positivos** del plan inicial
(importantes, porque apuntaban a código que estaba bien):

- **1.2 era falsa.** `_needs_refresh()` devuelve `True` **a propósito**: el
  firmware devuelve los brazos a su posición de reposo si deja de recibir
  paquetes, así que el refresco continuo es obligatorio. **No se ha tocado.**
  Lo que sí había que arreglar era que el watchdog reenviase la velocidad.
- **1.4 era falsa.** `_ejecutar_paso` **sí** respeta la duración: el
  `await asyncio.sleep(paso.duracion)` del final del paso la aplica, y el
  `Traductor` mete `bloque.segundos` en el `Step`. No se ha tocado.

### Dos agujeros de seguridad nuevos que aparecieron al implementar

- **El watchdog paraba la kata a mitad.** La kata dura ~20 s y el watchdog
  está a 5 s. Como antes el watchdog no paraba nada, el problema estaba
  latente; al arreglarlo, habría parado el robot en mitad de la coreografía.
  Resuelto con un contador `_en_ejecucion`: mientras hay un comando en
  marcha, el watchdog espera.
- **Desconectar no paraba el robot.** `session.desconectar()`,
  `AiroService._stop()` (Scratch) y `_shutdown()` de la consola soltaban el
  BLE con las ruedas en marcha. Ahora los tres mandan velocidad 0 antes.

---

## 1. Resumen ejecutivo

| Área | Estado | Hallazgos |
|---|---|---|
| Protocolo BLE / framing | Correcto | `FIXED_TAIL`, magic `0xA5`, payload de 20 B: coinciden 1:1 con `docs/desensamblado/*.asm` |
| Ruedas (motores) | **Correcto** | `encode_motor(invert=...)` reproduce exactamente la tabla de ruedas cruzadas del desensamblado |
| Servos (brazos) | **Roto** | 3 bugs de mirrored-side + 1 inconsistencia de fórmula de calibrado |
| Parada de emergencia / seguridad | **Roto** | El watchdog nunca frena; los programas terminan con las ruedas en marcha |
| Tests | Parcial | 29 pasan, 10 fallan **solo** por falta de `pytest-asyncio` (no son fallos de lógica) |
| Empaquetado | Roto | El entry point `airo-server` no existe dentro del wheel |
| API / Web / Scratch | Mayormente OK | Deuda menor: lifespan de FastAPI, CORS `*`, timings hardcodeados |

**Bugs empíricamente reproducidos** (scripts ejecutados contra el código actual): **5**,
de los cuales **4** afectan a la seguridad del robot (el robot puede seguir moviéndose solo).

---

## 2. Bugs confirmados por reproducción

### 🔴 BUG-01 — `session.brazo("ambos", ...)` solo mueve el brazo derecho

**Archivo:** `airo_ble/session.py:164-178`

```python
for joint, angle in ARM_POSES[pose].items():
    if lado.startswith(("izq", "left")):
        joint = (Joint.LEFT_SHOULDER if joint is Joint.RIGHT_SHOULDER
                 else Joint.LEFT_ARM)
    self.robot.command.set_joint(joint, angle)
```

La rama de espejado solo se dispara para `izq*`/`left*`. Con `lado="ambos"` el
`if` nunca entra, así que **siempre** escribe `RIGHT_SHOULDER` y `RIGHT_ARM`.
`LEFT_ARM` y `LEFT_SHOULDER` quedan en `None` para siempre.

**Reproducción (resultado real):**

```
{'RIGHT_SHOULDER': -60.0, 'RIGHT_ARM': 170.0, 'LEFT_ARM': None, 'LEFT_SHOULDER': None}
```

**Impacto:** la ruta web/Scratch está rota. `api/service.py` (`Traductor`) genera
`Step("brazo", {"lado": "ambos"})`, y `api/models.py:49-54` (`BloqueBrazo.lado`)
ofrece `"ambos"` explícitamente como opción en el editor de bloques. El
"izquierdo" nunca se mueve y el "derecho" se mueve **dos veces**.

**Note:** el CLI `airo_ble/console.py` **sí** funciona con "ambos" porque su
parser de comandos (`_cmd_brazo`) tiene su propia lógica. Solo la ruta
`session.brazo()` — la que usan la API web y el puente de Scratch — está rota.

---

### 🔴 BUG-02 — `airo_server.py` mueve el brazo **derecho** cuando se pide el **izquierdo**

**Archivo:** `airo_server.py:160-172` (y `airo_server.py:204` en `_kata`)

```python
lado = str(comando.get("side", "left")).lower()      # default: "left"
...
if lado.startswith("i"):                              # "left" NO empieza por "i"
    joint = (...)
```

El docstring del propio servidor (`airo_server.py:21`) documenta
`"side": "left|right"`. Pero la comprobación es `startswith("i")`, que en
español significa "izquierda" (`izq`). `"left"` en inglés **no** empieza por
`"i"` → no hay espejado → se mueve el brazo derecho.

**Reproducción (resultado real):** `side='left'` → solo se escriben
`RIGHT_SHOULDER` y `RIGHT_ARM`; los joints izquierdos nunca se tocan.

Mismo patrón en `_kata` (`airo_server.py:204`): `lado.startswith("izq")` — allí
el bug es distinto: el texto de la kata usa nombres en español, así que
funciona, pero es inconsistente con el resto del archivo y con `side="left"`.

**Impacto:** el puente Scratch 3 (`scratch3_airo/airo.js`) envía `side` en
inglés → el bloque "mover brazo izquierdo" mueve el brazo derecho. Esto es
exactamente el tipo de bug que el usuario describe como "cosas que se podrían
mejorar".

---

### 🔴 BUG-03 — El watchdog del CLI nunca frena las ruedas

**Archivo:** `airo_ble/console.py:303-324`

```python
idle = loop.time() - self._last_input
if self.watchdog and idle > self.watchdog and self._moving():
    await self._send(echo=False)                    # ← reenvía la velocidad
    print(f"\n[!] {self.watchdog:g} s sin comandos: ruedas paradas.")
```

El mensaje promete "ruedas paradas" pero lo único que hace es **reenviar el
paquete con la misma velocidad**. Nunca llama a `command.stop()`.

Además `_needs_refresh()` devuelve `True` siempre, así que el keepalive sigue
reeenviando la última velocidad cada ~200 ms indefinidamente.

**Reproducción (resultado real):** tras disparar el watchdog,
`left_speed` sigue en `2.0` (debería ser `0.0`).

**Impacto:** si el robot se queda con la orden de avanzar (se queda atascado
en una alfombra, se pierde el stream, se cierra el terminal a media orden),
**sigue avanzando indefinidamente** hasta que se apague el proceso. Es el
bug de seguridad más grave del repo.

---

### 🔴 BUG-04 — Al terminar un programa, las ruedas siguen en marcha

**Archivos:** `airo_ble/session.py` (`_ejecutar_paso` / `_ejecutar`),
`api/main.py:132-140`

Dos problemas encadenados:

1. En `_ejecutar_paso`, la rama `"mover"` llama a `self.mover(...)` **sin pasar
   `segundos`** (la duración se aplica *después* del paso). Como `mover()` solo
   hace `await asyncio.sleep(segundos)` si `segundos` es truthy, el paso
   "mover" no espera: devuelve el control inmediatamente.
2. `_ejecutar` **no llama a `parar()`** al terminar un programa con éxito
   (solo lo hace en la rama de excepción/cancelación).

**Reproducción (resultado real):** tras un programa "avanzar" completado,
`left_speed=2.0, right_speed=2.0`. La tarea de refresco sigue enviando → el
robot sigue conduciendo.

**Variante API:** `api/main.py:132-140` (`/api/mover`) sí duerme `segundos`,
pero **no pone las velocidades a 0** al terminar la llamada HTTP. La petición
devuelve "OK" y el robot sigue moviéndose.

**Impacto:** cualquier programa de bloques ejecutado desde la web deja el
robot conduciendo hasta que se envíe un `parar` explícito.

---

### 🟠 BUG-05 — `session._refrescar` traga el error y entra en bucle de reconexión eterno

**Archivo:** `airo_ble/session.py:108-139`

En el fallo de refresco se hace `self.conectado = False` y se vuelve a
intentar en bucle sin límite, **sin actualizar `self.error`** con la última
excepción (el estado que la UI lee para mostrar "error"). Además se llama a
`await self.robot.disconnect()` en cada iteración del bucle, no al salir de él,
lo que deja el cliente en un estado inconsistente entre reintentos.

**Impacto:** cuando el robot se desconecta, la web no muestra por qué; el
proceso queda en un bucle silencioso reintentando.

---

## 3. Discrepancias de protocolo (contrastadas con el desensamblado)

Esta sección documenta el trabajo de **verificación cruzada** contra
`docs/desensamblado/*.asm`, que es la fuente de verdad. Resultado por byte del paquete:

| Byte | Campo | Veredicto |
|---|---|---|
| 0 | Magic `0xA5` | ✅ coincide con `RobotStatus_SetFixedBytes.asm` |
| 1-2 | Velocidad izq. | ✅ `set_LeftMotorSpeed.asm`: `>0 → dir 2`, `<0 → dir 1` |
| 3-4 | Velocidad der. | ✅ `set_RightMotorSpeed.asm`: `<1 → dir 2, mag ≤3`, `≥1 → dir 1` |
| 5 | LED | ✅ |
| 6-9 | Servos 1-4 | ⚠️ signos correctos, pero **fórmula de calibrado inconsistente** (ver D-01) |
| 10-19 | Cola fija | ✅ `FIXED_TAIL = (5,22,39,56,73,90,107,124,141,158)` coincide byte a byte |

### ⚠️ D-01 — `encode_servo()` usa dos fórmulas distintas según `neutral`

**Archivo:** `airo_ble/protocol.py:220-228`

```python
raw = SERVO_ORIGIN + SERVO_SIGN[joint] * (clamped + int(offset))   # ruta principal
scaled = min(abs(raw), SERVO_ORIGIN * 2) / SERVO_SCALE
byte = round_half_even(scaled)
if neutral is not None:
    base = float(neutral)
    bruto = base + SERVO_SIGN[joint] * (clamped + int(offset)) / SERVO_SCALE
    byte = round_half_even(abs(bruto))                              # ← OTRA fórmula
```

La ruta con `neutral` **no divide por el mismo factor ni aplica el mismo
recorte de 340** que la ruta principal, y el `abs()` actúa sobre un valor que
ya está escalado de forma distinta. El desensamblado (`Servo1.asm`) muestra
un único pipeline: `angulo + offset` → `+170` → `abs` → `cap 340` → `/8.5` →
`Math.Round(ToEven)`.

**Impacto:** `calibration.json` define `neutral` para las cuatro
articulaciones (`left_shoulder:20, left_arm:20, right_arm:20,
right_shoulder:16`). Por tanto **la calibración real está usando la ruta
alternativa**, que es la que no replica el firmware. Cualquier valor de
`offset` en `calibration.json` tendrá un efecto distinto del esperado.

> **Matiz (calculado después):** con `neutral = 20` las dos fórmulas son
> *algebraicamente idénticas* (170/8.5 = 20), así que en la práctica solo
> difieren para la articulación cuyo `neutral` no es 20: el **hombro derecho**
> (byte 9), con 16. Por eso la tarea 2.5 es mucho más pequeña de lo que
> parecía: solo hay que decidir si ese 16 es una medida real o un error.

### ✅ Signos por servo — **correctos**

El desensamblado muestra la convención real por servo:

| Servo | Byte | Routine | Cálculo |
|---|---|---|---|
| 1 | 6 | `SetFirstServoMotor` | `+ (ángulo + offset)` → **+** |
| 2 | 7 | `SetSecondServoMotor` | `170 − ángulo − offset` → **−** |
| 3 | 8 | `SetThirdServoMotor` | `+ ángulo + offset` → **+** |
| 4 | 9 | `SetFourthServoMotor` | `170 − ángulo − offset` → **−** |

Y `protocol.py:SERVO_SIGN` (RIGHT_SHOULDER=+1, RIGHT_ARM=−1, LEFT_ARM=+1,
LEFT_SHOULDER=−1) coincide con esa tabla. **No tocar los signos.**

Ojo: la tabla de arriba está en bytes, que es lo único que importa. Los
**nombres** del enum se renombraron (tareas 2.8 y 2.9) para usar los físicos
del robot, verificados con el robot delante, pero el signo de cada byte no se
ha movido.

### ℹ️ D-02 — La guía simplifica la regla de escalado

`protocolo.md` §2.5 describe `170 + signo*(ángulo+offset)`, pero el
asm real calcula el offset **dentro** del paréntesis para el signo + y **fuera**
para el signo − (`170 − ángulo − offset` es idéntico a `170 − (ángulo+offset)`,
así que en la práctica coinciden). La simplificación es aceptable, pero la
fórmula de la rama `neutral` (D-01) **no** es una simplificación: es otra cosa.

---

## 4. Lista de tareas

Prioridad: **P0** = seguridad / el robot se mueve solo · **P1** = funcional roto
· **P2** = calidad / mantenibilidad · **P3** = pulido.

### FASE 0 — Decisión de producto ✅ **RESUELTA**

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 0.1 | **Fijar la semántica de "lado" del robot** | Reconciliar: (a) tabla de bytes de `protocolo.md` §2 líneas 63-66 (byte 6 = "Hombro izquierdo", ...), (b) enum `Joint` de `protocol.py`, (c) `console.ARM_POSES`. | ✅ **Resuelto con el robot delante** (tarea 2.9): la tabla de la guía tenía el byte 6 y el 9 cambiados. Ahora manda el **robot**: byte 6 = hombro derecho. |
| 0.2 | Confirmar cuántos servos existen físicamente | El usuario habló de "los brazos (2 servos)". ¿El Clementoni AIRO tiene 2 o 4 servos? | ✅ **4 servos**: hombro + codo por cada brazo. El enum `Joint` completo es válido. |
| 0.3 | Documentar la convención elegida | Añadir un bloque inequívoco en `protocolo.md` y en el docstring de `Joint`. | ⬜ Pendiente (tarea 2.8) |

### FASE 1 — Seguridad (P0) ✅ **APLICADA**

| # | Tarea | Archivo / referencia | Estado |
|---|---|---|---|
| 1.1 | **El watchdog debe parar las ruedas** | `console.py` → nuevo `Console.parar()`; el watchdog llama a `await self.parar()`. | ✅ Hecho |
| 1.2 | ~~`_needs_refresh()` debe devolver `False`~~ | **FALSO POSITIVO**: el refresco continuo es obligatorio (el firmware suelta los brazos si dejan de llegar paquetes). **No tocar.** | ✅ Descartada |
| 1.3 | **`_ejecutar` debe llamar a `parar()` al final** (éxito y excepción) | `session.py` → `try/finally` con `await self.parar()`. | ✅ Hecho |
| 1.4 | ~~`_ejecutar_paso` "mover" debe pasar `segundos`~~ | **FALSO POSITIVO**: el `sleep(paso.duracion)` del final del paso ya la aplica, y el `Traductor` mete `bloque.segundos` en el `Step`. **No tocar.** | ✅ Descartada |
| 1.5 | **`/api/mover` debe poner a 0 al terminar** | `api/main.py` → `try/finally` con `sesion.parar()` (solo si `segundos > 0`; con 0 es movimiento sostenido). | ✅ Hecho |
| 1.6 | **Fin de programa en la web** | El robot ya se para al final del programa (`_ejecutar`); además la interfaz usa la duración real (`Traductor.duracion_de` → `RespuestaEjecucion.duracion` → `main.jsx`) en vez de 1,5 s fijos. | ✅ Hecho |
| 1.7 | Apagado ordenado | `console.py` → `_shutdown()` para el robot antes de cerrar el BLE. | ✅ Hecho |
| 1.8 | **Desconectar debe parar el robot** *(nuevo)* | `session.desconectar()` y `AiroService._stop()` (Scratch) mandan velocidad 0 antes de soltar el BLE. | ✅ Hecho |
| 1.9 | **El watchdog no debe parar un comando en marcha** *(nuevo)* | `console.py` → contador `_en_ejecucion`; mientras hay una kata o un comando largo en curso, el watchdog espera. | ✅ Hecho |

### FASE 2 — Brazos / servos (P1) — **A y B aplicadas**

| # | Tarea | Archivo / referencia | Estado |
|---|---|---|---|
| 2.1 | **Arreglar `session.brazo("ambos")`** | `session.brazo` ahora usa el resolver compartido → "ambos" mueve las cuatro articulaciones. | ✅ Hecho |
| 2.2 | **Arreglar `"left"` vs `"izq"` en `airo_server`** | `_apply` y `_kata` usan el mismo resolver → `"left"` mueve el brazo izquierdo y `"ambos"` los dos. | ✅ Hecho |
| 2.3 | Unificar el criterio de espejado | Nuevo módulo `airo_ble/arms.py` con `resolver_lado()` / `resolver_brazo()`. Las cuatro copias anteriores (consola, sesión, servidor) se han borrado. | ✅ Hecho |
| 2.4 | **Unificar la fórmula de `encode_servo`** | **REBAJADA**: no era un bug. Con `neutral = 20` las dos fórmulas son *algebraicamente idénticas* (170/8.5 = 20). Solo difieren si el `neutral` de una articulación no es 20. | ⬜ Pendiente (solo documentación) |
| 2.5 | Validar la calibración contra el hardware | `calibration.json` — el `left_shoulder: 16` es lo único que hace que las dos fórmulas difieran (4 bytes = 34°). **Necesita el robot.** | ⬜ Pendiente (hardware) |
| 2.6 | `web/src/Robot.jsx:10` — mapeo visual de ángulos | `angulo = ((byte - 20) / 20) * 60` era aproximado y hardcodeado: errores de hasta 230° en los codos y el codo ni siquiera se dibujaba. | ✅ **Hecho**: el mapeo esta en `web/src/angulos.js` (espejo de `protocol.py`, con signo, limites y neutral por articulacion), el codo se dibuja, y el estado publica el `neutral`. 30 tests de vitest + 4 de pytest que lo contrastan con `encode_servo()`. |
| 2.7 | Bloque "ambos" en la UI web | `api/models.py:49-54` permite `"ambos"`; la ruta underlying ya funciona. Añadido test de integración bloque→robot. | ✅ Hecho |
| 2.8 | **Renombrar el enum `Joint` según la guía** | Byte 6 = hombro **izquierdo**, 7 = brazo izquierdo, 8 = brazo derecho, 9 = hombro derecho (según la tabla de la guía). | ⚠️ **Hecho, pero DESHECHO por la 2.9**: la tabla de la guía tenía el byte 6 y el 9 cambiados. |
| 2.9 | **Corregir el lado físico de los brazos con el robot delante** | La guía decía que el byte 6 era el hombro **izquierdo**; con el robot en la mesa y una cámara se vio que es el **derecho** (el robot enseña la cara: ojos y LED del pecho). Consecuencia: "brazo derecho" movía el brazo **izquierdo** del robot. | ✅ **Hecho**: `Joint.RIGHT_SHOULDER` = byte 6 y `Joint.LEFT_SHOULDER` = byte 9 (y los codos igual). **Los bytes no se han movido**: el mapa byte → (signo, límites) sigue 6:+, 7:−, 8:+, 9:− y el conjunto de 4 bytes de cada pose es idéntico. `calibration.json` se re-mapeó (el cero en 16 se queda en el byte 9, ahora `left_shoulder`). La guía y el README están corregidos. |
| 2.10 | **Documentar el rango real de bytes del codo** | Mandando bytes crudos al codo, los bytes 23/30/40 dan imágenes indistinguibles: el codo derecho solo usa 0..23 y el izquierdo 17..40. Consecuencia de los límites (−25..170) con la escala de 8,5°/byte. La app nunca manda los bytes inútiles (recorta el ángulo antes de escalar), así que no es un bug. | ✅ **Hecho**: documentado en `docs/protocolo.md` § 2.5 con la evidencia (el barrido con el robot delante). |
| 2.11 | **Geometría visual real del hombro y del codo** | Con qué ángulo se ve de verdad el antebrazo para un byte dado del codo, y con qué ángulo real gira el hombro. Las mediciones dan un desvío constante de ~30° en el codo y sugieren que el hombro cuelga antes del +77 de la app, pero con ±20-30° de margen (escena a contraluz, piezas de 30-60 px). | ⬜ **Abierta**: el dibujo de la web sigue el modelo de ángulos de la app oficial. No se cambia con una medición dudosa. Pendiente de repetir con luz y el robot más cerca. |

### FASE 2-bis — Lo que apareció al implementarla

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 2b.0 | **⚠️ Cambio de comportamiento al renombrar** | Antes del renombrado, el comando "brazo **der**" escribía los bytes 6 y 7, que la guía identificaba como el hombro y el brazo **izquierdos**. O sea: la palabra "derecho" movía el brazo izquierdo. **Los bytes de cada articulación no se han movido** (el byte 6 sigue siendo 13/0 en la pose "arriba"); lo único que se decide es a qué lado físico pertenece cada byte. | ✅ **Comprobado en el robot** (tarea 2.9): la guía estaba cambiada y el byte 6 es el hombro **derecho** de verdad. Así que "derecho" vuelve a escribir los bytes 6 y 7, que son los de su brazo. |
| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 2b.1 | **La web no cargaba la calibración** *(nuevo)* | `load_calibration()` solo se llamaba en la consola y en el puente de Scratch. La API web nunca la cargaba: el mismo comando ponía el hombro izquierdo en el byte **27** por la web y en el **23** por la consola. `session` ahora la carga al construirse (es del comando, no de la conexión) y al conectar. | ✅ Hecho |
| 2b.2 | `calibration.json` desaparece al instalar el paquete | `CALIBRATION_FILE = Path(__file__).parent.parent / "calibration.json"` → vale en un checkout, pero al instalar el wheel el fichero no está empaquetado y la calibración se pierde en silencio. Mismo clase de bug que el entry point `airo-server` (Fase 6). | ✅ **Hecho**: la calibración por defecto va dentro del paquete (`airo_ble/calibration.json`) y la del usuario a `~/.config/airo-ble/calibration.json`, que tiene prioridad. |
| 2b.3 | Comentarios contradictorios en `console.py` | El bloque de comentario de `ARM_POSES` mezclaba las dos convenciones (el viejo hablaba del "hombro izquierdo", el nuevo del "hombro derecho"). Al mover las poses a `arms.py` se han unificado. | ✅ Hecho |

### FASE 3 — Estado, sesión y reconexión (P1) ✅ **APLICADA**

| # | Tarea | Archivo / referencia | Estado |
|---|---|---|---|
| 3.1 | `session._refrescar` debe registrar el error | `session.py` → el bucle de reconexión se tragaba la excepción nueva con un `continue`, así que la interfaz mostraba **el primer error para siempre**; y llamaba a `disconnect()` en cada reintento. | ✅ **Hecho**: `_reconectar()` desconecta una vez y guarda el error más reciente. `espera_reconexion` es configurable. |
| 3.2 | `client._on_device` deduplica anuncios | `client.py` — `_seen` era una **lista** que crecia sin limite (el robot se anuncia varias veces por segundo) y `_wait_for_robot` devolvia siempre el ultimo anuncio, que podia ser de hace medio minuto. | ✅ **Hecho**: `_seen` es un dict `direccion -> (dispositivo, rssi, momento)`. Se queda con el de mejor RSSI y descarta los anuncios viejos. |
| 3.3 | `client.send()` marca `_last_write` antes del `await` | `client.py` — el ritmo quedaba optimista y dos envios concurrentes podian escribir casi a la vez (el segundo habia calculado el `now` antes de que el primero escribiera). | ✅ **Hecho**: el ritmo se aplica **dentro** del lock y `_last_write` se actualiza **despues** de escribir. |
| 3.4 | `client.send_raw()` unifica el pacing y respeta `force` | `client.py` — duplicaba la logica del ritmo y no aceptaba `force`. | ✅ **Hecho**: `send()` y `send_raw()` delegan en `_escribir()`. |
| 3.5 | `Command.to_bytes()` tiene un bucle redundante | `protocol.py:302-338` → el primer bucle (centro) es absorbido por el segundo (override). | ⬜ Pendiente (P3) |
| 3.6 | `_wait_for_robot` con timeout y criterios de RSSI | `client.py` → devolvia `self._seen[-1]` a ciegas. | ✅ **Hecho**: `_mejor_dispositivo()` con RSSI + antiguedad. |
| 3.7 | **Errores verificables por tipo** *(nuevo)* | `client.py` — todo se lanzaba como `RuntimeError` con un texto en espanol, asi que no se podia distinguir "no esta" de "no conecte" de "se colgo la escritura" sin leer el mensaje. | ✅ **Hecho**: `AiroError` → `AiroNotFound`, `AiroNotConnected`, `AiroConnectionError`, `AiroWriteError`. Todos siguen siendo `RuntimeError` (nadie rompe). |
| 3.8 | **Reconexion y comprobacion del enlace** *(nuevo)* | `client.py` — conectar dos veces dejaba el modulo a medias; bleak puede "conectar" sin que el enlace quede. | ✅ **Hecho**: `connect()` es idempotente, comprueba `is_connected` al conectar, y hay `reconnect()` (cierra limpio + vuelve a escanear). |

### FASE 4 — Tests (P1)

| # | Tarea | Detalle | Prioridad |
|---|---|---|---|
| 4.1 | **Instalar y configurar `pytest-asyncio`** | Los **10 tests de `tests/test_console.py` fallan** con *"async def functions are not natively supported"*. No es lógica: falta el plugin. Añadir `pytest-asyncio` a `pyproject.toml` + `asyncio_mode = "auto"` (o marcadores). | P1 |
| 4.2 | Tests de regresión para BUG-01/02/03/04 | Un test por bug, con un `AiroRobot` falso (como los ya existentes en `test_protocol.py`). | P1 |
| 4.3 | Test de equivalencia de `encode_servo` vs desensamblado | Casos límite: clamp a `[−60,77]`, `fcvtzs` (truncado, no redondeo), `round_half_even`, cap 340, `abs`. | P1 |
| 4.4 | Test de no-regresión de ruedas | Congelar el comportamiento actual de `encode_motor` **como está**, para que ningún arreglo de brazos lo rompa. | P1 |
| 4.5 | Test de fin de programa | Tras ejecutar un programa, `left_speed == right_speed == 0`. | P1 |
| 4.6 | Tests del traductor de bloques | `api/service.py` — `Traductor` con `ambos`, anidamiento de `BloqueRepetir`, límites. | P2 |

### FASE 5 — API, Web y Scratch (P2)

| # | Tarea | Detalle | Prioridad |
|---|---|---|---|
| 5.1 | Migrar `@app.on_event` a `lifespan` | `api/main.py` — FastAPI ya lo marca como *deprecated*. | ✅ **Hecho**: `@contextlib.asynccontextmanager` con `lifespan=`. Además el apagado **cancela** la tarea de reconexión, que antes se quedaba viva para siempre. La suite pasó de 53 s a 3 s y a **0 avisos**. |
| 5.2 | Restringir CORS | `api/main.py:47-52` — `allow_origins=["*"]` en una API de control local. | P2 |
| 5.3 | `BloqueRepetir` expande recursivamente sin tope | `api/service.py` — `veces` hasta 50 y anidamiento → explosión combinatoria de pasos. Añadir tope de pasos totales. | ✅ **Hecho**: tope de 1000 pasos, comprobado *dentro* del bucle (si no, se construían 125.000 pasos antes de decir que no). La API contesta con un error claro, no con un 500. |
| 5.4 | Validación de entradas del servidor Scratch | `airo_server.py:319` — `str(destino).startswith(str(base))` es un chequeo de prefijo débil → usar `Path.is_relative_to`. | P2 |
| 5.5 | Timing real del programa en la web | `web/src/main.jsx:360` — `1500` ms hardcodeados. | P1 |
| 5.6 | Estado de conexión visible en la web | `session.error` no se propaga (ver 3.1). | P2 |

### FASE 6 — Empaquetado y calidad (P2/P3)

| # | Tarea | Detalle | Prioridad |
|---|---|---|---|
| 6.1 | **`airo-server` no existe en el wheel** | `pyproject.toml:47` declara `airo-server = "airo_server:main"` pero `packages = ["airo_ble"]` — `airo_server.py` es un módulo suelto en la raíz y no se empaqueta. El entry point fallará tras `pip install`. | ✅ **Hecho**: todo lo instalable vive en `airo_ble/`. Verificado construyendo un wheel e instalándolo en un venv limpio: `airo-server` arranca. |
| 6.2 | Módulos de nivel superior sin empaquetar | `airo_server.py`, `airo_console.py` en la raíz → mover a paquete (`airo_ble/server.py`) o declararlos en `pyproject.toml`. | ✅ **Hecho**: `api/` → `airo_ble/api/`, `airo_server.py` → `airo_ble/server.py`, `scratch3_airo/` → `airo_ble/scratch3_airo/`. En la raíz quedan solo atajos (`airo_server.py`, `airo_console.py`) que no se instalan. |
| 6.3 | **Código muerto en `session.py`** | `POSE_NATURAL` y `_ARTICULACIONES` (`session.py:33-47`) están definidos y exportados pero **nadie los usa**. `POSE_NATURAL["saludo"]` apunta a `"arriba"` sin ningún caller que lo resuelva. | P3 |
| 6.4 | **Código muerto en `console.py`** | `_ARM_SIDE` (`console.py:166-173`) no se usa. | P3 |
| 6.5 | Expresión condicional confusa | `console.py:352` → `if echo if echo is not None else self.echo:` → reescribir con `if/else` o walrus. | P3 |
| 6.6 | Revisar `web/src/api.js` y `main.jsx` | Resto del flujo web no revisado en detalle (carga parcial). | P3 |

---

## 5. Lo que está bien (no tocar)

- ✅ `FIXED_TAIL` — coincidencia byte a byte con el firmware.
- ✅ Magic `0xA5` y longitud de payload de 20 bytes.
- ✅ `encode_motor` + `invert` — reproduce la tabla de ruedas cruzadas.
- ✅ `SERVO_SIGN` — coincide con los 4 routines de servo del desensamblado.
- ✅ `round_half_even` — replica `Math.Round(ToEven)` de .NET.
- ✅ Clamp de servos a `[−60, 77]` — coincide con `cmp w20,#0x4d` / `cmn w8,#0x3c`.
- ✅ `AiroControl_set_LeftArmAngle` → `SetThirdServoMotor` (byte 8) → ese byte es el **brazo derecho** físico (`Joint.RIGHT_ARM`).
- ✅ El contador `packageIdx` (`[x19,#0x6c]`) **no** está en el payload → correcto que no se envíe.
- ✅ La lógica de "qué lado se mueve" está unificada en `airo_ble/arms.py`: la consola, la API y Scratch ya no se contradicen.

---

## 6. Orden de ejecución recomendado

1. ✅ **Fase 0** — decisión de producto (resuelta: manda la guía, 4 servos).
2. ✅ **Fase 1** — seguridad. Hecha: el robot ya no puede quedarse moviendo solo.
3. ✅ **Fase 4.1** — `pytest-asyncio` instalado y configurado (`asyncio_mode = "auto"`).
4. ✅ **Fase 4.2-4.5** — `tests/test_safety.py` con 15 tests de regresión de la Fase 1.
5. ✅ **Fase 2.1-2.3** — la lógica de lados, unificada en `airo_ble/arms.py`.
6. ✅ **Fase 2-bis** — la web ya carga la calibración (era un bug).
7. ✅ **Fase 2.8** — el enum `Joint` renombrado a los nombres físicos de la
   guía. Los bytes no se han movido (ver abajo).
8. ⬜ **Fase 2.5** — recalibrar contra el hardware (¿es correcto el
   `left_shoulder: 16`?). **Necesita el robot delante.**
9. ⬜ **Fase 3** → **Fase 5** → **Fase 6**.

---

## 7. Cómo se ha verificado

- **Reproducción directa** de los bugs con scripts ejecutables sobre el código
  (se instancia `RobotSession`/`AiroRobot` reales y se inspecciona
  `robot.command.servos` / `left_speed`).
- **Contraste con el desensamblado ARM64** en `docs/desensamblado/*.asm` byte a byte.
- **Suite de tests**: `106 passed` (antes 29 passed / 10 failed).
  - `tests/test_safety.py`: 15 tests que fijan el comportamiento de seguridad
    (watchdog, fin de programa, desconexión, `/api/mover`, duración).
  - `tests/test_arms.py`: 52 tests que fijan los **bytes exactos** de cada pose
    y cada lado, el mapa byte → signo, y que consola / API / Scratch muevan
    lo mismo.
  - `tests/test_client.py`: el escenario con BLE simulado ahora lo recoge
    pytest (antes solo se ejecutaba con `python3 tests/test_client.py`).
- **Los bytes no han cambiado**: antes y después del refactor de los brazos y
  del renombrado del enum, el conjunto de 4 bytes de cada pose es idéntico
  byte a byte, y el mapa byte → (signo, límites) es el mismo.
- **Prueba en vivo contra el servidor real**: `uvicorn api.main:app` + `curl`.
  - Lanzar un programa de "avanzar 2 s" devuelve `duracion: 2.0` y, al terminar,
    `/api/estado` devuelve `accion: "parado"` y las ruedas a `0.0`.
  - `/api/estado` devuelve `left_shoulder byte=20` y `right_shoulder byte=16`
    (con el robot apagado), igual que la consola: la calibración ya se aplica
    en las dos entradas.
  - El bloque de brazo "ambos" deja los mismos bytes de siempre
    (13 / 0 / 40 / 23), pero ahora con los nombres físicos correctos.
- **Las ruedas no se han tocado**: el encoding de motores sigue siendo el que
  coincide con el firmware (`protocol.py` solo ha cambiado de *nombres*).
