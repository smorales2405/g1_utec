"""Gestos predefinidos: los de la Interfaz de la RH56DFTP (inspire_hand_interface/Interfaz, gesture_panel.py).

Cada gesto es una lista de pasos y cada paso, los 6 valores de ANGLE_SET:
    [menique, anular, medio, indice, pulgar_flexion, pulgar_rotacion]
    0 = cerrado (flexion maxima) ... 1000 = abierto (extendido)
Los pasos se mandan uno detras de otro, separados PAUSA_PASOS_MS. "Cerrar" cierra primero los cuatro dedos y despues
el pulgar, para que este quede por fuera.

Los valores de la Pinza salieron de los grados de la RH56DFTP (indice 100 grados, flexion del pulgar 15, rotacion
155). La RH56E2 tiene otros recorridos, asi que puede no cerrar igual de bien.
"""

PAUSA_PASOS_MS = 800

GESTOS = [
    ("Abrir",         [[1000, 1000, 1000, 1000, 1000, 1000]]),
    ("Cerrar",        [[   0,    0,    0,    0, 1000, 1000],    # los cuatro dedos
                       [   0,    0,    0,    0,    0, 1000]]),  # y despues el pulgar
    ("Señalar",       [[   0,    0,    0, 1000,    0,  500]]),
    ("Pinza",         [[1000, 1000, 1000,  486,  580,  133]]),
    ("Pulgar arriba", [[   0,    0,    0,    0, 1000, 1000]]),
]

POR_NOMBRE = dict(GESTOS)
