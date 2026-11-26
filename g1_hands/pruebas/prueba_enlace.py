#!/usr/bin/env python3
"""Prueba sin ventana del enlace con las dos manos (manos/enlace.py), contra las falsas o las del robot.

    prueba_enlace.py [--izq H:P] [--der H:P] leer                  estado de las dos manos (SOLO LECTURA)
    prueba_enlace.py [--izq H:P] [--der H:P] gestos [NOMBRE ...]    cada gesto en las dos manos (todos si no se dice)
    prueba_enlace.py [--izq H:P] [--der H:P] velocidad V            pone SPEED_SET = V, suelta y comprueba que vuelve
    prueba_enlace.py [--izq H:P] [--der H:P] indice                 mueve SOLO el indice y vuelve: el STATUS que cambia
                                                                    tiene que ser el del indice (orden de los bytes)
    prueba_enlace.py [--izq H:P] [--der H:P] dos-clientes           dos conexiones Modbus a la vez a cada mano (LECTURA)

    --fijar 5      esos DOF (separados por comas) no se mueven: se mandan con la consigna que ya tiene la mano (5 = rotacion del pulgar)
    --solo izq     una sola mano

Por defecto, las manos falsas de mano_falsa.py en 127.0.0.1:16210 y :16211. Contra el robot, con el tunel de
interfaz_manos.sh abierto, son los mismos puertos. Sale con 1 si algo no cuadra.
"""
import argparse
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "interfaz"))

from pymodbus.client import ModbusTcpClient  # noqa: E402

from manos import registros as R  # noqa: E402
from manos.enlace import EnlaceMano  # noqa: E402
from manos.gestos import GESTOS, PAUSA_PASOS_MS, POR_NOMBRE  # noqa: E402

INDICE = 3
TOLERANCIA = 30      # registros: lo que puede quedar un dedo de su consigna (en la real, por la fuerza o un tope)
ESPERA_GESTO = 4.0   # s como mucho hasta que los dedos dejan de moverse


class Manos:
    def __init__(self, direcciones):
        self.estado, self.eventos = {}, []
        self._cambio = threading.Condition()
        self.enlaces = {lado: EnlaceMano(lado, h, p, self._al_estado, self._al_evento)
                        for lado, (h, p) in direcciones.items()}

    def _al_estado(self, lado, estado):
        with self._cambio:
            self.estado[lado] = estado
            self._cambio.notify_all()

    def _al_evento(self, lado, tipo, texto):
        self.eventos.append((lado, tipo, texto))
        if tipo != "conectando":
            print(f"    [{lado}] {tipo} {texto}", flush=True)

    def conectar(self, espera=10.0, fijos=()):
        for e in self.enlaces.values():
            e.fijos = set(fijos)
            e.iniciar()
        fin = time.monotonic() + espera
        while time.monotonic() < fin:
            if all(lado in self.estado for lado in self.enlaces):
                return True
            time.sleep(0.05)
        return False

    def esperar_quietas(self, espera=ESPERA_GESTO):
        """Hasta que ningun dedo cambie en 0.3 s."""
        anterior, desde, fin = None, time.monotonic(), time.monotonic() + espera
        while time.monotonic() < fin:
            ahora = {l: tuple(s["angulo"]) for l, s in self.estado.items()}
            if ahora != anterior:
                anterior, desde = ahora, time.monotonic()
            elif time.monotonic() - desde > 0.3:
                return True
            time.sleep(0.05)
        return False

    def soltar(self):
        for e in self.enlaces.values():
            e.soltar()


def imprimir(lado, s):
    print(f"  mano {lado} ({R.NOMBRE_LADO[lado]}), ciclo {s['ms']:.0f} ms, velocidad {s['velocidad']}")
    for i, n in enumerate(R.DEDOS):
        print(f"    {n:15s} angulo {s['angulo'][i]:5d}  fuerza {s['fuerza'][i]:5d} gf  err {s['error'][i]:3d}  "
              f"status {s['status'][i]:3d}  {s['temp'][i]:3d} C")


def dos_clientes(direcciones):
    """Dos clientes Modbus a la vez contra cada mano, leyendo ANGLE_ACT por turnos. Solo lectura."""
    fallos = 0
    for lado, (h, p) in direcciones.items():
        a, b = ModbusTcpClient(h, port=p, timeout=2), ModbusTcpClient(h, port=p, timeout=2)
        print(f"  {lado}: conecta A {a.connect()}, conecta B {b.connect()}", flush=True)
        ok = {"A": 0, "B": 0}
        for _ in range(10):
            for nombre, c in (("A", a), ("B", b)):
                try:
                    r = c.read_holding_registers(R.ANGLE_ACT, 6, slave=R.ID_MANO)
                    ok[nombre] += 0 if r.isError() else 1
                except Exception as e:
                    print(f"    {nombre}: {type(e).__name__}: {e}")
            time.sleep(0.05)
        a.close(); b.close()
        print(f"  {lado}: lecturas buenas A {ok['A']}/10, B {ok['B']}/10", flush=True)
        fallos += ok["A"] < 10 or ok["B"] < 10
    print("RESULTADO:", "las manos aceptan dos clientes a la vez" if not fallos else "ALGUNA NO acepta dos clientes")
    return 0


def lista_dof(texto):
    dofs = [int(x) for x in texto.split(",") if x.strip()]
    if any(not 0 <= d <= 5 for d in dofs):
        raise argparse.ArgumentTypeError("los DOF van de 0 a 5")
    return dofs


def direccion(texto):
    h, _, p = texto.rpartition(":")
    return h, int(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--izq", type=direccion, default=("127.0.0.1", 16210))
    ap.add_argument("--der", type=direccion, default=("127.0.0.1", 16211))
    ap.add_argument("--solo", choices=["izq", "der"], help="una sola mano")
    ap.add_argument("--fijar", type=lista_dof, default=[], metavar="DOF[,DOF]")
    ap.add_argument("orden", choices=["leer", "gestos", "velocidad", "indice", "dos-clientes"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()

    direcciones = {"izq": a.izq, "der": a.der}
    if a.solo:
        direcciones = {a.solo: direcciones[a.solo]}
    if a.orden == "dos-clientes":
        sys.exit(dos_clientes(direcciones))
    manos = Manos(direcciones)
    print(f"conectando con {direcciones}" + (f", sin mover los DOF {a.fijar}" if a.fijar else ""), flush=True)
    if not manos.conectar(fijos=a.fijar):
        print("NO contestan todas las manos"); manos.soltar(); sys.exit(1)
    mal = []
    try:
        if a.orden == "leer":
            time.sleep(0.5)
            for lado, s in sorted(manos.estado.items()):
                imprimir(lado, s)

        elif a.orden == "gestos":
            nombres = a.args or [n for n, _ in GESTOS]
            for nombre in nombres:
                pasos = POR_NOMBRE[nombre]
                print(f"== {nombre}: {pasos}", flush=True)
                t0 = time.monotonic()
                enviado = {}
                for k, paso in enumerate(pasos):
                    if k:
                        time.sleep(PAUSA_PASOS_MS / 1000.0)
                        manos.esperar_quietas()          # como la interfaz: el paso siguiente, con los dedos parados
                    for lado, e in manos.enlaces.items():
                        enviado[lado] = e.mandar_angulos(paso)
                time.sleep(0.3)
                manos.esperar_quietas()
                for lado, s in sorted(manos.estado.items()):
                    if enviado[lado] is None:
                        print(f"  {lado}: NO SE MANDO"); mal.append(f"{nombre} {lado} sin mandar"); continue
                    dif = [abs(x - y) for x, y in zip(s["angulo"], enviado[lado])]
                    ok = max(dif) <= TOLERANCIA
                    print(f"  {lado}: {time.monotonic() - t0:.1f} s  ANGLE_SET {enviado[lado]}  angulo {s['angulo']}  "
                          f"status {s['status']}  fuerza {s['fuerza']}  "
                          f"{'OK' if ok else 'LEJOS DE LA CONSIGNA ' + str(dif)}", flush=True)
                    if not ok:
                        mal.append(f"{nombre} {lado}")

        elif a.orden == "indice":
            for lado, e in manos.enlaces.items():
                s0 = manos.estado[lado]
                base = [max(0, min(1000, v)) for v in s0["angulo"]]   # donde estan: solo se mueve el indice
                ida = list(base)
                ida[INDICE] = 300 if s0["angulo"][INDICE] > 500 else 700
                print(f"== {lado}: solo el indice, ANGLE_SET {base} -> {ida} -> {base}", flush=True)
                cambios = []
                for objetivo in (ida, base):
                    print(f"    manda {e.mandar_angulos(objetivo)}", flush=True)   # con los DOF de --fijar
                    fin = time.monotonic() + 2.0
                    previo = None
                    while time.monotonic() < fin:
                        st = manos.estado[lado]["status"]
                        if st != previo:
                            print(f"    status {st}  angulo {manos.estado[lado]['angulo']}", flush=True)
                            # Al recibir ANGLE_SET la mano real pone los 6 en 0/1 un instante: lo que cuenta es
                            # el dedo que sigue abriendo/cerrando cuando los demas ya estan en posicion (2)
                            if 2 in st:
                                cambios += [i for i in range(6) if st[i] in (0, 1)]
                            previo = st
                        time.sleep(0.02)
                dedos = sorted(set(cambios))
                print(f"  {lado}: STATUS abriendo/cerrando en {[R.DEDOS[i] for i in dedos]}")
                if dedos and dedos != [INDICE]:
                    mal.append(f"{lado}: el STATUS que cambia no es el del indice (BYTE_BAJO_PRIMERO?)")
                if not dedos:
                    print("    (el STATUS no cambio: no dice nada del orden de los bytes)")

        elif a.orden == "velocidad":
            v = int(a.args[0])
            antes = {l: e.velocidad_original for l, e in manos.enlaces.items()}
            print(f"  velocidad leida al conectar: {antes}; se pone {v}")
            for e in manos.enlaces.values():
                e.mandar_velocidad(v)
            time.sleep(1.5)            # la velocidad se relee una vuelta de cada 5
            for lado, s in sorted(manos.estado.items()):
                print(f"  {lado}: SPEED_SET ahora {s['velocidad']}")
                if s["velocidad"] != [v] * 6:
                    mal.append(f"no se puso la velocidad en {lado}")
    finally:
        manos.soltar()

    if a.orden == "velocidad":
        for lado, (h, p) in direcciones.items():
            c = ModbusTcpClient(h, port=p, timeout=2)
            c.connect()
            r = c.read_holding_registers(R.SPEED_SET, 6, slave=R.ID_MANO)
            c.close()
            vuelta = list(r.registers) if not r.isError() else None
            esperada = manos.enlaces[lado].velocidad_original
            print(f"  {lado}: tras soltar, SPEED_SET {vuelta} (antes {esperada})")
            if vuelta != esperada:
                mal.append(f"no se restauro la velocidad en {lado}")
    print("RESULTADO:", "OK" if not mal else "MAL: " + "; ".join(mal))
    sys.exit(1 if mal else 0)


if __name__ == "__main__":
    main()
