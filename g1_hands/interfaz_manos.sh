#!/usr/bin/env bash
# Interfaz de gestos de las dos manos Inspire RH56E2 del G1, desde la laptop por la WiFi del robot.
#
#   ./interfaz_manos.sh           tunel SSH al robot (sin clave SSH, pide UNA vez la contrasena) y abre la interfaz
#   ./interfaz_manos.sh --local   sin robot: contra dos manos falsas en esta laptop (pruebas/mano_falsa.py)
#
#   ROBOT_SSH=unitree@<IP> ./interfaz_manos.sh    otra IP (por defecto la de la WiFi UTEC_H1_2, como g1_teleoperation)
#   PUERTO_IZQ=... PUERTO_DER=...                  puertos locales del tunel (16210 y 16211)
#
# Las manos estan en la red interna del robot (192.168.123.210 la izquierda y .211 la derecha, detras de eth1 del
# PC2), a la que la laptop no llega. El tunel las trae a 127.0.0.1; en el robot no se instala ni se lanza nada.
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
PY=${PY:-python3}
ROBOT_SSH=${ROBOT_SSH:-unitree@192.168.0.151}
PUERTO_IZQ=${PUERTO_IZQ:-16210}
PUERTO_DER=${PUERTO_DER:-16211}
IP_IZQ=192.168.123.210          # las de g1_teleoperation (inspire_ftp_dual_driver.py, manos.py), comprobadas
IP_DER=192.168.123.211

case "${1:-}" in
    -h|--help|ayuda) sed -n '2,11p' "$0"; exit 0 ;;
    ""|--local) ;;
    *) echo "no entiendo '$1' (./interfaz_manos.sh --help)" >&2; exit 2 ;;
esac
if ! "$PY" -c "import PyQt5.QtWidgets, pymodbus.client" 2>/dev/null; then
    echo "A $PY le faltan PyQt5 o pymodbus:  pip install PyQt5 pymodbus==3.6.9" >&2
    exit 1
fi

if [ "${1:-}" = "--local" ]; then
    "$PY" "$AQUI/pruebas/mano_falsa.py" "$PUERTO_IZQ" "$PUERTO_DER" &
    FALSAS=$!
    trap 'kill $FALSAS 2>/dev/null || true' EXIT
    sleep 1
    "$PY" "$AQUI/interfaz/main.py" --izq "127.0.0.1:$PUERTO_IZQ" --der "127.0.0.1:$PUERTO_DER" \
        --titulo "manos FALSAS, sin robot"
    exit
fi

# El ControlMaster deja el tunel en segundo plano y sirve a la interfaz para mirar, sin otra contrasena, si el
# teleop esta usando las manos
DIR=$(mktemp -d "${XDG_RUNTIME_DIR:-/tmp}/g1_manos.XXXXXX")
SOCK=$DIR/ssh
cerrar() {
    ssh -S "$SOCK" -O exit "$ROBOT_SSH" 2>/dev/null || true
    rm -rf "$DIR"
}
trap cerrar EXIT
SSH=(ssh)
if [ -n "${SSHPASS:-}" ] && command -v sshpass >/dev/null; then SSH=(sshpass -e ssh); fi   # para automatizar
echo "Túnel a las manos por $ROBOT_SSH (si no hay clave SSH, pide la contraseña de unitree)..."
"${SSH[@]}" -M -S "$SOCK" -f -N \
    -o ExitOnForwardFailure=yes -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 \
    -L "127.0.0.1:$PUERTO_IZQ:$IP_IZQ:6000" -L "127.0.0.1:$PUERTO_DER:$IP_DER:6000" "$ROBOT_SSH"
echo "Túnel abierto: izquierda en 127.0.0.1:$PUERTO_IZQ, derecha en :$PUERTO_DER. Se cierra con la interfaz."
"$PY" "$AQUI/interfaz/main.py" --izq "127.0.0.1:$PUERTO_IZQ" --der "127.0.0.1:$PUERTO_DER" \
    --ssh-control "$SOCK" --robot "$ROBOT_SSH"
