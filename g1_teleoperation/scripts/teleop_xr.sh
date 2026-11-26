#!/usr/bin/env bash
# Teleoperacion XR del G1 con las Quest 3 (brazos por arm_sdk + manos Inspire RH56E2). Atajo a arrancar.sh y parar.sh.
#   ./teleop_xr.sh           arranca (G1 de pie en modo Regular, R1+Y, y alguien con el mando)
#   ./teleop_xr.sh parar
# Detalle: ~/utec/teleoperacion/README.md en el robot
source "$(dirname "$0")/comun.sh"
case "${1:-}" in
    parar) exec "$TELEOP/parar.sh" ;;
    *) aviso_mueve "brazos y manos siguen al operador; las piernas, con la locomocion de Unitree y el mando"
       exec "$TELEOP/arrancar.sh" "$@" ;;
esac
