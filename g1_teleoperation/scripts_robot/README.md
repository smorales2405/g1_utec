# scripts_robot — lo que corre en el G1 para la teleoperación XR

`scripts/teleop_xr.sh`, lanzado desde el PC, ejecuta la teleoperación **en el PC2 del G1** (el Jetson). Esta
carpeta es todo lo que hace falta allí, y los pasos para instalarlo.

- Sale de la del H1-2 (`h1_2_utec/h1_2_teleoperation/scripts_robot`). Lo que no cambia está copiado tal cual:
  `enviar.py`, `prueba_gafas.py`, `vuer_offline.sh` y los dos SDK de `pc2_offline/src`. El driver de las manos
  solo cambia las IP.
- **Instalado en el G1 de UTEC el 2026-11-26** siguiendo §4 (con `montar.sh`, que hace los pasos 3 y 4 de una
  vez). Lo que se encontró y probó allí está en [`../README.md`](../README.md) §9.
- Los valores propios del robot (IP WiFi, cámara, manos) **no están parametrizados**: §5 dice qué línea cambiar
  y cómo averiguar el valor.

Cómo se usa la teleoperación, una vez instalada: [`../README.md`](../README.md).

---

## 1. Qué hay y dónde va

`home_unitree/` reproduce el `$HOME` del robot (`/home/unitree`): todo cae en su sitio con un solo `rsync` (§4,
paso 2).

| En esta carpeta | En el robot | Qué es |
|---|---|---|
| `home_unitree/utec/teleoperacion/teleop_xr.sh`, `comun.sh` | `~/utec/teleoperacion/` | punto de entrada y entorno; fuera del robot, reenvían por SSH |
| `…/arrancar.sh`, `parar.sh` | `~/utec/teleoperacion/` | arranque (comprueba `rt/arm_sdk`, cámara, driver de las manos, teleop `--motion`) y parada |
| `…/lanzar_teleop.py` | `~/utec/teleoperacion/` | lanza `teleop_hand_and_arm.py` con los cambios para el G1 (solo `--motion`, entrada y salida suaves con el peso, salida que abre las manos, corte del SSH = `q`) |
| `…/modelo_ik.py`, `modelo/g1_29dof_with_RH56E2_hands.urdf` | `~/utec/teleoperacion/` | el modelo de la IK del G1 de UTEC. El URDF es copia de `ros2_g1_ws/src/g1_edu_inspire_rh56e2_description/urdf/` |
| `…/estado.sh`, `estado_g1.py` | `~/utec/teleoperacion/` | estado del robot, solo lectura |
| `…/manos.sh`, `manos.py` | `~/utec/teleoperacion/` | `leer`, `abrir`, `dedo` (qué IP es cada mano) y `borrar-error` |
| `…/instalar.sh`, `montar.sh` | `~/utec/teleoperacion/` | `instalar.sh` crea `env_tv` en el Jetson (§4, paso 4); `montar.sh` hace los pasos 3 y 4 seguidos (clon de `xr_teleoperate`, Miniforge e `instalar.sh`) |
| `…/prueba_arm_sdk.py` | `~/utec/teleoperacion/` | primera prueba de `rt/arm_sdk` sin gafas: sube el peso, mantiene los brazos y lo baja (§6, paso 5) |
| `…/enviar.py`, `prueba_gafas.py`, `vuer_offline.sh`, `README.md`, `certs/san.cnf` | `~/utec/teleoperacion/` | órdenes por IPC, prueba de las gafas sin DDS, la página de Vuer sin Internet, el README del robot y la plantilla del certificado |
| `home_unitree/inspire_ftp_dual_driver.py` | `~/` | driver de las manos, Modbus TCP ⇄ DDS (`rt/inspire_hand/*`). El del H1-2 con las IP `192.168.123.210/.211` y con `err`/`status`/`temperature` en el orden de bytes de la RH56E2 (el SDK de Inspire los cambiaba por parejas de dedos) |
| `home_unitree/pc2_offline/src/unitree_sdk2_python` | `~/pc2_offline/src/` | `unitree_sdk2py` 1.0.1, el del H1-2. Tiene `LocoClient` y `MotionSwitcherClient` del G1 |
| `home_unitree/pc2_offline/src/inspire_hand_sdk` | `~/pc2_offline/src/` | `inspire_sdkpy` 1.0.0 con el parche `uint16` del H1-2 |
| `xr_teleoperate_cambios/teleop/teleimager/cam_config_server.yaml` | `~/utec/teleoperacion/xr_teleoperate/teleop/teleimager/` | cámara: solo la D435i de la cabeza, por ZMQ. Se copia **después** de clonar `xr_teleoperate`, y hay que poner su número de serie |

Los dos SDK se instalan en modo editable en `env_tv`: **tienen que quedarse en esa ruta**.

**No está aquí:** `xr_teleoperate` (Unitree, `817fb00` + 3 submódulos, 404 MB, `git clone`), `env_tv` (conda,
varios GB) y `cert.pem`/`key.pem`, que se generan en el robot. **Las claves privadas no van a git.**

## 2. Qué se ejecuta en el robot

```
~/utec/teleoperacion/teleop_xr.sh               (llega por: ssh -t unitree@<ip> "cd ~/utec/teleoperacion && ./teleop_xr.sh")
  └─ comun.sh                                   PYTHONNOUSERSITE=1, sin CYCLONEDDS_URI
  └─ arrancar.sh
       0. env_tv/bin/python estado_g1.py eth1 --arm-sdk     ¿alguien publica en rt/arm_sdk? -> no sigue
       1. env_tv/bin/python -m teleimager.image_server --rs     D435i → ZMQ :55555          logs/image_server.log
       2. env_tv/bin/python ~/inspire_ftp_dual_driver.py --network eth1 --no-touch        logs/manos.log
       3. env_tv/bin/python lanzar_teleop.py --arm=G1_29 --ee=inspire_ftp --motion --input-mode=hand --headless
                --network-interface=eth1 --img-server-ip=127.0.0.1     → teleop_hand_and_arm.py (Vuer :8012)
                                                                          logs/teleop.log (el terminal ve un tail)
```

En el H1-2 el driver de las manos tenía su propio `teleop_venv` con el Python 3.10 del sistema. El Jetson trae
Ubuntu 20.04 (Python 3.8), así que aquí usa `env_tv`, que ya tiene todo lo que necesita.

## 3. Requisitos del robot

- **G1 EDU-U6, `mode_machine` 15**, con las RH56E2 por **Modbus TCP en `192.168.123.210` y `.211`**. Que las
  manos respondan ahí es lo supuesto (como en el H1-2); se comprueba en el paso 6.
- **PC2 = Jetson** (`uname -m` → `aarch64`), usuario `unitree`, la red interna `192.168.123.164` (en el G1 de UTEC,
  `eth1`).
- **La D435i de la cabeza en el Jetson**: `lsusb | grep 8086:0b3a`.
- **WiFi en el PC2**, en la misma red que las Quest. Si el G1 no tiene, un adaptador como el TP-Link del H1-2
  (`h1_2_utec/robot_config/wifi_tplink_tx20u_plus`, que es para x86: hay que ver si su driver compila en el Jetson).
- **conda para aarch64**: en el G1 de UTEC, Miniforge en `~/miniforge3` (solo conda-forge). `instalar.sh` también
  acepta `~/miniconda3`, que es lo que pone el README de teleimager para el Jetson.
- **Internet en el robot** durante la instalación.
- **Un PC con cable** a la red interna (puerto de depuración, IP fija `192.168.123.x/24`) hasta que funcione la WiFi.

## 4. Instalación en el G1

Desde la raíz del repositorio `g1_utec` en el PC. `<IP>` es la del robot: la del cable (`192.168.123.164`) hasta
tener la WiFi.

**Paso 0 — acceso por clave y qué hay**

```bash
ssh-copy-id unitree@192.168.123.164
ssh unitree@192.168.123.164 'hostname; uname -m; lsb_release -ds; whoami; ip -br addr; ls ~; lsusb | grep 8086'
```

Tiene que dar `aarch64` y el usuario `unitree`. Mira también si ya hay `~/utec`, `~/miniconda3`, otro
`xr_teleoperate` o algo de Unitree que use la D435i.

**Paso 1 — WiFi.** Conectar el PC2 a la red de las gafas y apuntar `<IP>`. Mejor reservarla en el router.

**Paso 2 — copiar los archivos**

```bash
rsync -a g1_teleoperation/scripts_robot/home_unitree/ unitree@<IP>:~/
```

**Paso 3 — `xr_teleoperate` de Unitree, en el commit del H1-2**

```bash
ssh unitree@<IP> 'cd ~/utec/teleoperacion && git clone https://github.com/unitreerobotics/xr_teleoperate.git &&
    cd xr_teleoperate && git checkout 817fb00 && git submodule update --init --recursive &&
    cp teleop/teleimager/cam_config_server.yaml teleop/teleimager/cam_config_server.yaml.orig'
scp g1_teleoperation/scripts_robot/xr_teleoperate_cambios/teleop/teleimager/cam_config_server.yaml \
    unitree@<IP>:utec/teleoperacion/xr_teleoperate/teleop/teleimager/
```

Los submódulos quedan en `teleimager 57cf2a4`, `televuer 766de45` y `dex-retargeting d7753d3`, como en el H1-2.
`lanzar_teleop.py` sustituye métodos de `G1_29_ArmController` de ese commit: con otro, revisar que siguen igual.

**Paso 4 — conda y el entorno `env_tv`** (en el robot; tarda y descarga varios GB)

```bash
# conda para aarch64, si no lo hay (Miniforge: solo conda-forge, sin los terminos de uso de Anaconda):
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh -O /tmp/Miniforge3.sh
bash /tmp/Miniforge3.sh -b -p ~/miniforge3 && rm /tmp/Miniforge3.sh
# el entorno:
bash ~/utec/teleoperacion/instalar.sh 2>&1 | tee ~/utec/teleoperacion/instalar.log
```

Tiene que terminar con `OK pinocchio 3.1.0 numpy 1.26.4 torch 2.3.0…`, la comprobación de `modelo_ik.py` y
`### LISTO`. **Probado en el G1 de UTEC el 2026-11-26.** Lo que se sabe:

- conda-forge para `linux-aarch64` tiene `pinocchio 3.1.0` (con casadi), `nlopt 2.7.1`, `pyqt 5.15` y la librería C
  de `cyclonedds 0.10.5` (resolución con `CONDA_SUBDIR=linux-aarch64 conda create --dry-run`);
- PyPI tiene ruedas `aarch64` de `torch 2.3.0`, `pyrealsense2`, `casadi`, `pupil-labs-uvc`, `opencv-python` y
  `rerun-sdk 0.20.1` (esta última pide glibc 2.31: Ubuntu 20.04 la tiene justa);
- PyPI **no** tiene ruedas `aarch64` de `cyclonedds 0.10.2`, `nlopt <2.8` ni `PyQt5`. Por eso las dos últimas
  vienen de conda, y el `cyclonedds` de Python se compila contra la librería C de conda (`CYCLONEDDS_HOME`). Si
  esa compilación falla, la alternativa es la de Unitree: compilar cyclonedds 0.10.x en `~/cyclonedds/install`.

**Paso 4b — página de Vuer sin Internet** (con Internet): `~/utec/teleoperacion/vuer_offline.sh`, que tiene que
acabar en `OFFLINE: si`. Es el mismo del H1-2.

**Paso 5 — valores propios del robot.** Todo lo de §5 **antes** de lanzar nada.

**Paso 6 — comprobaciones que no mueven nada**

```bash
ssh -t unitree@<IP> '~/utec/teleoperacion/estado.sh'          # lowstate, arm_sdk, CheckMode, FSM, manos
ssh -t unitree@<IP> '~/utec/teleoperacion/manos.sh leer'      # tienen que contestar las dos
ssh unitree@<IP> 'cd ~/utec/teleoperacion/xr_teleoperate/teleop/teleimager && PYTHONNOUSERSITE=1 ../../../env_tv/bin/python -m teleimager.image_server --cf'
```

El último lista las cámaras: de ahí sale el número de serie de la D435i (§5).

**Paso 7 — certificado HTTPS** para las gafas, con la IP WiFi (en el robot):

```bash
cd ~/utec/teleoperacion/certs
sed -i 's/^IP.2=.*/IP.2=<IP>/' san.cnf
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -keyout key.pem -out cert.pem -config san.cnf
chmod 600 key.pem
mkdir -p ~/.config/xr_teleoperate && cp cert.pem key.pem ~/.config/xr_teleoperate/
openssl x509 -in cert.pem -noout -ext subjectAltName      # tiene que aparecer <IP>
```

**Paso 8 — en el PC**

```bash
cd g1_teleoperation/scripts
ROBOT_SSH=unitree@<IP> ./robot.sh comprobar
```

O cambia la IP por defecto en `scripts/comun.sh` (línea 15) y `scripts/robot.sh` (línea 11), y la de
`home_unitree/utec/teleoperacion/comun.sh`, que es el mismo fichero.

## 5. Valores propios de cada robot

Rutas relativas a `home_unitree/`, es decir, al `$HOME` del robot.

| Qué | Dónde | Ahora | Cómo averiguarlo |
|---|---|---|---|
| **IP WiFi del robot** | `utec/teleoperacion/certs/san.cnf` (`IP.2`, paso 7) · `utec/teleoperacion/comun.sh:15` · en el PC, `scripts/comun.sh:15` y `scripts/robot.sh:11`, o la variable `ROBOT_SSH` | `192.168.0.151` (WiFi `UTEC_H1_2`) | `ip -br addr` en el robot |
| **Número de serie de la D435i** | `xr_teleoperate_cambios/…/cam_config_server.yaml:19` | `401622072718` | `python -m teleimager.image_server --cf` (paso 6) |
| **IP y lateralidad de las manos** | `inspire_ftp_dual_driver.py:67-68` · `utec/teleoperacion/manos.py:20` · `utec/teleoperacion/estado_g1.py:16` | izquierda `.210`, derecha `.211`, **comprobado** | ver abajo |
| **Interfaz de la red interna** | `utec/teleoperacion/arrancar.sh:12` y `comun.sh:29` (`IFACE`) | `eth1` | `ip -br addr \| grep 192.168.123` |
| **`sudo`** | — | pide contraseña; ya no hace falta (la cámara va sin sudo) | — |

**IP y lateralidad de las manos:** las dos dicen `HAND_ID 1` y no hay registro que distinga la izquierda de la
derecha: solo se sabe mirando. Con el robot **colgado** y nadie cerca, en el robot:

```bash
~/utec/teleoperacion/manos.sh leer            # solo lee; tienen que contestar las dos
~/utec/teleoperacion/manos.sh dedo izq        # ¿se mueve el índice de la mano IZQUIERDA del robot?
```

Si se mueve el de la derecha, intercambia las dos IP en los tres sitios de la tabla. Si no, la teleoperación
sale espejada. En el G1 de UTEC (2026-11-26): `.210` izquierda, `.211` derecha.

## 6. Primeras pruebas en el robot

Siguiendo [`../README.md`](../README.md) §9. Las cuatro primeras no mueven el robot:

1. **El teleop arranca**: `cd ~ && PYTHONNOUSERSITE=1 ~/utec/teleoperacion/env_tv/bin/python
   ~/utec/teleoperacion/lanzar_teleop.py --help` imprime la ayuda de `teleop_hand_and_arm.py`. Sin `--motion`
   tiene que negarse a arrancar.
2. **El estado**: `~/utec/teleoperacion/estado.sh`, con el robot en Debug y después de pie en Regular. Apuntar
   qué devuelven `CheckMode` y la FSM en cada caso.
3. **Las manos**: `manos.sh leer` y la lateralidad (§5).
4. **Las gafas, sin DDS**: el servidor de imagen (la línea `nohup … image_server` de `arrancar.sh`) y
   `cd ~/utec/teleoperacion && PYTHONNOUSERSITE=1 env_tv/bin/python prueba_gafas.py`; en las Quest,
   `https://<IP>:8012/?ws=wss://<IP>:8012`. Para todo con `./teleop_xr.sh parar`.
5. **arm_sdk sin seguir al operador**: robot colgado y de pie en Regular, `./teleop_xr.sh` y `q` sin pulsar `r`.
   Los brazos no deberían moverse.
6. **El teleop completo**, colgado; después en el suelo, quieto; después caminando despacio.

## 7. Mantener esta copia y el robot iguales

**Del repositorio al robot** (desde la raíz de `g1_utec`; no toca `env_tv`, `xr_teleoperate` ni `logs`):

```bash
rsync -a g1_teleoperation/scripts_robot/home_unitree/utec/teleoperacion/ unitree@<IP>:utec/teleoperacion/
```

Si cambias `teleop_xr.sh`, `comun.sh`, `estado.sh` o `manos.sh`, cópialos también a [`../scripts/`](../scripts/).
Si cambias el URDF del robot en `ros2_g1_ws`, copia el nuevo `g1_29dof_with_RH56E2_hands.urdf` a
`home_unitree/utec/teleoperacion/modelo/`: la IK y el par de gravedad salen de ahí.

**Del robot al repositorio** (con `R=unitree@<IP>`): lo mismo al revés, y con `rsync -anc -i` se ve qué ha
cambiado sin copiar nada.
