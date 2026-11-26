"""Registros Modbus TCP de las manos Inspire RH56E2 del G1 y como se leen.

Son los mismos que usan g1_teleoperation (manos.py, inspire_ftp_dual_driver.py) y la Interfaz de la RH56DFTP:
la RH56E2 tiene la misma tabla. Dos cosas comprobadas en el G1 el 2026-11-26 (g1_teleoperation, README §9):

  - 192.168.123.210 es la mano IZQUIERDA y .211 la DERECHA (perspectiva del propio robot), al reves que en el H1-2.
  - ANGLE_SET se escribe SIEMPRE como bloque de 6 desde 1486: las direcciones de la tabla son de byte (cada dedo
    ocupa 2) y escribir un registro suelto en 1486 + 3 movio el ANULAR, no el indice.
"""

PUERTO = 6000      # Modbus TCP de cada mano
ID_MANO = 1        # las dos manos reportan HAND_ID 1

IPS = {"izq": "192.168.123.210", "der": "192.168.123.211"}
NOMBRE_LADO = {"izq": "IZQUIERDA", "der": "DERECHA"}

# Orden de los 6 grados de libertad en todos los bloques
DEDOS = ["Meñique", "Anular", "Medio", "Índice", "Pulgar (flex.)", "Pulgar (rot.)"]

# Bloques de 6 valores de 16 bits
ANGLE_SET = 1486   # consigna de angulo, 0 = cerrado ... 1000 = abierto. Solo escribirla: leida NO devuelve la
                   # consigna (con las manos abiertas daba [0, 0, 0, 0, 0, 208] y [0, 0, 0, 0, 0, 160])
SPEED_SET = 1522   # velocidad, 0-1000. La mano la recupera de DEFAULT_SPEED_SET (1032) al encenderse
ANGLE_ACT = 1546   # angulo medido, misma escala que ANGLE_SET
FORCE_ACT = 1582   # fuerza medida, en gramos-fuerza, con signo
# Bloques de 6 valores de 1 byte, empaquetados en 3 registros
ERROR = 1606
STATUS = 1612
TEMP = 1618        # grados C
# Un registro suelto
CLEAR_ERROR = 1004  # escribir 1 borra el fallo de los dedos

# Dentro de cada registro, el byte del dedo par va en el byte BAJO, como en manos.py de g1_teleoperation. Comprobado
# en el G1 el 2026-11-26 moviendo solo el indice (pruebas/prueba_enlace.py indice): el STATUS que seguia en
# movimiento era el del indice. El SDK de Inspire (inspire_sdk.py) los toma AL REVES, asi que el err, status y
# temperatura que publica el driver del teleop salen cambiados por parejas de dedos.
BYTE_BAJO_PRIMERO = True

# STATUS de cada dedo (manual de la RH56; 255 es lo que leen las RH56E2 del G1 en reposo). Al recibir un ANGLE_SET
# la mano real pone los 6 dedos en 0/1 un instante, y a veces se quedan asi un rato despues de llegar
ESTADOS = {
    0: ("#2196F3", "Abriendo"),
    1: ("#FF9800", "Cerrando"),
    2: ("#4CAF50", "En posición"),
    3: ("#FF9800", "Límite de fuerza"),
    5: ("#F44336", "Prot. corriente"),
    6: ("#F44336", "Bloqueado"),
    7: ("#F44336", "Fallo actuador"),
    255: ("#9E9E9E", "Reposo"),
}

# Bits de ERROR (manual de la RH56). El "err 5" de g1_teleoperation es bloqueo + sobrecorriente
BITS_ERROR = ["bloqueo", "sobretemperatura", "sobrecorriente", "motor", "comunicación"]


def con_signo(registros):
    """Registros de 16 bits sin signo (pymodbus) -> enteros con signo."""
    return [r - 65536 if r > 32767 else r for r in registros]


def a_bytes(registros):
    """3 registros -> los 6 bytes de un bloque de bytes (ERROR, STATUS, TEMP)."""
    salida = []
    for r in registros:
        bajo, alto = r & 0xFF, (r >> 8) & 0xFF
        salida += [bajo, alto] if BYTE_BAJO_PRIMERO else [alto, bajo]
    return salida


def de_bytes(valores):
    """Lo contrario de a_bytes (lo usa la mano falsa de las pruebas)."""
    regs = []
    for i in range(0, len(valores), 2):
        a, b = valores[i] & 0xFF, valores[i + 1] & 0xFF
        regs.append(a | (b << 8) if BYTE_BAJO_PRIMERO else (a << 8) | b)
    return regs


def describir_error(codigo):
    if not codigo:
        return "sin fallo"
    partes = [n for i, n in enumerate(BITS_ERROR) if codigo & (1 << i)]
    return ", ".join(partes) if partes else f"código {codigo}"


def texto_bloque(valores):
    """[1000]*6 -> '1000'; si los 6 no son iguales, la lista."""
    return str(valores[0]) if valores and len(set(valores)) == 1 else str(valores)
