#!/usr/bin/env python3
"""G1 de UTEC en MuJoCo, colgado, con un control de locomocion FALSO que atiende rt/arm_sdk, y manos falsas.

Sirve para probar en este PC lo que hace lanzar_teleop.py con los brazos y las manos (entrada, teleop, salida),
sin el robot. No es el control de Unitree: este solo imita lo que se sabe de arm_sdk.

  - Modelo: el URDF del robot (modo 15 con las RH56E2, masas de la balanza), con la pelvis fija al mundo y sin
    contactos. Armadura de 0.01 kg m2 en cada junta (como el MJCF de Unitree) y 0.001 en los dedos.
  - "Locomocion": piernas, cintura y brazos con PD a una postura fija, POSTURA_LOCO (inventada, no la de Unitree).
  - rt/arm_sdk (unitree_hg LowCmd_): en cintura y brazos (motores 12..28) manda la mezcla
        q = w q_sdk + (1 - w) q_loco    kp y kd igual    tau = w tau_sdk
    con w = motor_cmd[29].q recortado a [0, 1]. Si deja de llegar, se queda con el ultimo mensaje (lo que haga el
    robot de verdad en ese caso no se sabe: hay que probarlo colgado).
  - Publica rt/lowstate (unitree_hg LowState_, mode_machine 15) a 500 Hz.
  - Manos: escucha rt/inspire_hand/ctrl/{l,r} y publica rt/inspire_hand/state/{l,r}; cada dedo va hacia su
    angle_set a VEL_DEDOS unidades/s (1000 = abierto). En el visor se mueven los dedos del modelo.

    python3 sim_g1_arm_sdk.py [--visor] [--log sim.csv] [--manos-cerradas] [--segundos N]

Usa el python3 del sistema (mujoco + unitree_sdk2py), en el dominio DDS 1 por lo (como unitree_mujoco).
"""
import argparse, os, re, signal, sys, tempfile, threading, time
import xml.etree.ElementTree as ET
import numpy as np
import mujoco

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
PAQUETE = os.path.join(REPO, "ros2_g1_ws", "src", "g1_edu_inspire_rh56e2_description")
URDF = os.path.join(PAQUETE, "urdf", "g1_29dof_with_RH56E2_hands.urdf")
SDK_MANOS = os.path.join(os.path.dirname(AQUI), "scripts_robot", "home_unitree", "pc2_offline", "src",
                         "inspire_hand_sdk", "inspire_sdkpy")

# Orden de los 29 motores en rt/lowcmd y rt/lowstate (unitree_mujoco/unitree_robots/g1/g1_joint_index_dds.md)
MOTORES = ([f"{l}_{j}_joint" for l in ("left", "right")
            for j in ("hip_pitch", "hip_roll", "hip_yaw", "knee", "ankle_pitch", "ankle_roll")]
           + ["waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint"]
           + [f"{l}_{j}_joint" for l in ("left", "right")
              for j in ("shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow",
                        "wrist_roll", "wrist_pitch", "wrist_yaw")])
ARM_SDK = range(12, 29)   # cintura y brazos: lo que mezcla arm_sdk
PESO = 29                 # motor_cmd[29].q
POSTURA_LOCO = np.array([-0.1, 0, 0, 0.3, -0.2, 0] * 2 + [0, 0, 0]
                        + [0.2, 0.2, 0.0, 0.9, 0.0, 0.0, 0.0] + [0.2, -0.2, 0.0, 0.9, 0.0, 0.0, 0.0])
KP_LOCO = np.array([200.0] * 12 + [200.0] * 3 + [60.0] * 14)
KD_LOCO = np.array([5.0] * 12 + [5.0] * 3 + [1.5] * 14)
LIMITE_PAR = np.array([88, 88, 88, 139, 50, 50] * 2 + [88, 50, 50] + [25, 25, 25, 25, 25, 5, 5] * 2, float)
VEL_DEDOS = 1500.0        # unidades de angle_set por segundo
# Dedos en el orden de los registros de la RH56E2: menique, anular, medio, indice, flexion y rotacion del pulgar
DEDOS = ["pinky_proximal", "ring_proximal", "middle_proximal", "index_proximal",
         "thumb_proximal_pitch", "thumb_proximal_yaw"]


def modelo_mujoco():
    """El URDF con las mallas en una sola carpeta (sus nombres no se repiten) y la etiqueta <mujoco> de MuJoCo."""
    tmp = tempfile.mkdtemp(prefix="g1_mujoco_")
    for sub in ("g1", "hand_left", "hand_right"):
        d = os.path.join(PAQUETE, "meshes", sub)
        for n in os.listdir(d):
            os.symlink(os.path.join(d, n), os.path.join(tmp, n))
    texto = re.sub(r'package://g1_edu_inspire_rh56e2_description/meshes/[^/"]+/', "", open(URDF).read())
    texto = texto.replace("</robot>", '<mujoco><compiler meshdir="." balanceinertia="true" '
                                      'discardvisual="false" fusestatic="false"/></mujoco></robot>', 1)
    ruta = os.path.join(tmp, "g1.urdf")
    open(ruta, "w").write(texto)
    m = mujoco.MjModel.from_xml_path(ruta)
    m.opt.timestep = 0.001
    m.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
    m.dof_armature[:] = 0.01
    m.dof_damping[:] = 0.05
    # mimic de los dedos: junta -> (junta madre, multiplicador)
    mimic = {}
    for j in ET.parse(URDF).getroot().findall("joint"):
        mi = j.find("mimic")
        if mi is not None:
            mimic[j.get("name")] = (mi.get("joint"), float(mi.get("multiplier", 1)), float(mi.get("offset", 0)))
    dedos = [m.joint(i).name for i in range(m.njnt)
             if any(k in m.joint(i).name for k in ("thumb", "index", "middle", "ring", "pinky"))]
    for n in dedos:
        m.dof_armature[m.joint(n).dofadr[0]] = 0.001
    return m, mimic, dedos


class ArmSdk:
    def __init__(self):
        self.cerrojo = threading.Lock()
        self.msg, self.t = None, None

    def recibir(self, msg):
        with self.cerrojo:
            self.msg, self.t = msg, time.monotonic()

    def ultimo(self):
        with self.cerrojo:
            return self.msg, self.t


class Manos:
    def __init__(self, cerradas):
        self.cerrojo = threading.Lock()
        inicio = 0.0 if cerradas else 1000.0
        self.act = {l: np.full(6, inicio) for l in "lr"}
        self.objetivo = {l: np.full(6, inicio) for l in "lr"}

    def recibir(self, lado, msg):
        with self.cerrojo:
            self.objetivo[lado] = np.clip(np.array(list(msg.angle_set)[:6], float), 0, 1000)

    def avanzar(self, dt):
        with self.cerrojo:
            for l in "lr":
                self.act[l] += np.clip(self.objetivo[l] - self.act[l], -VEL_DEDOS * dt, VEL_DEDOS * dt)
            return {l: self.act[l].copy() for l in "lr"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--visor", action="store_true", help="abrir el visor de MuJoCo")
    ap.add_argument("--log", help="CSV a 100 Hz: t, peso, q y q_des de los 14 brazos, angulos de las manos")
    ap.add_argument("--manos-cerradas", action="store_true", help="las manos falsas empiezan cerradas")
    ap.add_argument("--segundos", type=float, default=0, help="terminar solo tras N s (0 = hasta Ctrl-C)")
    a = ap.parse_args()

    from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
    from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowState_
    sys.path.insert(0, SDK_MANOS)   # solo los tipos DDS de las manos, sin el resto de inspire_sdkpy
    import inspire_dds

    m, mimic, dedos = modelo_mujoco()
    d = mujoco.MjData(m)
    qadr = np.array([m.joint(n).qposadr[0] for n in MOTORES])
    vadr = np.array([m.joint(n).dofadr[0] for n in MOTORES])
    dedo_q = [m.joint(n).qposadr[0] for n in dedos]
    dedo_v = [m.joint(n).dofadr[0] for n in dedos]
    sup = {n: m.jnt_range[m.joint(n).id][1] for n in dedos}
    d.qpos[qadr] = POSTURA_LOCO
    mujoco.mj_forward(m, d)

    ChannelFactoryInitialize(1, "lo")
    arm_sdk, manos = ArmSdk(), Manos(a.manos_cerradas)
    sub = ChannelSubscriber("rt/arm_sdk", LowCmd_); sub.Init(arm_sdk.recibir, 10)
    subs_manos = []
    for l in "lr":
        s = ChannelSubscriber(f"rt/inspire_hand/ctrl/{l}", inspire_dds.inspire_hand_ctrl)
        s.Init(lambda msg, l=l: manos.recibir(l, msg), 10)
        subs_manos.append(s)
    pub = ChannelPublisher("rt/lowstate", LowState_); pub.Init()
    pubs_manos = {l: ChannelPublisher(f"rt/inspire_hand/state/{l}", inspire_dds.inspire_hand_state) for l in "lr"}
    for p in pubs_manos.values():
        p.Init()
    estado = unitree_hg_msg_dds__LowState_()
    estado.mode_machine = 15
    estado.imu_state.quaternion = [1.0, 0.0, 0.0, 0.0]

    log = open(a.log, "w") if a.log else None
    if log:
        log.write("t,peso," + ",".join(f"q{i}" for i in range(14)) + "," + ",".join(f"qd{i}" for i in range(14))
                  + "," + ",".join(f"mano_{l}{i}" for l in "lr" for i in range(6)) + ",edad_arm_sdk\n")
    visor = None
    if a.visor:
        from mujoco import viewer as visor_mujoco
        visor = visor_mujoco.launch_passive(m, d)
    print(f"sim G1 UTEC: {m.nq} juntas, {m.body_subtreemass[0]:.2f} kg. rt/arm_sdk -> cintura y brazos; "
          f"rt/lowstate a 500 Hz; manos {'cerradas' if a.manos_cerradas else 'abiertas'}", flush=True)

    # Lanzado en segundo plano desde bash, SIGINT llega ignorado: se termina con SIGTERM (o Ctrl-C en primer plano)
    def terminar(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminar)
    signal.signal(signal.SIGINT, terminar)
    paso, t0, aviso_sin = 0, time.monotonic(), False
    try:
        while not a.segundos or d.time < a.segundos:
            q, dq = d.qpos[qadr], d.qvel[vadr]
            q_des, kp, kd, tau = POSTURA_LOCO.copy(), KP_LOCO.copy(), KD_LOCO.copy(), np.zeros(29)
            msg, t_msg = arm_sdk.ultimo()
            peso, edad = 0.0, -1.0
            if msg is not None:
                peso = float(np.clip(msg.motor_cmd[PESO].q, 0.0, 1.0))
                edad = time.monotonic() - t_msg
                for i in ARM_SDK:
                    c = msg.motor_cmd[i]
                    q_des[i] = peso * c.q + (1 - peso) * q_des[i]
                    kp[i] = peso * c.kp + (1 - peso) * kp[i]
                    kd[i] = peso * c.kd + (1 - peso) * kd[i]
                    tau[i] = peso * c.tau
                if edad > 0.5 and peso > 0 and not aviso_sin:
                    print(f"AVISO: sin rt/arm_sdk desde hace {edad:.1f} s con el peso en {peso:.2f}", flush=True)
                    aviso_sin = True
                elif edad < 0.1:
                    aviso_sin = False
            d.qfrc_applied[:] = 0
            d.qfrc_applied[vadr] = np.clip(kp * (q_des - q) - kd * dq + tau, -LIMITE_PAR, LIMITE_PAR)
            # dedos: PD a la postura que da el angulo de cada dedo (0 = abierto en el URDF)
            ang = manos.avanzar(m.opt.timestep)
            for n, iq, iv in zip(dedos, dedo_q, dedo_v):
                lado = "l" if n.startswith("left_") else "r"
                base, mult, off = mimic.get(n, (n, 1.0, 0.0))
                clave = base[len("left_") if lado == "l" else len("right_"):-len("_joint")]
                obj = (1 - ang[lado][DEDOS.index(clave)] / 1000.0) * sup[base] * mult + off
                d.qfrc_applied[iv] = 2.0 * (obj - d.qpos[iq]) - 0.05 * d.qvel[iv]
            mujoco.mj_step(m, d)
            paso += 1
            if paso % 2 == 0:
                for i in range(29):
                    estado.motor_state[i].q = float(d.qpos[qadr[i]])
                    estado.motor_state[i].dq = float(d.qvel[vadr[i]])
                    estado.motor_state[i].tau_est = float(d.qfrc_applied[vadr[i]])
                estado.tick = paso
                pub.Write(estado)
            if paso % 10 == 0:
                for l in "lr":
                    s = inspire_dds.inspire_hand_state(
                        pos_act=[0] * 6, angle_act=[int(x) for x in ang[l]], force_act=[0] * 6,
                        current=[0] * 6, err=[0] * 6, status=[0] * 6, temperature=[30] * 6)
                    pubs_manos[l].Write(s)
                if log:
                    log.write(f"{d.time:.3f},{peso:.4f}," + ",".join(f"{x:.5f}" for x in q[15:29]) + ","
                              + ",".join(f"{x:.5f}" for x in q_des[15:29]) + ","
                              + ",".join(f"{x:.0f}" for l in "lr" for x in ang[l]) + f",{edad:.3f}\n")
            if visor is not None and paso % 20 == 0:
                if not visor.is_running():
                    break
                visor.sync()
            espera = t0 + d.time - time.monotonic()
            if espera > 0:
                time.sleep(espera)
    except KeyboardInterrupt:
        pass
    finally:
        if log:
            log.close()
        retraso = time.monotonic() - t0 - d.time
        print(f"sim: {d.time:.1f} s simulados, {retraso:+.2f} s de retraso sobre el tiempo real", flush=True)


if __name__ == "__main__":
    main()
