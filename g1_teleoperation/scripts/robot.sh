#!/usr/bin/env bash
# Acceso al G1 desde el PC. En el propio robot no hace falta.
#
#   ./robot.sh               terminal en el robot, ya en ~/utec/teleoperacion
#   ./robot.sh comprobar     red, SSH por clave y estado del robot (solo lectura)
#   ./robot.sh gafas         URL para las Meta Quest 3 del teleop XR
#
# Los demas lanzadores (./teleop_xr.sh, ./estado.sh, ./manos.sh) ya se reenvian solos al robot: ver comun.sh.
# Por defecto, el G1 .151 (manos RH56E2); el .152 (manos de goma) con  G1=152 ./robot.sh comprobar
# Otra direccion:  ROBOT_SSH=unitree@<IP> ./robot.sh. Si el SSH va por el cable, la IP de las gafas (la de la
# WiFi del robot) se da aparte:  IP_GAFAS=<IP WiFi> ./robot.sh gafas
G1=${G1:-151}                                        # como en comun.sh
ROBOT_SSH=${ROBOT_SSH:-unitree@192.168.0.$G1}
IP=${ROBOT_SSH#*@}
IP_GAFAS=${IP_GAFAS:-$IP}
AQUI="$(cd "$(dirname "$0")" && pwd)"
if [ "$(uname -m)" = "aarch64" ] && [ -d /home/unitree/utec/teleoperacion/xr_teleoperate ]; then
    echo "Ya estas en el robot: usa los lanzadores directamente."; exit 0
fi
case "${1:-}" in
    "")
        exec ssh -t "$ROBOT_SSH" "cd ~/utec/teleoperacion && exec bash -l" ;;
    comprobar)
        ping -c 2 -W 1 "$IP" >/dev/null && echo "red: $IP responde" || { echo "red: $IP NO responde"; exit 1; }
        if ssh -o BatchMode=yes -o ConnectTimeout=8 "$ROBOT_SSH" true 2>/dev/null; then
            echo "ssh: acceso por clave OK"
        else
            echo "ssh: sin acceso por clave. Una sola vez:  ssh-copy-id $ROBOT_SSH"; exit 1
        fi
        exec "$AQUI/estado.sh" 2 ;;
    gafas)
        echo "En las Quest 3 (la misma WiFi que el robot):  https://$IP_GAFAS:8012/?ws=wss://$IP_GAFAS:8012"
        [ "$IP_GAFAS" = 192.168.123.164 ] && echo "  OJO: esa es la IP del cable interno; las gafas necesitan la de la WiFi del robot (IP_GAFAS=...)"
        echo "Antes, en este PC:  $([ "$G1" = 151 ] || echo "G1=$G1 ")./teleop_xr.sh   (G1 de pie en Regular con R1+Y; r empieza, q sale)" ;;
    *)
        sed -n '2,11p' "$0"; exit 1 ;;
esac
