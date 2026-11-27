#!/usr/bin/env python3
"""Lo propio de ESTE G1: ~/utec/teleoperacion/robot.conf. Cada robot tiene el suyo y el rsync del repositorio no lo
trae ni lo pisa: las plantillas de los G1 de UTEC estan en g1_teleoperation/scripts_robot/robots/.

El mismo fichero lo leen los .sh (comun.sh hace source) y los .py (leer()). Por eso solo lleva lineas CLAVE=valor,
sin espacios alrededor del =, con el valor entre comillas si tiene espacios, y comentarios con #:

    NOMBRE  como se presenta el robot en los avisos, para no lanzar en el G1 equivocado
    MANOS   rh56e2  las Inspire RH56E2 por Modbus TCP: los dedos siguen a los del operador
            goma    las manos falsas de Unitree: solo los brazos (el teleop va sin --ee)
    IFACE   la interfaz de la red interna 192.168.123.x, la del DDS de Unitree (IFACE=... a mano gana)
    D435I   numero de serie de la D435i de la cabeza (arrancar.sh lo pone en cam_config_server.yaml)
    MAC_WIFI la MAC de wlan0 de ESE robot. Los dos G1 de UTEC llevan la misma imagen clonada (misma clave de host
            SSH y, por cable, la misma 192.168.123.164), asi que es lo que los distingue: si el robot no la tiene,
            este robot.conf es de otro G1 y nada que mueva el robot arranca

    env_tv/bin/python config_robot.py      muestra lo que se lee
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(AQUI, "robot.conf")
MANOS = ("rh56e2", "goma")


def _valor(texto):
    # Como lo entenderia bash en estos casos: "entre comillas" o hasta el primer espacio (lo demas es comentario)
    texto = texto.strip()
    if texto[:1] in ("'", '"'):
        fin = texto.find(texto[0], 1)
        return texto[1:fin] if fin > 0 else texto[1:]
    partes = texto.split()
    return partes[0] if partes and not partes[0].startswith("#") else ""


def leer(ruta=RUTA):
    """{CLAVE: valor} de robot.conf; {} si no existe."""
    conf = {}
    if not os.path.exists(ruta):
        return conf
    with open(ruta) as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, resto = linea.split("=", 1)
            if clave.isidentifier():
                conf[clave] = _valor(resto)
    return conf


def macs_locales():
    """Las MAC de todas las interfaces de este equipo, en minusculas."""
    macs = set()
    for nombre in os.listdir("/sys/class/net"):
        try:
            with open(f"/sys/class/net/{nombre}/address") as f:
                macs.add(f.read().strip().lower())
        except OSError:
            pass
    return macs - {"", "00:00:00:00:00:00"}


def mac_coincide(conf):
    """True o False si robot.conf trae MAC_WIFI (este equipo la tiene o no); None si no la trae."""
    mac = conf.get("MAC_WIFI", "").lower()
    return None if not mac else mac in macs_locales()


def manos(conf=None, ruta=RUTA):
    """'rh56e2' o 'goma'. Sin robot.conf, con otro valor o con la MAC de otro robot, no se sigue."""
    conf = leer(ruta) if conf is None else conf
    valor = conf.get("MANOS")
    if valor not in MANOS:
        raise SystemExit(f"{ruta}: {'no existe' if not os.path.exists(ruta) else f'MANOS={valor!r} no vale'}. "
                         f"Hace falta MANOS={' o MANOS='.join(MANOS)}: copia el de este robot de "
                         "g1_teleoperation/scripts_robot/robots/ (scripts_robot/README.md, §5)")
    if mac_coincide(conf) is False:
        raise SystemExit(f"{ruta} es de {conf.get('NOMBRE', '?')} (MAC_WIFI={conf['MAC_WIFI']}) y este robot no "
                         f"tiene esa MAC ({', '.join(sorted(macs_locales()))}): es el robot.conf de otro G1")
    return valor


if __name__ == "__main__":
    c = leer()
    print(f"{RUTA}: {c if c else 'NO EXISTE'}")
    print(f"MAC_WIFI: {({None: 'no la trae', True: 'la tiene este robot', False: 'NO la tiene este robot'})[mac_coincide(c)]}")
    print(f"MANOS: {manos(c)}")
    sys.exit(0)
