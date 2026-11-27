#!/usr/bin/env bash
# Entorno comun de los lanzadores de la teleoperacion del G1. Se carga con:  source "$(dirname "$0")/comun.sh"
# No lanza nada: solo fija rutas y variables.
#
# FUERA DEL ROBOT (el PC del operador) el mismo lanzador se reenvia al robot por SSH:
#   ./teleop_xr.sh   ->   ssh -t unitree@<robot> 'cd ~/utec/teleoperacion && ./teleop_xr.sh'
# El codigo que se ejecuta es SIEMPRE el del robot (~/utec/teleoperacion alli), que es el que tiene los SDK,
# los entornos y el DDS de Unitree (que no sale de la red interna). Hace falta acceso por clave:  ssh-copy-id.
# El robot se reconoce por ser ARM (el PC2 del G1 es un Jetson) y tener ~/utec/teleoperacion/xr_teleoperate.
# Los G1 de UTEC en la WiFi del laboratorio (UTEC_H1_2), y se elige con G1=<ultimo numero de la IP>:
#   ./teleop_xr.sh             el 192.168.0.151, con las manos Inspire RH56E2 (el de siempre)
#   G1=152 ./teleop_xr.sh      el 192.168.0.152, con las manos de goma: solo los brazos
# Que manos tiene cada uno no se dice aqui: lo dice ~/utec/teleoperacion/robot.conf en cada robot (config_robot.py).
#   ROBOT_SSH=unitree@192.168.123.164 ./estado.sh    # por el cable interno, si el PC esta en esa red

G1=${G1:-151}
ROBOT_SSH=${ROBOT_SSH:-unitree@192.168.0.$G1}
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
# Lo propio de ESTE robot: NOMBRE, MANOS (rh56e2 | goma), IFACE y D435I. Una IFACE puesta a mano gana a la del fichero
_iface=${IFACE:-}
NOMBRE="" MANOS="" D435I="" MAC_WIFI=""
[ -f "$TELEOP/robot.conf" ] && source "$TELEOP/robot.conf"
IFACE=${_iface:-${IFACE:-eth1}}                              # DDS de Unitree: la red interna 192.168.123.x (eth1 en el .151)

# ~/.local se cuela en cualquier python; el .bashrc del G1 pone un CYCLONEDDS_URI (el de ROS foxy) que puede sacar el DDS de eth1
export PYTHONNOUSERSITE=1
unset CYCLONEDDS_URI RMW_IMPLEMENTATION

requiere_conf() {
    # Lo que mueve el robot no sigue sin saber que manos tiene
    case "$MANOS" in
        rh56e2|goma) ;;
        *) echo "Falta $TELEOP/robot.conf con MANOS=rh56e2 o MANOS=goma (ahora: '${MANOS}'). Copia el de este"
           echo "robot de g1_teleoperation/scripts_robot/robots/ (scripts_robot/README.md, §5)."
           exit 1 ;;
    esac
    # Los dos G1 llevan la misma imagen: la MAC de la WiFi es lo que dice si este robot.conf es de este robot
    if [ -n "$MAC_WIFI" ] && ! cat /sys/class/net/*/address 2>/dev/null | grep -qix "$MAC_WIFI"; then
        echo "Este robot.conf es de $NOMBRE (MAC_WIFI=$MAC_WIFI) y este robot no tiene esa MAC: es el de otro G1."
        exit 1
    fi
}

aviso_mueve() {
    # $1 = que se mueve. Recordatorio antes de cualquier cosa que mueva el robot.
    echo "=================================================================="
    echo "  ROBOT: ${NOMBRE:-sin robot.conf}"
    echo "  ESTO MUEVE EL ROBOT: $1"
    echo "  Alguien con el mando de Unitree en la mano y nadie al alcance de"
    echo "  los brazos. L2 + B = amortiguamiento: de pie, el robot CAE."
    echo "=================================================================="
}
