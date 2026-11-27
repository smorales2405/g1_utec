#!/usr/bin/env python3
"""Prueba de la ventana sin pantalla (Qt offscreen) contra dos manos falsas, con un robot falso para la
comprobacion del teleop. Pulsa los botones como lo haria alguien y mira lo que les llega a las manos.

    python3 prueba_ventana.py [--capturas DIR]

Casos: no conecta con el teleop corriendo; conecta; gesto en las dos; gesto en una sola; un gesto nuevo cancela los
pasos que faltan del anterior; "Cerrar" a velocidad baja espera a los dedos antes de cerrar el pulgar; la velocidad
se pone y se restaura; si el teleop arranca, la interfaz suelta las manos; cerrar la ventana restaura la velocidad.
"""
import argparse
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "interfaz"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pymodbus.client import ModbusTcpClient  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication, QPushButton  # noqa: E402

import main as principal  # noqa: E402
from manos import registros as R  # noqa: E402
from manos import robot  # noqa: E402

PUERTOS = {"izq": 17210, "der": 17211}
ROBOT = {"codigo": 1, "salida": ""}      # lo que contesta el robot falso a la comprobacion


def comando_falso(_control, _robot):
    return ["bash", "-c", f"printf '%s' {ROBOT['salida']!r}; exit {ROBOT['codigo']}"]


robot.comando = comando_falso
mal = []


def leer(lado, direccion, n=6):
    c = ModbusTcpClient("127.0.0.1", port=PUERTOS[lado], timeout=2)
    c.connect()
    r = c.read_holding_registers(direccion, n, slave=1)
    c.close()
    return list(r.registers)


def esperar(cond, segundos, paso=50):
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        if cond():
            return True
        QTest.qWait(paso)
    return cond()


def comprobar(nombre, ok, detalle=""):
    print(f"  {'OK ' if ok else 'MAL'} {nombre}{(': ' + detalle) if detalle else ''}", flush=True)
    if not ok:
        mal.append(nombre)


def boton(padre, texto):
    for b in padre.findChildren(QPushButton):
        if b.text() == texto:
            return b
    raise LookupError(texto)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capturas")
    a = ap.parse_args()
    falsas = subprocess.Popen([sys.executable, os.path.join(AQUI, "mano_falsa.py"),
                               str(PUERTOS["izq"]), str(PUERTOS["der"])])
    time.sleep(1.2)
    try:
        correr(a.capturas)
    finally:
        falsas.terminate()
        falsas.wait(3)
    print("RESULTADO:", "OK" if not mal else "MAL: " + "; ".join(mal))
    sys.exit(1 if mal else 0)


def correr(capturas):
    app = QApplication([sys.argv[0]])
    app.setStyleSheet(principal.HOJA)
    args = principal.argumentos(["--izq", f"127.0.0.1:{PUERTOS['izq']}", "--der", f"127.0.0.1:{PUERTOS['der']}",
                                 "--ssh-control", "/no/existe", "--robot", "unitree@robot-falso"])
    w = principal.crear_ventana(args)
    w.resize(1240, 680)
    w.show()
    QTest.qWait(200)

    def captura(nombre):
        if capturas:
            os.makedirs(capturas, exist_ok=True)
            w.grab().save(os.path.join(capturas, nombre + ".png"))

    captura("0_desconectada")
    conectar = w._boton
    izq, der = w.paneles["izq"], w.paneles["der"]

    print("== con el teleop corriendo no conecta")
    ROBOT.update(codigo=0, salida="4242 /home/unitree/utec/teleoperacion/env_tv/bin/python "
                                   "/home/unitree/inspire_ftp_dual_driver.py --network eth1")
    QTest.mouseClick(conectar, 1)
    esperar(lambda: conectar.isEnabled(), 3)
    comprobar("no conecta", not w.enlaces, w._teleop.text())
    comprobar("dice que corre el driver", "inspire_ftp_dual_driver.py" in w._teleop.text())
    captura("1_teleop_corriendo")

    print("== conecta con el teleop parado")
    ROBOT.update(codigo=1, salida="")
    QTest.mouseClick(conectar, 1)
    ok = esperar(lambda: all(e.conectada for e in w.enlaces.values()) and len(w.enlaces) == 2
                 and izq._ultimo and der._ultimo, 5)
    comprobar("conectadas las dos", ok)
    comprobar("botones activos", boton(izq, "Cerrar").isEnabled() and w._botones_ambas[0].isEnabled())
    comprobar("slider con la velocidad leida", w._vel.value() == 1000, str(w._vel.value()))

    print("== Cerrar en las dos")
    QTest.mouseClick(w._botones_ambas[1], 1)
    esperar(lambda: leer("izq", R.ANGLE_ACT) == [0, 0, 0, 0, 0, 1000]
            and leer("der", R.ANGLE_ACT) == [0, 0, 0, 0, 0, 1000], 4)
    for lado in ("izq", "der"):
        v = leer(lado, R.ANGLE_ACT)
        comprobar(f"{lado} cerrada", v == [0, 0, 0, 0, 0, 1000], str(v))
    QTest.qWait(300)
    captura("2_cerrar_ambas")

    print("== un gesto distinto en cada mano")
    QTest.mouseClick(w._botones_ambas[0], 1)          # desde abiertas: Pulgar arriba tiene que mover algo
    esperar(lambda: leer("der", R.ANGLE_ACT) == [1000] * 6, 4)
    QTest.mouseClick(boton(izq, "Señalar"), 1)
    QTest.mouseClick(boton(der, "Pulgar arriba"), 1)
    esperar(lambda: leer("izq", R.ANGLE_ACT) == [0, 0, 0, 1000, 0, 500]
            and leer("der", R.ANGLE_ACT) == [0, 0, 0, 0, 1000, 1000], 4)
    comprobar("izq señala", leer("izq", R.ANGLE_ACT) == [0, 0, 0, 1000, 0, 500], str(leer("izq", R.ANGLE_ACT)))
    comprobar("der pulgar arriba", leer("der", R.ANGLE_ACT) == [0, 0, 0, 0, 1000, 1000],
              str(leer("der", R.ANGLE_ACT)))
    QTest.qWait(300)
    captura("3_senalar_pulgar")

    print("== Abrir justo despues de Cerrar cancela el segundo paso de Cerrar")
    QTest.mouseClick(boton(izq, "Cerrar"), 1)
    QTest.qWait(150)
    QTest.mouseClick(boton(izq, "Abrir"), 1)
    QTest.qWait(2500)
    v = leer("izq", R.ANGLE_SET)
    comprobar("ANGLE_SET sigue en Abrir", v == [1000] * 6, str(v))

    print("== velocidad 200: Cerrar espera a los dedos antes de cerrar el pulgar")
    QTest.mouseClick(boton(der, "Abrir"), 1)          # desde abierta, para que los dedos tarden en cerrar
    esperar(lambda: leer("der", R.ANGLE_ACT) == [1000] * 6, 4)
    w._vel.setValue(200)
    esperar(lambda: leer("izq", R.SPEED_SET) == [200] * 6 and leer("der", R.SPEED_SET) == [200] * 6, 2)
    comprobar("SPEED_SET 200 en las dos", leer("izq", R.SPEED_SET) == [200] * 6 and leer("der", R.SPEED_SET) == [200] * 6)
    QTest.mouseClick(boton(der, "Cerrar"), 1)
    t0 = time.monotonic()
    esperar(lambda: leer("der", R.ANGLE_SET)[4] == 0, 8)
    t_pulgar = time.monotonic() - t0
    dedos = leer("der", R.ANGLE_ACT)[:4]
    # a 200, la mano falsa tarda 3 s en cerrar del todo: el pulgar no puede salir a los 0.8 s
    comprobar("el pulgar sale con los dedos cerrados", max(dedos) <= 60 and t_pulgar > 2.0,
              f"a los {t_pulgar:.1f} s, dedos en {dedos}")
    captura("4_velocidad_200")

    print("== el teleop arranca con la interfaz conectada: suelta las manos y restaura la velocidad")
    ROBOT.update(codigo=0, salida="4243 python lanzar_teleop.py --arm=G1_29 --motion")
    ok = esperar(lambda: not w.enlaces, 6)
    comprobar("soltadas", ok)
    for lado in ("izq", "der"):
        comprobar(f"{lado} velocidad restaurada", leer(lado, R.SPEED_SET) == [1000] * 6, str(leer(lado, R.SPEED_SET)))
    comprobar("aviso del teleop", "lanzar_teleop.py" in w._teleop.text(), w._teleop.text())
    comprobar("botones apagados", not boton(izq, "Abrir").isEnabled() and not w._botones_ambas[0].isEnabled())
    captura("5_teleop_arranca")

    print("== cerrar la ventana con la velocidad cambiada la restaura")
    ROBOT.update(codigo=1, salida="")
    QTest.mouseClick(conectar, 1)
    esperar(lambda: len(w.enlaces) == 2 and all(e.conectada for e in w.enlaces.values()), 5)
    w._vel.setValue(400)
    esperar(lambda: leer("izq", R.SPEED_SET) == [400] * 6, 2)
    comprobar("velocidad 400 puesta", leer("izq", R.SPEED_SET) == [400] * 6)
    w.close()
    esperar(lambda: not w.isVisible(), 6)
    comprobar("ventana cerrada", not w.isVisible())
    for lado in ("izq", "der"):
        comprobar(f"{lado} velocidad restaurada al cerrar", leer(lado, R.SPEED_SET) == [1000] * 6,
                  str(leer(lado, R.SPEED_SET)))


if __name__ == "__main__":
    main()
