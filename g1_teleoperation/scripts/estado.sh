#!/usr/bin/env bash
# SOLO LECTURA: estado del robot en unos segundos (no publica nada, no puede mover el robot).
#   ./estado.sh        robot.conf, lowstate durante 3 s, si alguien publica en rt/arm_sdk, CheckMode, FSM y las manos
#   G1=152 ./estado.sh en el G1 .152 (desde el PC)
#   ./estado.sh 10     lowstate durante 10 s
# Detalle: estado_g1.py
source "$(dirname "$0")/comun.sh"
exec "$PY" "$TELEOP/estado_g1.py" "$IFACE" "${1:-3}"
