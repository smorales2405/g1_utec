#!/usr/bin/env bash
# Manos Inspire RH56E2 del G1 .151 (Modbus TCP: izq 192.168.123.210, der .211, comprobado). Detalle: manos.py
#
#   ./manos.sh leer [izq|der|ambas]            estado de cada dedo (SOLO LECTURA)
#   ./manos.sh abrir [izq|der|ambas]           abrir todos los dedos
#   ./manos.sh dedo izq|der                    cerrar a medias y abrir el indice: ¿es la mano que dice?
#   ./manos.sh borrar-error [izq|der|ambas]    borrar un dedo en fallo (registro 1004)
source "$(dirname "$0")/comun.sh"
case "${1:-}" in
    ""|-h|--help|ayuda) sed -n '2,8p' "$0"; exit 0 ;;
esac
requiere_conf
if [ "$MANOS" != rh56e2 ]; then
    echo "$NOMBRE: robot.conf dice MANOS=$MANOS, no hay manos RH56E2 que leer ni mover."; exit 1
fi
[ "$1" = leer ] || aviso_mueve "los dedos de las manos"
exec "$PY" "$TELEOP/manos.py" "$@"
