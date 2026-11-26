#!/usr/bin/env bash
# Para el servidor de imagen y el driver de las manos (el teleop se sale con q).
# Si el teleop sigue vivo, se le manda SIGINT SOLO al proceso principal (-o, el mas antiguo): sale como con q (brazos
# a la locomocion y peso de arm_sdk a 0). A sus hijos no: el de las manos tiene que seguir vivo para abrirlas.
if pgrep -f "lanzar_teleop[.]py" >/dev/null; then
    pkill -INT -o -f "lanzar_teleop[.]py" 2>/dev/null || true
    for _ in $(seq 1 15); do pgrep -f "lanzar_teleop[.]py" >/dev/null || break; sleep 1; done
fi
pkill -f "inspire_ftp_dual_driver[.]py" 2>/dev/null || true
pkill -f "teleimager[.]image_server" 2>/dev/null || true
sleep 1; pgrep -af "lanzar_teleop|inspire_ftp_dual|teleimager.image_server" | grep -v pgrep || echo "parado"
