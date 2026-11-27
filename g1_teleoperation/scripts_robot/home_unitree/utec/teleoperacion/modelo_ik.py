#!/usr/bin/env python3
"""Modelo del G1 de UTEC para la cinematica inversa (IK) de xr_teleoperate.

G1_29_ArmIK de Unitree (teleop/robot_control/robot_arm_ik.py, commit 817fb00) carga su modelo de
teleop/g1_29_model_cache.pkl si ese fichero existe, y si no, de assets/g1/g1_body29_hand14.urdf: un G1 con
munecas 4010 (wrist_yaw a 0.046 m) y manos Dex3. Los de UTEC son el modo 15 (munecas 5010, wrist_yaw a 0.051 m)
con las manos de cada robot (MANOS en robot.conf) y las masas de la balanza, copias de
ros2_g1_ws/src/g1_edu_inspire_rh56e2_description/urdf/ del repositorio g1_utec:
  - rh56e2: modelo/g1_29dof_with_RH56E2_hands.urdf, las RH56E2 con sus acoples (0.97 kg por muneca y mano);
  - goma:   modelo/g1_29dof_with_fake_hands.urdf, las manos falsas de Unitree (0.32 kg por muneca y mano).

lanzar_teleop.py llama a escribir_cache() en cada arranque, antes del teleop: escribe ese .pkl con el modelo de
ese robot, construido como lo construye Unitree, y G1_29_ArmIK lo usa sin tocar su codigo:
  - todas las juntas menos las 14 de los brazos, bloqueadas en q = 0 (piernas, cintura y manos abiertas);
  - L_ee / R_ee a 0.05 m del eje de wrist_yaw_joint, igual que Unitree.

Comparado con el de Unitree (python3 modelo_ik.py lo calcula), con las RH56E2: L_ee y R_ee quedan 5 mm mas lejos,
y el par de gravedad que el teleop suma a los brazos (sol_tauff) es ~40 % mayor en el hombro y el codo, por la masa
de las munecas 5010, las manos y los acoples. Con un modelo de otras manos, ese par no corresponde a lo que pesan: con
el de las RH56E2 en el G1 de goma, los brazos quedarian desviados hacia arriba.

    env_tv/bin/python modelo_ik.py      comprueba los dos modelos y, si encuentra el URDF de Unitree, los compara
"""
import os
import pickle
import sys

import numpy as np
import pinocchio as pin

AQUI = os.path.dirname(os.path.abspath(__file__))
URDFS = {"rh56e2": os.path.join(AQUI, "modelo", "g1_29dof_with_RH56E2_hands.urdf"),   # por MANOS de robot.conf
         "goma": os.path.join(AQUI, "modelo", "g1_29dof_with_fake_hands.urdf")}
URDF = URDFS["rh56e2"]
URDF_UNITREE = os.path.join(AQUI, "xr_teleoperate", "assets", "g1", "g1_body29_hand14.urdf")
CACHE = "g1_29_model_cache.pkl"   # el nombre fijo que busca G1_29_ArmIK, relativo a xr_teleoperate/teleop
OFFSET_EE = 0.05                  # m sobre el eje x de wrist_yaw_joint, como Unitree

# Mismo orden que G1_29_JointArmIndex (robot_arm.py): brazo izquierdo y luego derecho
BRAZOS = [f"{lado}_{j}_joint" for lado in ("left", "right")
          for j in ("shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow",
                    "wrist_roll", "wrist_pitch", "wrist_yaw")]


def construir(urdf=URDF):
    """(modelo completo, modelo reducido a los 14 brazos con L_ee y R_ee). Sin mallas: solo cinematica e inercias."""
    modelo = pin.buildModelFromUrdf(urdf)
    faltan = [n for n in BRAZOS if not modelo.existJointName(n)]
    if faltan:
        raise ValueError(f"{urdf}: faltan las juntas {faltan}")
    bloquear = [modelo.getJointId(n) for n in modelo.names[1:] if n not in BRAZOS]
    reducido = pin.buildReducedModel(modelo, bloquear, pin.neutral(modelo))
    if list(reducido.names[1:]) != BRAZOS:
        raise ValueError(f"orden de juntas inesperado en el modelo reducido: {list(reducido.names[1:])}")
    for marco, lado in (("L_ee", "left"), ("R_ee", "right")):
        reducido.addFrame(pin.Frame(marco, reducido.getJointId(f"{lado}_wrist_yaw_joint"),
                                    pin.SE3(np.eye(3), np.array([OFFSET_EE, 0.0, 0.0])),
                                    pin.FrameType.OP_FRAME))
    return modelo, reducido


def escribir_cache(carpeta_teleop, urdf=URDF):
    """Escribe <carpeta_teleop>/g1_29_model_cache.pkl con el formato de G1_29_ArmIK.save_cache(). Devuelve un resumen."""
    modelo, reducido = construir(urdf)
    destino = os.path.join(carpeta_teleop, CACHE)
    tmp = destino + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump({"robot_model": modelo, "reduced_model": reducido}, f)
    os.replace(tmp, destino)
    return f"{os.path.basename(urdf)}: {modelo.nq} juntas, {sum(i.mass for i in modelo.inertias):.3f} kg -> {destino}"


def _par_gravedad(reducido, q):
    return pin.rnea(reducido, reducido.createData(), q, np.zeros(reducido.nv), np.zeros(reducido.nv))


def _posiciones_ee(reducido, q):
    d = reducido.createData()
    pin.framesForwardKinematics(reducido, d, q)
    return [d.oMf[reducido.getFrameId(m)].translation.copy() for m in ("L_ee", "R_ee")]


def main():
    q0 = np.zeros(14)
    red_u = None
    if os.path.exists(URDF_UNITREE):
        _, red_u = construir(URDF_UNITREE)
        print(f"Unitree: {URDF_UNITREE}")
        print(f"  par de gravedad en q = 0, brazo izq (N m): {np.round(_par_gravedad(red_u, q0)[:7], 2)}")
    else:
        print(f"(sin {URDF_UNITREE}: no se compara con el modelo de Unitree)")
    for manos, urdf in URDFS.items():
        modelo, reducido = construir(urdf)
        print(f"UTEC, MANOS={manos}: {urdf}")
        print(f"  {modelo.nq} juntas, {sum(i.mass for i in modelo.inertias):.3f} kg; reducido a {reducido.nq}: "
              f"{'orden de brazos OK' if list(reducido.names[1:]) == BRAZOS else 'ORDEN MAL'}")
        L, R = _posiciones_ee(reducido, q0)
        print(f"  q = 0: L_ee {np.round(L, 4)}  R_ee {np.round(R, 4)}")
        print(f"  par de gravedad en q = 0, brazo izq (N m): {np.round(_par_gravedad(reducido, q0)[:7], 2)}")
        if red_u is None:
            continue
        rng = np.random.default_rng(0)
        dif = []
        for k in range(200):
            q = q0 if k == 0 else rng.uniform(reducido.lowerPositionLimit, reducido.upperPositionLimit)
            dif += [np.linalg.norm(a - b) for a, b in zip(_posiciones_ee(reducido, q), _posiciones_ee(red_u, q))]
        print(f"  L_ee/R_ee frente a Unitree, 200 posturas: max {max(dif) * 1000:.1f} mm, "
              f"media {np.mean(dif) * 1000:.1f} mm")
        print(f"  limites de los brazos iguales a los de Unitree: "
              f"{np.allclose(reducido.lowerPositionLimit, red_u.lowerPositionLimit) and np.allclose(reducido.upperPositionLimit, red_u.upperPositionLimit)}")


if __name__ == "__main__":
    sys.exit(main())
