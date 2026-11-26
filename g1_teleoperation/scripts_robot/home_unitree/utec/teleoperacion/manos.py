#!/usr/bin/env python3
"""Ordenes sueltas a las manos Inspire RH56E2 del G1 por Modbus TCP (puerto 6000), para diagnostico.

    manos.py leer         [izq|der|ambas]   angulos, fuerzas, err, status y temperatura (SOLO LECTURA)
    manos.py abrir        [izq|der|ambas]   todos los dedos a 1000 (abiertos)
    manos.py dedo         izq|der           el indice va 1.5 s a media apertura y vuelve a donde estaba:
                                            sirve para ver que IP es cada mano
    manos.py borrar-error [izq|der|ambas]   escribe 1 en el registro 1004 (p. ej. tras un err 5)

Las ordenes que escriben no se mandan con el driver de las manos (inspire_ftp_dual_driver.py) corriendo: los
dos escribirian a la vez. Para pararlo: ./parar.sh. No se toca la velocidad (SPEED_SET) para que el teleop la
encuentre como siempre. Los registros se leen por grupos de 6 (en el H1-2, leer 1546..1620 de una vez daba basura).
ANGLE_SET se escribe SIEMPRE como bloque de 6 desde 1486, como el driver: en la RH56E2 las direcciones de la tabla son
de byte (cada dedo ocupa 2), y escribir un solo registro en 1486 + 3 (2026-11-26) movio el ANULAR, no el indice.
"""
import subprocess, sys, time

# Las mismas que inspire_ftp_dual_driver.py (LEFT_IP/RIGHT_IP). Comprobado el 2026-11-26 con "dedo" (al reves que en
# el H1-2): al mover un dedo de la .211 se movio la mano DERECHA del robot
IPS = {"izq": "192.168.123.210", "der": "192.168.123.211"}
DOF = ["menique", "anular", "medio", "indice", "pulgar", "rot_pulgar"]
ANGLE_SET, ANGLE_ACT, FORCE_ACT, ERROR, STATUS, TEMP, BORRAR_ERROR = 1486, 1546, 1582, 1606, 1612, 1618, 1004
INDICE = 3


def conectar(ip):
    from pymodbus.client import ModbusTcpClient
    c = ModbusTcpClient(ip, port=6000, timeout=3)
    if not c.connect():
        sys.exit(f"no conecta con la mano {ip}:6000")
    return c


def regs(c, direccion, n):
    r = c.read_holding_registers(direccion, n, slave=1)
    if r.isError():
        raise RuntimeError(f"lectura de {direccion} fallo: {r}")
    return [v - 65536 if v > 32767 else v for v in r.registers]


def bytes6(c, direccion):
    # 6 valores de un byte en 3 registros, el bajo primero
    return [b for v in regs(c, direccion, 3) for b in (v & 0xFF, (v >> 8) & 0xFF)]


def leer(c):
    ang, fza = regs(c, ANGLE_ACT, 6), regs(c, FORCE_ACT, 6)
    err, sta, tmp = bytes6(c, ERROR), bytes6(c, STATUS), bytes6(c, TEMP)
    for i, n in enumerate(DOF):
        print(f"    {n:10s} angulo {ang[i]:5d}  fuerza {fza[i]:5d} gf  err {err[i]:3d}  status {sta[i]:3d}  {tmp[i]:3d} C")


def escribir(c, direccion, valores):
    r = c.write_registers(direccion, valores, slave=1)
    if r.isError():
        raise RuntimeError(f"escritura en {direccion} fallo: {r}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("leer", "abrir", "dedo", "borrar-error"):
        print(__doc__); sys.exit(1)
    orden = sys.argv[1]
    cual = sys.argv[2] if len(sys.argv) > 2 else ("" if orden == "dedo" else "ambas")
    lados = ["izq", "der"] if cual == "ambas" and orden != "dedo" else [cual]
    if any(l not in IPS for l in lados):
        sys.exit(f"mano desconocida: {cual!r} (izq, der{'' if orden == 'dedo' else ' o ambas'})")
    if orden != "leer" and subprocess.run(["pgrep", "-f", "inspire_ftp_dual_driver[.]py"],
                                          stdout=subprocess.DEVNULL).returncode == 0:
        sys.exit("el driver de las manos esta corriendo: paralo antes (./parar.sh)")
    for lado in lados:
        print(f"[{lado}] {IPS[lado]}: {orden}", flush=True)
        c = conectar(IPS[lado])
        try:
            if orden == "abrir":
                escribir(c, ANGLE_SET, [1000] * 6)
                time.sleep(1.5)
            elif orden == "borrar-error":
                escribir(c, BORRAR_ERROR, [1])
                time.sleep(0.5)
            elif orden == "dedo":
                print(f"    se mueve el INDICE de la mano que contesta en {IPS[lado]}: tiene que ser la "
                      f"{'IZQUIERDA' if lado == 'izq' else 'DERECHA'} del robot", flush=True)
                antes = [max(0, min(1000, a)) for a in regs(c, ANGLE_ACT, 6)]
                movido = list(antes)
                movido[INDICE] = 600 if antes[INDICE] < 500 else 300
                print(f"    ANGLE_SET {movido} 1.5 s y despues {antes} (donde estaba)", flush=True)
                escribir(c, ANGLE_SET, movido)
                time.sleep(1.5)
                escribir(c, ANGLE_SET, antes)
                time.sleep(1.5)
            leer(c)
        finally:
            c.close()


if __name__ == "__main__":
    main()
