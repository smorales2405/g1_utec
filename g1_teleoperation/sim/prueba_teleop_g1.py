#!/usr/bin/env python3
"""Prueba de lanzar_teleop.py contra sim_g1_arm_sdk.py: el G1_29_ArmController y el Inspire_Controller_FTP reales
de Unitree (xr_teleoperate 817fb00) con los parches de lanzar_teleop, sin gafas: la IK recibe las munecas de una
postura conocida. La lanza probar.sh, que tambien arranca el simulador.

    prueba_teleop_g1.py <carpeta como ~/utec/teleoperacion> [--sin-r] [--falla-brazos]
        --sin-r         sale sin haber empezado a seguir (q sin pulsar r)
        --falla-brazos  los movimientos de la salida fallan: el peso tiene que bajar igual
    prueba_teleop_g1.py analizar <log del simulador> [--sin-r]

Las manos falsas reciben "cerrada" hasta que lanzar_teleop pide abrirlas (como si el operador tuviera los puños
cerrados al pulsar q). Imprime OK/FALLO por cada comprobacion y sale con 1 si alguna falla.
"""
import os, sys, time
import numpy as np

FALLOS = []


def comprobar(nombre, ok, detalle=""):
    print(f"  {'OK   ' if ok else 'FALLO'} {nombre}{': ' + detalle if detalle else ''}", flush=True)
    if not ok:
        FALLOS.append(nombre)


def analizar(ruta, sin_r):
    # El log del simulador: t, peso, 14 q, 14 q_des, 12 angulos de las manos, edad del ultimo arm_sdk
    datos = np.genfromtxt(ruta, delimiter=",", names=True)
    peso, t = datos["peso"], datos["t"]
    q = np.stack([datos[f"q{i}"] for i in range(14)], 1)
    print(f"log del simulador: {len(t)} filas, {t[-1]:.1f} s")
    activo = np.flatnonzero(peso > 1e-3)
    comprobar("el peso llega a 1", peso.max() > 0.999, f"max {peso.max():.3f}")
    comprobar("el peso termina en 0", peso[-1] == 0.0, f"ultimo {peso[-1]:.3f}")
    saltos = np.abs(np.diff(peso)).max()
    comprobar("el peso cambia sin saltos (<= 0.02 cada 10 ms)", saltos <= 0.02, f"{saltos:.4f}")
    if len(activo):
        sube = t[activo[0]:][np.argmax(peso[activo[0]:] > 0.999)] - t[activo[0]]
        cerca = np.flatnonzero(peso > 0.999)
        baja = t[activo[-1]] - t[cerca[-1]]
        comprobar("subida del peso ~2 s", 1.7 < sube < 2.5, f"{sube:.2f} s")
        comprobar("bajada del peso ~2 s", 1.7 < baja < 2.5, f"{baja:.2f} s")
        i0 = activo[0]
        i1 = activo[0] + np.argmax(peso[activo[0]:] > 0.999)
        mov = np.abs(q[i0:i1 + 50] - q[i0]).max()
        comprobar("los brazos no se mueven mientras sube el peso (< 0.1 rad)", mov < 0.1, f"{mov:.3f} rad")
        v = np.abs(np.diff(q, axis=0) / np.diff(t)[:, None])
        comprobar("velocidad maxima de los brazos < 3 rad/s", v.max() < 3.0, f"{v.max():.2f} rad/s")
    if sin_r and len(activo):
        mov = np.abs(q[activo[0]:] - q[activo[0]]).max()
        comprobar("sin r, los brazos no se mueven (< 0.1 rad)", mov < 0.1, f"{mov:.3f} rad")
    return 1 if FALLOS else 0


def main():
    carpeta = os.path.abspath(sys.argv[1])
    sin_r, falla_brazos = "--sin-r" in sys.argv, "--falla-brazos" in sys.argv
    sys.path.insert(0, carpeta)
    import lanzar_teleop as lt                     # cambia el directorio a xr_teleoperate/teleop
    from multiprocessing import Array, Lock, Value
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    import pinocchio as pin
    from teleop.robot_control import robot_arm_ik

    print("== modelo de la IK")
    print("  " + lt.modelo_ik.escribir_cache(lt.TELEOP))
    enviar = lt._enviar_mano
    lt._enviar_mano = lambda self, izq, der: enviar(self, *((izq, der) if lt.ABRIR_MANOS.value else ([0] * 6, [0] * 6)))
    if falla_brazos:
        def mover_falla(self, q, destino):
            raise RuntimeError(f"fallo simulado camino de {destino}")
        lt.mover_brazos = mover_falla
    lt.aplicar_parches()
    ChannelFactoryInitialize(1, "lo")

    ik = robot_arm_ik.G1_29_ArmIK()
    _, propio = lt.modelo_ik.construir()
    comprobar("la IK usa el modelo de UTEC", ik.reduced_robot.model.nq == 14 and np.isclose(
        sum(i.mass for i in ik.reduced_robot.model.inertias), sum(i.mass for i in propio.inertias)),
        f"{sum(i.mass for i in ik.reduced_robot.model.inertias):.3f} kg en el modelo")

    print("== controlador de brazos (motion_mode) y manos")
    t0 = time.monotonic()
    brazos = lt.Brazos(motion_mode=True, simulation_mode=False)
    q_inicio = brazos.get_current_dual_arm_q()
    listo = Value("b", False, lock=True)
    izq, der = Array("d", 75, lock=True), Array("d", 75, lock=True)
    estado_manos, accion_manos = Array("d", 12, lock=False), Array("d", 12, lock=False)
    lt.robot_hand_inspire.Inspire_Controller_FTP(izq, der, Lock(), estado_manos, accion_manos,
                                                 simulation_mode=False, xr_motion_data_ready_in=listo)
    mano = lt.MANOS[0]
    time.sleep(lt.RAMPA_PESO_S + 0.5)
    mov = np.abs(brazos.get_current_dual_arm_q() - q_inicio).max()
    comprobar("tras subir el peso, los brazos siguen en la postura de la locomocion", mov < 0.1, f"{mov:.3f} rad")
    cerradas = max(list(mano.left_hand_state_array[:]) + list(mano.right_hand_state_array[:]))
    comprobar("las manos falsas estan cerradas", cerradas < 0.1, f"max {cerradas:.2f}")

    if not sin_r:
        print("== teleop: la IK lleva las munecas a una postura conocida")
        objetivo = np.array([-0.6, 0.35, 0.1, 0.2, 0.2, -0.3, 0.1, -0.6, -0.35, -0.1, 0.2, -0.2, -0.3, -0.1])
        modelo = ik.reduced_robot.model
        datos = modelo.createData()
        pin.framesForwardKinematics(modelo, datos, objetivo)
        L = datos.oMf[modelo.getFrameId("L_ee")].homogeneous.copy()
        R = datos.oMf[modelo.getFrameId("R_ee")].homogeneous.copy()
        t_r = time.monotonic()
        while time.monotonic() - t_r < 5.0:
            sol_q, sol_tau = ik.solve_ik(L, R, brazos.get_current_dual_arm_q(), brazos.get_current_dual_arm_dq())
            brazos.ctrl_dual_arm(sol_q, sol_tau)
            time.sleep(1 / 30)
        pin.framesForwardKinematics(modelo, datos, brazos.get_current_dual_arm_q())
        err = max(np.linalg.norm(datos.oMf[modelo.getFrameId(f)].translation - M[:3, 3])
                  for f, M in (("L_ee", L), ("R_ee", R)))
        comprobar("las munecas llegan a donde pide la IK (< 2 cm)", err < 0.02, f"{err * 100:.1f} cm")

    print("== salida (lo que hace q)")
    t_q = time.monotonic()
    brazos.ctrl_dual_arm_go_home()
    duracion = time.monotonic() - t_q
    abiertas = min(list(mano.left_hand_state_array[:]) + list(mano.right_hand_state_array[:]))
    comprobar("manos abiertas al terminar", abiertas >= lt.MANO_ABIERTA, f"min {abiertas:.2f}")
    comprobar("peso de arm_sdk en 0", brazos._peso.valor() == 0.0, f"{brazos._peso.valor():.3f}")
    if not falla_brazos:
        err = np.abs(brazos.get_current_dual_arm_q() - q_inicio).max()
        comprobar("brazos en la postura de la locomocion", err < 0.1, f"{err:.3f} rad")
    print(f"  salida en {duracion:.1f} s; prueba en {time.monotonic() - t0:.1f} s")
    time.sleep(0.5)
    return 1 if FALLOS else 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "analizar":
        sys.exit(analizar(sys.argv[2], "--sin-r" in sys.argv))
    sys.exit(main())
