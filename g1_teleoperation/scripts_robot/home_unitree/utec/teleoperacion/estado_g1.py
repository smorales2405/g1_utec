#!/usr/bin/env python3
"""SOLO LECTURA: estado del G1 para la teleoperacion. No publica nada en DDS ni escribe en las manos.

    estado_g1.py [IFACE] [SEGUNDOS]      todo (por defecto la IFACE de robot.conf, o eth1, y 3 s)
    estado_g1.py [IFACE] --arm-sdk       solo si alguien publica en rt/arm_sdk; sale con 1 si hay alguien
    estado_g1.py --manos                 solo si las dos manos contestan en el puerto 6000; sale con 1 si no

  - rt/lowstate: si llega, frecuencia, mode_machine (el robot de UTEC es el 15), cintura y brazos, IMU.
  - rt/arm_sdk: si alguien publica (otro teleop, desde el robot o desde otro PC de la red) y con que peso.
  - CheckMode: '' es Debug (arm_sdk no hace nada y las piernas no se sostienen); otro nombre, la locomocion.
  - GetFsmId de la locomocion. En Debug no contesta.
  - robot.conf (config_robot.py): que robot es y que manos tiene.
  - Manos, si robot.conf dice MANOS=rh56e2: si responden al ping y al puerto Modbus TCP 6000 (192.168.123.210 y
    .211). Con MANOS=goma no hay nada que comprobar.
"""
import os, socket, subprocess, sys, threading, time
import numpy as np
import config_robot

MANOS = {"izq": "192.168.123.210", "der": "192.168.123.211"}   # las mismas que inspire_ftp_dual_driver.py
NOMBRES = (["cintura_yaw", "cintura_roll", "cintura_pitch"]
           + [f"{l}_{j}" for l in ("izq", "der")
              for j in ("hombro_pitch", "hombro_roll", "hombro_yaw", "codo", "muneca_roll", "muneca_pitch",
                        "muneca_yaw")])


class Ultimo:
    def __init__(self):
        self.cerrojo, self.msg, self.n = threading.Lock(), None, 0

    def __call__(self, msg):
        with self.cerrojo:
            self.msg, self.n = msg, self.n + 1


def escuchar(topico, tipo, segundos):
    from unitree_sdk2py.core.channel import ChannelSubscriber
    u = Ultimo()
    s = ChannelSubscriber(topico, tipo)
    s.Init(u, 10)
    time.sleep(segundos)
    s.Close()
    return u.msg, u.n


def arm_sdk(segundos=1.0):
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_
    msg, n = escuchar("rt/arm_sdk", LowCmd_, segundos)
    if not n:
        print("rt/arm_sdk: nadie publica")
        return False
    print(f"rt/arm_sdk: ALGUIEN PUBLICA ({n / segundos:.0f} msg/s, peso {msg.motor_cmd[29].q:.2f}). "
          "¿Otro teleop lanzado? Sin pararlo no se puede teleoperar")
    return True


def manos():
    # True si las dos contestan en el puerto Modbus TCP 6000
    todas = True
    for lado, ip in MANOS.items():
        ping = subprocess.run(["ping", "-c", "1", "-W", "1", "-q", ip], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0
        try:
            socket.create_connection((ip, 6000), timeout=1).close()
            modbus = True
        except OSError:
            modbus = False
        todas = todas and modbus
        print(f"mano {lado} {ip}: ping {'si' if ping else 'NO'}, Modbus TCP :6000 {'si' if modbus else 'NO'}")
    return todas


def main():
    if "--manos" in sys.argv:
        sys.exit(0 if manos() else 1)
    conf = config_robot.leer()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    iface = args[0] if args else conf.get("IFACE", "eth1")
    segundos = float(args[1]) if len(args) > 1 else 3.0
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    ChannelFactoryInitialize(int(os.environ.get("DDS_DOMINIO", "0")), iface)   # 1 = simulador
    if "--arm-sdk" in sys.argv:
        hay = arm_sdk()
        sys.stdout.flush()
        os._exit(1 if hay else 0)

    mac = {None: "sin MAC_WIFI", True: "MAC_WIFI la de este robot",
           False: "MAC_WIFI de OTRO robot: el teleop no arranca"}[config_robot.mac_coincide(conf)]
    print(f"robot.conf: {conf.get('NOMBRE', '?')}, MANOS={conf.get('MANOS', '?')}, IFACE={conf.get('IFACE', '?')}, "
          f"D435I={conf.get('D435I', '?')}, {mac}" if conf
          else f"robot.conf: NO EXISTE ({config_robot.RUTA}); el teleop no arranca")
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
    msg, n = escuchar("rt/lowstate", LowState_, segundos)
    if not n:
        print(f"rt/lowstate: NO LLEGA en {segundos:.0f} s por {iface}")
    else:
        q = np.degrees([msg.motor_state[i].q for i in range(12, 29)])
        rpy = np.degrees(list(msg.imu_state.rpy))
        print(f"rt/lowstate: {n / segundos:.0f} msg/s, mode_machine {msg.mode_machine}"
              f"{'' if msg.mode_machine == 15 else '  (OJO: el G1 de UTEC es el 15)'}")
        print(f"  IMU roll {rpy[0]:+.1f}  pitch {rpy[1]:+.1f}  yaw {rpy[2]:+.1f} grados")
        for i in range(0, 17, 3):
            print("  " + "   ".join(f"{NOMBRES[j]:>15s} {q[j]:+7.1f}" for j in range(i, min(i + 3, 17))))
    arm_sdk()

    from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
    msc = MotionSwitcherClient()
    msc.SetTimeout(2.0)
    msc.Init()
    codigo, modo = msc.CheckMode()
    if codigo != 0:
        print(f"CheckMode: sin respuesta (codigo {codigo})")
    elif not modo.get("name"):
        print(f"CheckMode: {modo} -> DEBUG: arm_sdk no hace nada y las piernas no se sostienen")
    else:
        print(f"CheckMode: {modo} -> locomocion de Unitree")
    try:
        from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
        loco = LocoClient()
        loco.SetTimeout(2.0)
        loco.Init()
        codigo, fsm = loco.GetFsmId()
        print(f"FSM de la locomocion: {fsm}" if codigo == 0 else f"FSM de la locomocion: sin respuesta ({codigo})")
    except Exception as e:
        print(f"FSM de la locomocion: no se pudo leer ({type(e).__name__}: {e})")

    if conf.get("MANOS") == "goma":
        print("manos: de goma (robot.conf), no se comprueban")
    else:
        manos()
    sys.stdout.flush()
    os._exit(0)   # sin esperar a que cyclonedds cierre sus hilos


if __name__ == "__main__":
    main()
