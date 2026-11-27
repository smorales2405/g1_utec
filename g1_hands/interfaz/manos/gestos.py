"""Gestos predefinidos: los de la Interfaz de la RH56DFTP (inspire_hand_interface/Interfaz, gesture_panel.py), sin la
Pinza, que se quito el 2026-11-26 (sus valores eran de la RH56DFTP: indice 486, pulgar 580 y 133).

Cada gesto es una lista de pasos y cada paso, los 6 valores de ANGLE_SET:
    [menique, anular, medio, indice, pulgar_flexion, pulgar_rotacion]
    0 = cerrado (flexion maxima) ... 1000 = abierto (extendido)
Los pasos se mandan uno detras de otro, separados PAUSA_PASOS_MS. "Cerrar" cierra primero los cuatro dedos y despues
el pulgar, para que este quede por fuera.
"""

PAUSA_PASOS_MS = 800

GESTOS = [
    ("Abrir",         [[1000, 1000, 1000, 1000, 1000, 1000]]),
    ("Cerrar",        [[   0,    0,    0,    0, 1000, 1000],    # los cuatro dedos
                       [   0,    0,    0,    0,    0, 1000]]),  # y despues el pulgar
    ("Señalar",       [[   0,    0,    0, 1000,    0,  500]]),
    ("Pulgar arriba", [[   0,    0,    0,    0, 1000, 1000]]),
]

POR_NOMBRE = dict(GESTOS)
