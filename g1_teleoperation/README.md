# Teleoperación XR del G1 con Meta Quest 3, caminando con el mando

Los brazos del G1 EDU-U6 y los dedos de sus manos **Inspire RH56E2** siguen a los del operador, que lleva unas
**Meta Quest 3**. A la vez, **el robot sigue en su locomoción de Unitree** y otra persona lo hace caminar con el
mando. Los brazos van por **`rt/arm_sdk`** (el *Motion Mode* de `xr_teleoperate`, `--motion`), no por `rt/lowcmd`.

Es la teleoperación del H1-2 (`h1_2_utec/h1_2_teleoperation`) pasada al G1. Todo corre en el **PC2 del robot**
(el Jetson): `~/utec/teleoperacion`, `xr_teleoperate` de Unitree en el commit `817fb00` y el entorno `env_tv`.
Desde el PC solo se lanza, por SSH, con los scripts de [`scripts/`](scripts/).

> **Estado (2026-11-26): funciona en el G1.** Teleop completo con las Quest: los brazos y los dedos siguen al
> operador y **el robot camina con el mando mientras mueve los brazos, sin caerse**. Detalle y lo pendiente en §9.

> **Dos G1, el mismo código.** El **.151** (`192.168.0.151`) tiene las RH56E2: brazos y dedos. El **.152**
> (`192.168.0.152`) tiene las **manos de goma** de Unitree: **solo los brazos**. Lo que cambia lo dice
> `~/utec/teleoperacion/robot.conf` en cada robot (`MANOS=rh56e2` o `MANOS=goma`, §1), y desde el PC se elige con
> `G1=152 ./teleop_xr.sh`. **El .152 funciona desde el 2026-11-27**: los brazos siguen al operador con el robot
> moviéndose con el mando (§9).

**Nada de esto se lanza sin el visto bueno del responsable del laboratorio.**

---

## 1. Cómo funciona

```
  PC (Ubuntu)                               G1 EDU-U6
  scripts/teleop_xr.sh ── ssh -t ──▶ PC2 (Jetson, WiFi UTEC_H1_2: 192.168.0.151; cable: 192.168.123.164)
                                      ~/utec/teleoperacion/teleop_xr.sh → arrancar.sh
                                        0. robot.conf; ¿alguien publica ya en rt/arm_sdk? → no arranca;
                                           con MANOS=rh56e2, ¿contestan las dos manos? → si no, no arranca
                                        1. servidor de imagen: teleimager + D435i de la cabeza
                                        2. driver de las manos: Modbus TCP ⇄ DDS (inspire_ftp_dual_driver.py),
                                           solo con MANOS=rh56e2
                                        3. teleop_hand_and_arm.py --motion (lanzar_teleop.py)
                                             · Vuer/WebXR :8012  ◀── Meta Quest 3 (WiFi)
                                             · rt/arm_sdk (DDS eth1)  ──▶ cintura y brazos, mezclados con la
                                                                          locomoción según el peso
                                             · rt/inspire_hand/ctrl/{l,r} ──▶ driver ──▶ manos (solo rh56e2)
                                                                   izq 192.168.123.210 · der .211
  Mando de Unitree (otra persona) ───────▶ locomoción de Unitree (piernas): caminar, parar, amortiguamiento
```

- **`rt/arm_sdk`**: el control de locomoción de Unitree mezcla su consigna de cintura y brazos con la que llega
  por `rt/arm_sdk`, según el **peso** que va en `motor_cmd[29].q`: 0 es solo la locomoción y 1 es solo arm_sdk.
  Las piernas son siempre de la locomoción. Para eso el robot tiene que estar de pie en **modo Regular**, no en
  Running (R2+A): lo dice el código de Unitree (`teleop_hand_and_arm.py`, línea 141), que lo pone con R1+X. **En
  el G1 .151 el Regular es R1+Y** y da la FSM 501 (2026-11-26). Antes de eso se leyó también la 802, en un modo que no
  se apuntó.
- **Dos personas**: los brazos y los dedos se mueven con el seguimiento de manos de las Quest
  (`--input-mode=hand`), así que el operador mueve brazos y manos, y **otra persona hace caminar al robot con el
  mando de Unitree**. En el .152 tampoco se usan los mandos de las gafas: con `--motion`, el modo `controller` de
  Unitree les da la locomoción a ellos, y con los dos joysticks pulsados la pone en amortiguamiento (el robot cae).
  `lanzar_teleop.py` no arranca con `--input-mode=controller`.
- **`robot.conf`**, en `~/utec/teleoperacion` de cada robot: `NOMBRE`, `MANOS` (`rh56e2` | `goma`), `IFACE` (la
  red interna), `D435I` (el n.º de serie de su cámara) y `MAC_WIFI`. **Los dos G1 llevan la misma imagen
  clonada**: la misma clave de host SSH y, por cable, la misma `192.168.123.164`. Solo los distingue la MAC de
  `wlan0`, así que si el robot no tiene la `MAC_WIFI` de su `robot.conf`, ese fichero es el del otro G1 y nada que
  lo mueva arranca. Las plantillas son
  [`scripts_robot/robots/`](scripts_robot/robots/). Con `MANOS=goma`, `arrancar.sh` no arranca el driver de las
  manos y lanza el teleop **sin `--ee`**: Unitree no crea el control de las manos y solo mueve los brazos. La IK
  usa el modelo con las manos de goma. Sin `robot.conf`, nada que mueva el robot arranca.
- `comun.sh` ve que el PC no es el robot y **reenvía la orden por SSH**. **Siempre se ejecuta el código del
  robot.** Su copia versionada está en [`scripts_robot/`](scripts_robot/README.md).
- **Las gafas se conectan directamente al robot**, no al PC.

## 2. Qué cambia respecto al H1-2

| | H1-2 | G1 |
|---|---|---|
| Brazos | `rt/lowcmd` en Debug (L2+R2): las piernas se sueltan, colgado | **`rt/arm_sdk` con la locomoción**: las piernas se sostienen solas y el mando sigue mandando |
| Lanzador | `--arm=H1_2` | `--arm=G1_29 --motion`; sin `--motion` no arranca |
| Manos | RH56DFTP, Modbus TCP en `192.168.124.210` (der) y `.211` (izq) | .151: **RH56E2**, mismo driver y registros, en `192.168.123.210` (**izq**) y `.211` (**der**): al revés. .152: **de goma**, sin driver ni `--ee` |
| Modelo de la IK | el de Unitree | **el del G1 de UTEC** (modo 15, muñecas 5010, masas de la balanza) **con las manos de cada robot**: RH56E2 y acoples, o las de goma (`modelo_ik.py`) |
| PC2 | x86_64, Ubuntu 22.04, red interna en `eth0` | **Jetson (ARM64), Ubuntu 20.04, red interna en `eth1`**: `env_tv` se instala distinto (`instalar.sh`); el driver de las manos y la cámara usan también `env_tv`, sin sudo |
| Entrada | el peso no existe; los brazos van solos a 0° al arrancar | el peso **sube de 0 a 1 en 2 s** y los brazos **se quedan donde los tiene la locomoción**; al pulsar `r` pasan **en 2 s** a seguir al operador |
| Salida (`q`) | 0°, abrir manos, postura inicial; brazos y piernas sin fuerza | 0°, abrir manos, postura de la locomoción y **el peso baja a 0 en 2 s**: el robot sigue de pie con sus brazos |

`lanzar_teleop.py` hace todo esto sin tocar el código de Unitree. Detalle en su cabecera.

**Por qué no basta con el `--motion` de Unitree tal cual.** Medido en el simulador (§8) con el
`G1_29_ArmController` original:
- al crearse, el peso **salta de 0 a 1 en un paso** y los brazos **arrancan hacia 0°** a 1,8 rad/s, antes de
  pulsar `r`, con el robot de pie;
- al salir, el peso solo baja si los brazos llegan a menos de 0,05 rad de 0° en 5 s. Unitree manda esos 0°
  **sin par de gravedad** y los brazos, con las RH56E2, se quedan a 0,059 rad, así que **el programa termina con
  el peso en 1**. Qué hace el robot real cuando `rt/arm_sdk` deja de llegar con el peso en 1 no se sabe.

**El modelo de la IK.** El de Unitree es un G1 con muñecas 4010 y manos Dex3. Con el de UTEC, L_ee y R_ee quedan
**5 mm** más lejos, y el **par de gravedad** que el teleop suma a los brazos es **un 40 % mayor** en el hombro y el
codo (5,1 frente a 3,6 N·m en el hombro a 0°), por las muñecas 5010, las manos y los acoples
(`env_tv/bin/python modelo_ik.py`). Con las manos de goma (0,32 kg por muñeca y mano, frente a 0,97 con las RH56E2)
son **2,9 N·m**: con el modelo de las RH56E2, el par de gravedad del .152 sobraría y los brazos quedarían algo
desviados hacia arriba. Por eso cada robot usa el suyo.

## 3. Los scripts del PC

| Archivo | Qué hace | ¿Mueve el robot? |
|---|---|---|
| `teleop_xr.sh` | arranca el teleop; `./teleop_xr.sh parar` detiene el teleop (como Ctrl-C), la cámara y el driver de las manos | **sí** |
| `comun.sh` | el reenvío por SSH; lo cargan los demás y sin él no funciona ninguno | no |
| `estado.sh [s]` | `rt/lowstate`, si alguien publica en `rt/arm_sdk`, `CheckMode`, FSM de la locomoción y si responden las manos | no |
| `manos.sh leer\|abrir\|dedo\|borrar-error` | diagnóstico de las manos (`leer` es solo lectura) | `leer` no; el resto, los dedos |
| `robot.sh [comprobar\|gafas]` | `comprobar`: red, clave SSH y estado. `gafas`: URL para las Quest. Sin argumentos: terminal en el robot | no |

`teleop_xr.sh`, `comun.sh`, `estado.sh` y `manos.sh` son los mismos que hay en `~/utec/teleoperacion` del robot.
Tienen que estar **en la misma carpeta**; lánzalos por su ruta, sin enlaces simbólicos.

**Qué robot**: los dos G1 están en la WiFi del H1-2, `UTEC_H1_2`. Sin nada, los scripts van al **.151**
(`unitree@192.168.0.151`, el de las RH56E2); **`G1=152`** delante de cualquiera de ellos va al **.152** (el de las
manos de goma):

```bash
G1=152 ./robot.sh comprobar
G1=152 ./teleop_xr.sh
```

El aviso de antes de mover el robot dice cuál es (`ROBOT: G1 .152 (manos de goma)`, de su `robot.conf`). Otra
dirección: `ROBOT_SSH=unitree@<IP> ./teleop_xr.sh`. Si un robot no tiene la clave SSH de este PC, los scripts piden
la contraseña de `unitree` cada vez, hasta hacer `ssh-copy-id unitree@<IP>` (el .151 ya la tiene; el .152, no).

## 4. Antes de cada sesión

- **El robot con el arnés cerca**: aunque la locomoción lo sostiene, con L2 + B o un fallo cae. Ya ha caminado
  teleoperado (§9), pero quedan cosas por comprobar.
- Una persona con el **mando de Unitree** en la mano y nadie al alcance de los brazos.
- El G1 **de pie en modo Regular (R1+Y en el .151; FSM 501; el .152 está por ver)**, no en Running (R2+A) ni en Debug.
- Comprobación de solo lectura:

  ```bash
  cd ~/Documents/g1_utec/g1_teleoperation/scripts
  ./robot.sh comprobar
  ```

  Tiene que salir el `robot.conf` del robot que toca, `rt/lowstate`, `rt/arm_sdk: nadie publica`, `CheckMode` con
  `'ai'` (no `''`), `FSM 501` y, en el .151, las dos manos con `Modbus TCP :6000 si` (en el .152, `manos: de
  goma`). El .151 da `mode_machine 5` (ver §9).

## 5. Ejecutar

```bash
cd ~/Documents/g1_utec/g1_teleoperation/scripts
./teleop_xr.sh          # en una terminal interactiva: hacen falta las teclas r y q
G1=152 ./teleop_xr.sh   # el G1 de las manos de goma: solo los brazos
```

1. Arranca la cámara y, en el .151, el driver de las manos, que **las abre nada más arrancar**. Antes comprueba
   que nadie publica en `rt/arm_sdk` y, en el .151, que contestan las dos manos.
2. `lanzar_teleop.py` pregunta el modo: si el robot está en Debug (`CheckMode` con `''`), **no arranca**.
3. Al crearse el controlador de los brazos, **el peso de arm_sdk sube de 0 a 1 en 2 s** y los brazos **se quedan
   en la postura de la locomoción**. Al final imprime la URL para las gafas.
4. **En las Quest 3**: la misma WiFi que el robot y, en el navegador, la URL completa con su `?ws=`:
   `https://<IP WiFi del G1>:8012/?ws=wss://<IP WiFi del G1>:8012`. Aviso del certificado: *Avanzado →
   Continuar*. Después, «Virtual Reality» **sin los mandos en la mano**, y permitir todo. `./robot.sh gafas`
   imprime la URL.
5. Pon los brazos como los tiene el robot y pulsa **`r`**: en 2 s los brazos pasan de su postura a la tuya, y
   en el .151 los dedos te siguen. Desde ese momento, el compañero puede caminar con el mando. **Despacio**: los brazos, con
   las manos, mueven el centro de masas.
6. **`q`** para salir, en este orden:
   1. Los dos **brazos van a 0°**: antebrazos hacia delante. Hasta aquí las manos siguen a las tuyas.
   2. Se **abren del todo las dos manos**. El teleop espera a leerlas abiertas, como mucho 3 s. En el .152 no
      hay nada que abrir y se pasa al siguiente.
   3. Los **brazos vuelven a la postura de la locomoción**, la que tenían al lanzar el teleop.
   4. **El peso de arm_sdk baja a 0 en 2 s**: los brazos vuelven a la locomoción. Esto se hace siempre, aunque
      falle alguno de los pasos anteriores.

   Si no se llegó a pulsar `r`, los brazos no se han movido: solo se abren las manos y baja el peso. El robot
   **sigue de pie** con su locomoción al terminar.
7. Parar la cámara y el driver de las manos: `./teleop_xr.sh parar`. Si el teleop siguiera vivo, le manda
   SIGINT solo a su proceso principal (la misma salida que `q`).

   **Mejor `q` que Ctrl-C en la terminal**: Ctrl-C llega también a los procesos hijos del teleop, y el de las
   manos muere antes de poder abrirlas. Los brazos y el peso salen igual.

## 6. Si se corta el SSH

Igual que en el H1-2: **el teleop sale solo, con la misma secuencia que `q`**, si se cuelga el terminal (~0,2 s)
o si el PC deja de responder al ping durante 3 s. Después, `./teleop_xr.sh parar`. Con el robot caminando importa
más: el compañero del mando debe **parar el robot** si ve que los brazos vuelven solos.

## 7. Logs y problemas

Los logs están en el robot, en `~/utec/teleoperacion/logs/`: `teleop.log`, `manos.log` e `image_server.log`. La
terminal muestra `teleop.log` en directo; las líneas de `lanzar_teleop` dicen el `CheckMode`, la FSM, el peso y
cada paso de la salida.

| Síntoma | Causa y solución |
|---|---|
| `el robot esta en Debug` y no arranca | El G1 no está en la locomoción: ponlo de pie en Regular (R1+Y) con el mando |
| Las manos no responden en `.210` / `.211` | Un cable del repartidor de red de la espalda suelto (pasó el 2026-11-26). `./estado.sh` dice si contestan |
| `rt/arm_sdk: ALGUIEN PUBLICA` y no arranca | Hay otro teleop (u otro programa) mandando los brazos, en el robot o en otro PC de la red |
| `Falta .../robot.conf con MANOS=rh56e2 o MANOS=goma` | El robot no tiene su `robot.conf`: el de [`scripts_robot/robots/`](scripts_robot/robots/) ([`scripts_robot/README.md`](scripts_robot/README.md) §5) |
| `Las manos RH56E2 no contestan` y no arranca | El .151 con alguna mano sin red: el cable del repartidor de la espalda. Sin esta comprobación, Unitree espera 5 s a las manos y sigue sin ellas |
| `Falta el numero de serie de la D435i` | `D435I=POR_RELLENAR` en `robot.conf` ([`scripts_robot/README.md`](scripts_robot/README.md) §5). `arrancar.sh` lo copia a `cam_config_server.yaml` |
| `Este robot.conf es de G1 .15x ... es el de otro G1` | Se copió al robot el `robot.conf` del otro G1 (por cable son indistinguibles): pon el suyo |
| `robot.conf dice MANOS=goma ... sin --ee` (o al revés) | Se le pasó a `lanzar_teleop.py` un `--ee` que no corresponde a las manos del robot: lánzalo con `arrancar.sh` |
| La mano izquierda del operador mueve la derecha del robot | Las IP de las manos están al revés: `./manos.sh dedo izq` y cambiar `LEFT_IP`/`RIGHT_IP` |
| La página de las gafas carga pero no se ve nada | Falta `?ws=` en la URL, o el *Socket URI* no lleva el puerto |
| La imagen se congela al entrar en VR | La WiFi sin Internet: `~/utec/teleoperacion/vuer_offline.sh` (con Internet una vez; como en el H1-2) |
| Un dedo deja de moverse (`err` 5) | `./teleop_xr.sh parar`, `./manos.sh borrar-error izq` (o `der`) |

## 8. Pruebas en simulación (este PC)

```bash
cd ~/Documents/g1_utec/g1_teleoperation/sim
./probar.sh                 # cuatro casos: normal, sin pulsar r y con fallos en la salida (RH56E2), y goma
VISOR=1 ./probar.sh normal  # mirándolo en MuJoCo
```

- `sim_g1_arm_sdk.py`: el **G1 de UTEC** (el URDF del modo 15 con las RH56E2, 38,17 kg, o con `--manos goma` el
  de las manos de goma, 36,85 kg) en MuJoCo, colgado y sin contactos, con un **control de locomoción falso** que atiende `rt/arm_sdk` como se ha descrito en §1 y **manos
  falsas** por DDS. **No es el control de Unitree**: su postura de los brazos es inventada y no camina.
- `prueba_teleop_g1.py`: el `G1_29_ArmController` y el `Inspire_Controller_FTP` **reales** de Unitree (`817fb00`)
  con los parches de `lanzar_teleop.py`, y la IK con el modelo de UTEC llevando las muñecas a una postura
  conocida, sin gafas.

Cada caso le pone a la carpeta de prueba su `robot.conf` (`MANOS=rh56e2` o `MANOS=goma`), como en el robot.

**Resultado del 2026-11-26: los cuatro casos OK.**

| Caso | Qué se comprueba (y lo medido) |
|---|---|
| normal | la IK carga el modelo de UTEC; el peso sube en 1,9 s sin saltos; mientras sube, los brazos se mueven 0,002 rad; al pulsar `r` las muñecas llegan a 0,2 cm de lo pedido; salida en 4,4 s con las manos abiertas, el peso en 0 y los brazos a 0,000 rad de la postura de la locomoción; velocidad máxima de los brazos 1,75 rad/s |
| sin pulsar `r` | los brazos no se mueven (0,003 rad); salida en 2,9 s: abrir manos y bajar el peso |
| fallos en la salida | los dos movimientos de los brazos fallan a propósito: las manos abren y **el peso baja a 0 igual** |
| goma (el .152) | `robot.conf` con `MANOS=goma`: la IK carga el modelo de las manos de goma (36,85 kg); `lanzar_teleop` acepta los argumentos de `arrancar.sh`, sin `--ee`, y rechaza `--ee=inspire_ftp` y `--input-mode=controller`. Sin control de manos: peso arriba en 1,9 s con los brazos quietos (0,001 rad), muñecas a 0,2 cm de lo pedido y salida en 3,7 s sin esperar a las manos, con el peso en 0 y los brazos a 0,000 rad de la postura de la locomoción |

Además, sin robot: `estado_g1.py` contra el simulador (lee `rt/lowstate` y detecta otro publicador en
`rt/arm_sdk`), `manos.py` contra una mano Modbus falsa, el reenvío por SSH, que `lanzar_teleop.py` **no arranca
sin `--motion`** ni con otro `--arm`, y su `--help`.

La simulación **no cubre**: la locomoción real de Unitree (cómo mezcla de verdad el peso, la cintura y el par, y el
equilibrio al mover los brazos caminando), las gafas, la cámara, las manos reales ni el Jetson.

## 9. En el robot

### G1 .151, con las RH56E2

**Hecho el 2026-11-26** (por SSH a `unitree@192.168.0.151`, con el robot colgado del arnés):

| Qué | Resultado |
|---|---|
| El PC2 | Jetson (L4T R35.3.1), Ubuntu 20.04, Python 3.8 del sistema, 8 núcleos, 15 GB. **Red interna en `eth1`** (`eth0` es un USB-Ethernet sin cable). En la red interna, además, `.161` (PC1) y `.120` |
| Instalación | `instalar.sh` con Miniforge en `~/miniforge3`: `OK pinocchio 3.1.0 numpy 1.26.4 torch 2.3.0` y `modelo_ik.py` igual que en el PC. `pyrealsense2` de PyPI no carga (pide glibc 2.32-2.34; el Jetson tiene la 2.31): se usa el de conda-forge (2.58.3, sin CUDA), que ve la cámara **sin sudo** |
| Cámara | D435i de la cabeza, n.º de serie `401622072718`, firmware 5.15.1.55, enchufada por USB-C pero a **USB 2.1**: color 640×480 a 27 fps medidos. El servidor de imagen del teleop la sirve. Hay además dos cámaras UVC en las muñecas (`/dev/video0-3`, «Abham Image»), sin usar |
| Manos | Responden en `.210` y `.211` (hubo que recolocar un cable del repartidor de la espalda). **`.210` es la IZQUIERDA y `.211` la DERECHA**, comprobado moviendo un dedo de cada una: al revés que en el H1-2. Mismos registros que la RH56DFTP; `ANGLE_SET` hay que escribirlo **en bloque desde 1486**: un registro suelto en 1486 + 3 movió el anular |
| Modo | `CheckMode` `'ai'`; FSM **501** en Regular (R1+Y) |
| arm_sdk (`prueba_arm_sdk.py`) | peso de 0 a 1 en 1,9 s, 5 s quieto y a 0 en 2,2 s, sin aborto. Las muñecas se desplazan ~1,5° mientras cambia el peso (la consigna pasa de la locomoción a la nuestra y vuelve) y, con el peso en 1, nada se mueve más de 0,3°: **la locomoción atiende `rt/arm_sdk`** |
| Certificado y Vuer | certificado para `192.168.0.151` en `~/.config/xr_teleoperate`; `vuer_offline.sh` → `OFFLINE: si` |
| **Teleop completo** (`./teleop_xr.sh`, ~6,5 min) | con las Quest 3: **brazos y dedos siguen al operador, y el G1 camina con el mando moviendo los brazos sin caerse**. En el log: `CheckMode` `'ai'`, FSM 501, entrada con `r` en 2 s y salida con `q` completa (brazos a 0° en 1,3 s, manos abiertas en 0,5 s, brazos a la postura de la locomoción en 1,0 s, peso a 0), sin errores. El driver lee las dos manos a 200 Hz |

**Pendiente**, de menos a más:

1. **`mode_machine`**: `rt/lowstate` dice **5** (en la tabla de Unitree, 29 DOF con muñecas 4010), y la app dijo 15
   (muñecas 5010). El .152 también da 5. La IK usa el modelo del 15; entre los dos, la mano se desplaza 5 mm.
   Aclarar cuál es.
2. **Qué hace la locomoción si `rt/arm_sdk` deja de llegar con el peso en 1** (por ejemplo `kill -9` del teleop):
   si mantiene la última consigna o devuelve los brazos. De eso depende cuánto importa un fallo del PC2.
3. **La cintura**: `G1_29_ArmController` manda también la cintura, fija en su ángulo inicial y con kp 300, como hace
   Unitree en `--motion`. Con ella así el robot caminó sin caerse; falta ver si conviene dejársela a la locomoción.
4. El ajuste de los dedos: el retargeting de Unitree usa el modelo de su Inspire (dedos de 0 a 1,7 rad, pulgar de
   0 a 0,5 y de −0,1 a 1,3) y la RH56E2 tiene otros rangos (0–1,438, 0–0,62 y 0–1,658 rad). Funciona igual, pero
   la correspondencia de los dedos no será exacta.
5. Que `L2 + B` del mando es el amortiguamiento en el .151, como en el manual de Unitree.
6. `rt/lowstate` llega a ~1000 msg/s (no 500): no afecta, pero no se sabe por qué.
7. Un teleop corto con los scripts de `robot.conf`. Se pusieron en el robot el 2026-11-27, con su `robot.conf` (el
   de antes quedó en `~/utec/respaldo_teleoperacion_antes_robot_conf_20261127.tgz`). Sin mover el robot, se comprobó
   que reconoce su MAC, que las dos manos contestan y se leen, y que `lanzar_teleop.py` no arranca sin `--ee`, con
   `--input-mode=controller` ni sin `--motion`.

### G1 .152, con las manos de goma

Su PC2 lleva **la misma imagen clonada** que el .151: la red interna en `eth1` con `192.168.123.164` y la misma
clave de host SSH. Por cable no se distingue del .151, así que todo se hizo **por la WiFi** (`192.168.0.152`, MAC de
`wlan0` `f8:f6:b7:f1:79:76`). Su `robot.conf` es [`scripts_robot/robots/g1_152.conf`](scripts_robot/robots/g1_152.conf).

**Hecho el 2026-11-27**, por SSH con contraseña (todavía no tiene la clave de este PC); hasta la prueba de arm_sdk,
sin mover el robot:

| Qué | Resultado |
|---|---|
| El PC2 | Jetson, Ubuntu 20.04.6, 1,8 TB libres. No tenía nada de la teleoperación (ni `~/utec` ni conda) |
| Instalación | `rsync` de `home_unitree/`, su `robot.conf` y `montar.sh`: `xr_teleoperate` `817fb00` con los mismos submódulos, Miniforge y `instalar.sh`: `OK pinocchio 3.1.0 numpy 1.26.4 torch 2.3.0`, y `modelo_ik.py` igual que en el PC (con las manos de goma, 36,85 kg y 2,88 N·m en el hombro a 0°). `vuer_offline.sh` → `OFFLINE: si` |
| `robot.conf` | `config_robot.py` lo lee y la `MAC_WIFI` es la de este robot |
| Cámara | D435i, n.º de serie **`262522074781`**, firmware 5.15.1.55, a **USB 2.1**, como la del .151. El servidor de imagen del teleop (sin sudo) la abre a 640×480 y por ZMQ llegan **30 imágenes/s** |
| Certificado | para `192.168.0.152` (y `127.0.0.1`, `192.168.123.164`), hasta 2036, en `~/.config/xr_teleoperate` |
| Estado (`estado.sh`) | `mode_machine` **5**, como el .151; `rt/lowstate` a ~1040 msg/s; `rt/arm_sdk: nadie publica`; `CheckMode` `'ai'` y FSM 0 (no estaba en Regular); `manos: de goma` |
| `lanzar_teleop.py` | arranca (`--help`) y **no arranca** sin `--motion`, con `--ee=inspire_ftp` ni con `--input-mode=controller` |
| Modo, colgado y de pie en Regular (**R1+Y**, como el .151) | `CheckMode` `'ai'` y FSM **501** |
| arm_sdk (`prueba_arm_sdk.py`), con el modelo de las manos de goma | peso de 0 a 1 en 1,9 s, 4,9 s quieto y a 0 en 2,2 s, sin aborto. **Con el peso en 1, nada cambia más de 0,02°**. Mientras cambia el peso, la muñeca izquierda se va 2,2° en roll (0,9° en pitch) y se queda ahí al devolverla a la locomoción: la locomoción parece dejarla donde cae, dentro de una holgura. En el .151 fueron ~1,5° |
| Teleop sin pulsar `r` (`G1=152 ./teleop_xr.sh` y `q`) | el peso sube, los brazos no se mueven y la salida baja el peso a 0 |
| **Teleop completo** (~2 min, colgado) | con las Quest 3: **los brazos siguen al operador sin problemas con el robot moviéndose con el mando**. En el log: `CheckMode` `'ai'`, FSM 501, modelo de las manos de goma, entrada con `r` y salida con `q` completa (brazos a 0° en 1,3 s, a la postura de la locomoción en 1,0 s, peso a 0; sin paso de manos), sin errores |

**Falta:** la clave SSH de este PC (`ssh-copy-id unitree@192.168.0.152`), para no escribir la contraseña cada vez.

## 10. Qué hay en esta carpeta

```
g1_teleoperation/
├── README.md        esto
├── scripts/         los del PC (§3)
├── scripts_robot/   lo que va en el robot y cómo instalarlo: README.md
│   ├── robots/                       g1_151.conf y g1_152.conf: el robot.conf de cada G1
│   ├── home_unitree/                 el $HOME del robot (/home/unitree), para un rsync
│   │   ├── utec/teleoperacion/       lanzar_teleop.py, config_robot.py, modelo_ik.py, modelo/ (los dos URDF),
│   │   │                             arrancar.sh, estado_g1.py, manos.py, prueba_arm_sdk.py...
│   │   ├── inspire_ftp_dual_driver.py
│   │   └── pc2_offline/src/          unitree_sdk2_python 1.0.1 e inspire_hand_sdk (los del H1-2)
│   └── xr_teleoperate_cambios/       cam_config_server.yaml (solo la D435i)
└── sim/             simulador y pruebas (§8)
```
