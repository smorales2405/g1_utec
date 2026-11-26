#!/usr/bin/env bash
# Entorno comun de los lanzadores de la teleoperacion del G1. Se carga con:  source "$(dirname "$0")/comun.sh"
# No lanza nada: solo fija rutas y variables.
#
# FUERA DEL ROBOT (el PC del operador) el mismo lanzador se reenvia al robot por SSH:
#   ./teleop_xr.sh   ->   ssh -t unitree@<robot> 'cd ~/utec/teleoperacion && ./teleop_xr.sh'
# El codigo que se ejecuta es SIEMPRE el del robot (~/utec/teleoperacion alli), que es el que tiene los SDK,
# los entornos y el DDS de Unitree (que no sale de la red interna, eth1 en este G1). Hace falta acceso por clave:  ssh-copy-id.
# El robot se reconoce por ser ARM (el PC2 del G1 es un Jetson) y tener ~/utec/teleoperacion/xr_teleoperate.
#   ROBOT_SSH=unitree@192.168.123.164 ./estado.sh    # por el cable interno, si el PC esta en esa red
# La WiFi del G1 de UTEC es la del laboratorio (UTEC_H1_2), y alli el robot es la 192.168.0.151 (2026-11-26).

ROBOT_SSH=${ROBOT_SSH:-unitree@192.168.0.151}
if [ "$(uname -m)" != "aarch64" ] || [ ! -d /home/unitree/utec/teleoperacion/xr_teleoperate ]; then
    _base="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    _yo="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
    _rel="${_yo#"$_base"/}"
    _args=""
    for _a in "$@"; do _args+=" $(printf '%q' "$_a")"; done
    _env=""                                       # IFACE la usa estado.sh, tambien viaja
    [ -n "${IFACE:-}" ] && _env="IFACE=$(printf '%q' "$IFACE") "
    echo "(en el robot $ROBOT_SSH) ${_env}~/utec/teleoperacion/$_rel$_args" >&2
    exec ssh -t -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 \
         "$ROBOT_SSH" "cd ~/utec/teleoperacion && ${_env}./$_rel$_args"
fi

TELEOP=/home/unitree/utec/teleoperacion
PY=$TELEOP/env_tv/bin/python                                 # el del teleop, el driver de las manos y estado.sh
IFACE=${IFACE:-eth1}                                         # DDS de Unitree: la red interna 192.168.123.x, que en este G1 es eth1

# ~/.local se cuela en cualquier python; el .bashrc del G1 pone un CYCLONEDDS_URI (el de ROS foxy) que puede sacar el DDS de eth1
export PYTHONNOUSERSITE=1
unset CYCLONEDDS_URI RMW_IMPLEMENTATION

aviso_mueve() {
    # $1 = que se mueve. Recordatorio antes de cualquier cosa que mueva el robot.
    echo "=================================================================="
    echo "  ESTO MUEVE EL ROBOT: $1"
    echo "  Alguien con el mando de Unitree en la mano y nadie al alcance de"
    echo "  los brazos. L2 + B = amortiguamiento: de pie, el robot CAE."
    echo "=================================================================="
}
