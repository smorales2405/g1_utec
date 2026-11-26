# teleoperacion — teleoperación XR del G1 con las Meta Quest 3

`xr_teleoperate` de Unitree (commit `817fb00`) para el G1 EDU-U6 con las manos Inspire RH56E2: **los brazos y los
dedos siguen a los del operador**, por `rt/arm_sdk`, mientras **la locomoción de Unitree sostiene al robot** y otra
persona lo maneja con el mando. Todo corre en el PC2 (Jetson). Copia versionada y detalle:
`g1_utec/g1_teleoperation` (README.md y scripts_robot/README.md).

**Funciona desde el 2026-11-26**: brazos y dedos siguen al operador y el robot camina con el mando sin caerse.

## Cómo se lanza

```bash
~/utec/teleoperacion/teleop_xr.sh          # = arrancar.sh
~/utec/teleoperacion/teleop_xr.sh parar    # = parar.sh
~/utec/teleoperacion/estado.sh             # solo lectura
```

1. **Antes:** G1 **de pie en modo Regular (R1+Y en este G1; FSM 501)**, colgado del arnés en las primeras pruebas, alguien con el
   mando, nadie cerca de los brazos. En Debug (`CheckMode` con `''`) el teleop no arranca.
2. **Gafas:** la WiFi del robot, `https://<IP>:8012/?ws=wss://<IP>:8012`, aviso del certificado → Avanzado →
   Continuar, y «Virtual Reality» **sin los mandos en la mano**.
3. El peso de arm_sdk sube en 2 s con los brazos quietos. Poner los brazos como el robot y pulsar **`r`**: en 2 s
   pasan a seguir al operador. **`q`** para salir: brazos a 0°, abrir las manos, brazos a la postura de la
   locomoción y el peso baja a 0 en 2 s. El robot sigue de pie.

Sin teclado: `env_tv/bin/python enviar.py r | q | estado`, si se lanzó con `--ipc`.

## Ficheros

| Fichero | Qué es |
|---|---|
| `arrancar.sh` / `parar.sh` | arranque y parada (`parar.sh` manda Ctrl-C al teleop si sigue vivo) |
| `teleop_xr.sh` / `comun.sh` / `estado.sh` / `estado_g1.py` | entrada, entorno (y reenvío por SSH desde el PC) y estado del robot |
| `lanzar_teleop.py` | lanza `teleop_hand_and_arm.py` con los cambios para el G1 sin tocar el código de Unitree |
| `modelo_ik.py`, `modelo/` | el modelo del G1 de UTEC para la IK y el par de gravedad (escribe `xr_teleoperate/teleop/g1_29_model_cache.pkl` en cada arranque) |
| `manos.sh` / `manos.py` | `leer`, `abrir`, `dedo izq\|der` y `borrar-error`, con el driver parado |
| `enviar.py`, `prueba_gafas.py`, `vuer_offline.sh` | los del H1-2: IPC, gafas sin DDS, página de Vuer sin Internet |
| `instalar.sh` | crea `env_tv` (conda, aarch64) |
| `certs/` | `san.cnf`: la plantilla del certificado |
| `xr_teleoperate/` | el repo de Unitree, con `cam_config_server.yaml` puesto solo con la D435i |
| `env_tv/`, `logs/` | el entorno conda y los logs de la última vez (`teleop.log`, `manos.log`, `image_server.log`) |

## Lo que hay que saber

- **Nunca sin `--motion`**: sin él, el teleop de Unitree llama a `ReleaseMode()` y el G1 de pie se caería.
  `lanzar_teleop.py` no arranca sin él y anula `Enter_Debug_Mode`.
- **Si se corta el SSH, el teleop sale solo como con `q`**. Lo que pasó queda en `logs/teleop.log`. El servidor de
  imagen y el driver de las manos siguen: `./teleop_xr.sh parar`.
- El driver de las manos **las abre nada más arrancar**.
- Siempre `PYTHONNOUSERSITE=1` (ya lo ponen los scripts).
