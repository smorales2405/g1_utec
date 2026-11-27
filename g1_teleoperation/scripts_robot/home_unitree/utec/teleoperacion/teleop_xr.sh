#!/usr/bin/env bash
# Teleoperacion XR del G1 con las Quest 3: brazos por arm_sdk y, si el robot tiene las RH56E2, tambien los dedos
# (lo dice robot.conf en el robot). Atajo a arrancar.sh y parar.sh.
#   ./teleop_xr.sh           arranca en el G1 .151 (G1 de pie en modo Regular, R1+Y, y alguien con el mando)
#   G1=152 ./teleop_xr.sh    en el G1 .152, el de las manos de goma
#   ./teleop_xr.sh parar
# Detalle: ~/utec/teleoperacion/README.md en el robot
source "$(dirname "$0")/comun.sh"
case "${1:-}" in
    parar) exec "$TELEOP/parar.sh" ;;
    *) requiere_conf
       if [ "$MANOS" = rh56e2 ]; then QUE="brazos y dedos siguen"; else QUE="los brazos siguen (manos de goma)"; fi
       aviso_mueve "$QUE al operador; las piernas, con la locomocion de Unitree y el mando"
       exec "$TELEOP/arrancar.sh" "$@" ;;
esac
