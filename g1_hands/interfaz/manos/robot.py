"""Comprueba en el robot, por la conexion SSH del tunel, si alguien mas esta mandando las manos.

El teleop de g1_teleoperation escribe en las manos con su driver (inspire_ftp_dual_driver.py) a 100 Hz. Si la
interfaz escribiera a la vez, la mano obedeceria a los dos. Por eso la interfaz no se conecta mientras corre el
driver o el teleop, y se suelta en cuanto los ve aparecer. (Las RH56E2 del G1 aceptan dos clientes Modbus a la vez,
comprobado leyendo el 2026-11-26, asi que el driver puede conectar aunque la interfaz siga conectada; aun asi se
suelta, para no escribir los dos.)

La comprobacion va por el ControlMaster del tunel (ssh -S): no pide otra vez la contrasena.
"""

# El [.] evita que pgrep se encuentre a si mismo (su linea de comando lleva "[.]", no ".")
PATRON = "inspire_ftp_dual_driver[.]py|lanzar_teleop[.]py|teleop_hand_and_arm[.]py"


def comando(control, robot):
    """argv de ssh que lista los procesos que usan las manos. Codigo 0: hay alguno; 1: ninguno; otro: fallo."""
    return ["ssh", "-S", control, "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", robot,
            f"pgrep -af '{PATRON}'"]


def interpretar(codigo, salida):
    """-> (libre, texto). libre es True, False o None (no se pudo comprobar)."""
    if codigo == 1:
        return True, "teleop y driver de las manos parados"
    if codigo == 0:
        procesos = []
        for linea in salida.splitlines():
            for nombre in ("inspire_ftp_dual_driver.py", "lanzar_teleop.py", "teleop_hand_and_arm.py"):
                if nombre in linea and nombre not in procesos:
                    procesos.append(nombre)
        return False, "corriendo en el robot: " + ", ".join(procesos or ["?"])
    return None, f"no se pudo comprobar el robot (ssh salió con {codigo}): {salida.strip()[:120]}"
