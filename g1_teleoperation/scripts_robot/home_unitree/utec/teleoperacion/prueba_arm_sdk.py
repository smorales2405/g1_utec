#!/usr/bin/env python3
"""Primera prueba de rt/arm_sdk en el G1, sin gafas ni IK: los brazos NO deberian moverse.

Con los parches de lanzar_teleop.py (los mismos que usa el teleop):
  1. comprueba el modo (CheckMode; en Debug no sigue) y crea el G1_29_ArmController de Unitree en motion_mode;
  2. el peso de arm_sdk sube de 0 a 1 en 2 s, con la consigna en la postura medida y su par de gravedad;
  3. se mantiene SEGUNDOS s (5 por defecto);
  4. la salida de lanzar_teleop sin haber pulsado r: abrir las manos (si las hay) y bajar el peso a 0 en 2 s.
Registra a 50 Hz cintura y brazos (logs/prueba_arm_sdk_<hora>.csv) y dice cuanto se movieron en cada fase.
Si alguna junta se aparta mas de LIMITE_RAD de su postura inicial, baja el peso enseguida. Ctrl-C tambien lo baja.

    ./comun.sh no hace falta:  PYTHONNOUSERSITE=1 env_tv/bin/python prueba_arm_sdk.py [SEGUNDOS] [IFACE]
ANTES: G1 de pie en la locomocion (no Debug), colgado del arnes, alguien con el mando, nadie cerca de los brazos.
"""
import os, sys, threading, time
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import lanzar_teleop as lt   # cambia el directorio a xr_teleoperate/teleop
from unitree_sdk2py.core.channel import ChannelFactoryInitialize

LIMITE_RAD = 0.25
JUNTAS = list(range(12, 29))   # cintura (12-14) y brazos (15-28)
NOMBRES = ["cint_yaw", "cint_roll", "cint_pitch"] + [f"{l}{j}" for l in ("I", "D")
          for j in ("_homb_p", "_homb_r", "_homb_y", "_codo", "_mun_r", "_mun_p", "_mun_y")]


def main():
    segundos = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    iface = sys.argv[2] if len(sys.argv) > 2 else lt.CONF.get("IFACE", "eth1")   # la de robot.conf
    ChannelFactoryInitialize(int(os.environ.get("DDS_DOMINIO", "0")), iface)   # 1 = simulador
    lt.aplicar_parches()
    brazos = lt.Brazos(motion_mode=True, simulation_mode=False)
    q0 = np.array([brazos.lowstate_buffer.GetData().motor_state[j].q for j in JUNTAS])
    t0 = time.monotonic()
    filas, fase, abortado = [], ["subida"], [None]

    def registrar():
        while fase[0] != "fin":
            q = np.array([brazos.lowstate_buffer.GetData().motor_state[j].q for j in JUNTAS])
            filas.append((time.monotonic() - t0, fase[0], brazos._peso.valor(), q))
            d = np.abs(q - q0)
            if abortado[0] is None and d.max() > LIMITE_RAD and fase[0] in ("subida", "quieto"):
                abortado[0] = f"{NOMBRES[int(d.argmax())]} se aparto {d.max():.3f} rad"
                lt.aviso(f"ABORTO: {abortado[0]} -> el peso baja ya")
                brazos._peso.ir(0.0, 0.5)
            time.sleep(0.02)

    hilo = threading.Thread(target=registrar, daemon=True)
    hilo.start()
    try:
        # el hilo que publica arranca la rampa por su cuenta: se espera a ver el peso arriba (como mucho 5 s)
        while brazos._peso.valor() < 0.999 and abortado[0] is None and time.monotonic() - t0 < 5.0:
            time.sleep(0.02)
        fase[0] = "quieto"
        lt.aviso(f"peso en {brazos._peso.valor():.2f}: brazos quietos {segundos:.0f} s")
        t_q = time.monotonic()
        while time.monotonic() - t_q < segundos and abortado[0] is None:
            time.sleep(0.05)
    except KeyboardInterrupt:
        lt.aviso("Ctrl-C: bajo el peso")
    fase[0] = "bajada"
    brazos.ctrl_dual_arm_go_home()   # = lt.salida: sin r, abre las manos y baja el peso
    fase[0] = "despues"
    time.sleep(1.0)
    fase[0] = "fin"
    hilo.join()

    ruta = os.path.join(AQUI, "logs", time.strftime("prueba_arm_sdk_%Y%m%d_%H%M%S.csv"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w") as f:
        f.write("t,fase,peso," + ",".join(NOMBRES) + "\n")
        for t, fs, w, q in filas:
            f.write(f"{t:.3f},{fs},{w:.4f}," + ",".join(f"{x:.5f}" for x in q) + "\n")
    print(f"\nregistro: {ruta}")
    print(f"{'fase':8s} {'s':>5s}  mayor desvio respecto a la postura inicial (grados)")
    for nombre in ("subida", "quieto", "bajada", "despues"):
        qs = np.array([q for _, fs, _, q in filas if fs == nombre])
        if len(qs):
            d = np.degrees(np.abs(qs - q0).max(0))
            i = np.argsort(d)[::-1][:3]
            dur = sum(1 for _, fs, _, _ in filas if fs == nombre) * 0.02
            print(f"{nombre:8s} {dur:5.1f}  max {d.max():5.2f}  ({', '.join(f'{NOMBRES[k]} {d[k]:.2f}' for k in i)})")
    print("ABORTADO: " + abortado[0] if abortado[0] else "sin aborto")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
