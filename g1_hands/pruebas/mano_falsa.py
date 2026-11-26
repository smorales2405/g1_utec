#!/usr/bin/env python3
"""Manos RH56E2 FALSAS por Modbus TCP, para probar la interfaz sin el robot.

    python3 mano_falsa.py 16210 16211          una mano en cada puerto de 127.0.0.1

Imitan lo que usa la interfaz: ANGLE_SET (bloque de 6), SPEED_SET, ANGLE_ACT (los dedos van hacia la consigna a una
velocidad proporcional a SPEED_SET), FORCE_ACT, ERROR, STATUS (255 en reposo, como las del G1), TEMP y CLEAR_ERROR.
Cada dedo tiene su propia temperatura (30 + dedo) para ver que los bytes se desempaquetan en orden.

    --error-dedo N    el dedo N arranca con err 5 (bloqueo + sobrecorriente), hasta que se borre con 1004
    --ver             imprime cada escritura que llega
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "interfaz"))

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext  # noqa: E402
from pymodbus.server import ModbusTcpServer  # noqa: E402

from manos import registros as R  # noqa: E402

DT = 0.01
RECORRIDO_S_A_1000 = 0.6   # segundos para recorrer 0..1000 a SPEED_SET 1000


class Bloque(ModbusSequentialDataBlock):
    """Registros 0..2999 que avisan de cada escritura."""

    def __init__(self, mano):
        super().__init__(0, [0] * 3000)
        self.mano = mano

    def setValues(self, address, values):
        values = list(values) if isinstance(values, (list, tuple)) else [values]
        super().setValues(address, values)
        self.mano.escrito(address, values)


class ManoFalsa:
    def __init__(self, nombre, puerto, error_dedo=None, ver=False):
        self.nombre, self.puerto, self.ver = nombre, puerto, ver
        self.bloque = Bloque(self)
        self.angulo = [1000.0] * 6
        self.consigna = [1000] * 6
        self.velocidad = [1000] * 6
        self.status = [255] * 6
        self.error = [0] * 6
        if error_dedo is not None:
            self.error[error_dedo] = 5
        self._poner(R.SPEED_SET, self.velocidad)
        self._poner(R.ANGLE_SET, self.consigna)
        self._publicar()

    def _poner(self, direccion, valores):
        ModbusSequentialDataBlock.setValues(self.bloque, direccion, [int(v) & 0xFFFF for v in valores])

    def escrito(self, direccion, valores):
        if self.ver:
            print(f"[{self.nombre}] escribe {direccion}: {valores}", flush=True)
        if direccion == R.ANGLE_SET and len(valores) == 6:
            for i, v in enumerate(valores):
                if v != 0xFFFF:                 # -1 = deja este dedo como esta
                    self.consigna[i] = max(0, min(1000, v))
                    d = self.consigna[i] - self.angulo[i]
                    self.status[i] = 0 if d > 0 else 1 if d < 0 else self.status[i]
        elif direccion == R.ANGLE_SET:
            print(f"[{self.nombre}] AVISO: ANGLE_SET de {len(valores)} registros (la RH56E2 quiere el bloque de 6)")
        elif direccion == R.SPEED_SET:
            self.velocidad = list(self.bloque.getValues(R.SPEED_SET, 6))
        elif direccion == R.CLEAR_ERROR and valores and valores[0] == 1:
            self.error = [0] * 6

    def paso(self):
        for i in range(6):
            if self.error[i]:
                continue
            max_paso = 1000.0 * DT / RECORRIDO_S_A_1000 * self.velocidad[i] / 1000.0
            d = self.consigna[i] - self.angulo[i]
            if abs(d) <= max_paso:
                if self.status[i] in (0, 1):
                    self.status[i] = 2
                self.angulo[i] = float(self.consigna[i])
            else:
                self.angulo[i] += max_paso if d > 0 else -max_paso
        self._publicar()

    def _publicar(self):
        self._poner(R.ANGLE_ACT, [round(a) for a in self.angulo])
        # un poco de fuerza al cerrar del todo, para que se vea algo en la columna
        self._poner(R.FORCE_ACT, [int(300 * (1 - a / 200)) if a < 200 else 0 for a in self.angulo])
        self._poner(R.ERROR, R.de_bytes(self.error))
        self._poner(R.STATUS, R.de_bytes(self.status))
        self._poner(R.TEMP, R.de_bytes([30 + i for i in range(6)]))

    async def correr(self):
        contexto = ModbusServerContext(slaves=ModbusSlaveContext(hr=self.bloque, zero_mode=True), single=True)
        servidor = ModbusTcpServer(contexto, address=("127.0.0.1", self.puerto))

        async def simular():
            while True:
                self.paso()
                await asyncio.sleep(DT)

        print(f"mano falsa {self.nombre} en 127.0.0.1:{self.puerto}", flush=True)
        await asyncio.gather(servidor.serve_forever(), simular())


async def principal(args):
    nombres = ["izq", "der"] + [f"m{i}" for i in range(2, len(args.puertos))]
    manos = [ManoFalsa(n, p, args.error_dedo if i == 0 else None, args.ver)
             for i, (n, p) in enumerate(zip(nombres, args.puertos))]
    await asyncio.gather(*(m.correr() for m in manos))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("puertos", type=int, nargs="+")
    ap.add_argument("--error-dedo", type=int, choices=range(6), help="dedo con err 5 en la primera mano")
    ap.add_argument("--ver", action="store_true")
    args = ap.parse_args()
    try:
        asyncio.run(principal(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
