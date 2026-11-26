#!/usr/bin/env python3
"""Interfaz de gestos de las dos manos Inspire RH56E2 del G1. Se lanza normalmente con ../interfaz_manos.sh, que abre
el tunel SSH; a mano:

    python3 main.py --izq HOST:PUERTO --der HOST:PUERTO [--ssh-control SOCKET --robot unitree@IP] [--titulo TEXTO]

Sin --ssh-control no se comprueba si el teleop esta usando las manos (para las manos falsas de las pruebas, o con
la laptop en la red interna del robot: --izq 192.168.123.210:6000 --der 192.168.123.211:6000).
"""
import argparse
import os
import signal
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import QTimer  # noqa: E402
from PyQt5.QtGui import QFont  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from manos import registros as R  # noqa: E402
from ui.estilo import HOJA  # noqa: E402
from ui.ventana import Ventana  # noqa: E402


def direccion(texto):
    host, _, puerto = texto.rpartition(":")
    if not host:
        raise argparse.ArgumentTypeError(f"{texto!r}: tiene que ser HOST:PUERTO")
    return host, int(puerto)


def argumentos(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--izq", type=direccion, default=(R.IPS["izq"], R.PUERTO), help="mano IZQUIERDA del robot")
    ap.add_argument("--der", type=direccion, default=(R.IPS["der"], R.PUERTO), help="mano DERECHA del robot")
    ap.add_argument("--ssh-control", help="socket del ControlMaster del tunel, para comprobar el teleop")
    ap.add_argument("--robot", help="usuario@IP del robot (con --ssh-control)")
    ap.add_argument("--titulo", default="", help="texto para la barra del titulo")
    a = ap.parse_args(argv)
    if bool(a.ssh_control) != bool(a.robot):
        ap.error("--ssh-control y --robot van juntos")
    return a


def crear_ventana(a):
    dirs = {"izq": a.izq, "der": a.der}
    if a.ssh_control:
        reales = {l: f"{R.IPS[l]}:{R.PUERTO} · túnel :{dirs[l][1]}" for l in dirs}
    else:
        reales = {l: "%s:%d" % dirs[l] for l in dirs}
    return Ventana(dirs, reales, a.ssh_control, a.robot, a.titulo)


def main():
    a = argumentos()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Arial", 10))
    app.setStyleSheet(HOJA)
    ventana = crear_ventana(a)
    ventana.show()
    # Ctrl-C (o cerrar la terminal) cierra la ventana como el boton: soltando las manos y restaurando la velocidad.
    # Qt no deja a Python atender senales mientras espera; el temporizador le da la vez.
    for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(s, lambda *_: ventana.close())
    latido = QTimer()
    latido.timeout.connect(lambda: None)
    latido.start(200)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
