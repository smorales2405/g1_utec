#!/usr/bin/env bash
# Teleoperacion XR del G1 con Meta Quest 3 y manos Inspire RH56E2, todo en el PC2 (Jetson). Los brazos van por
# rt/arm_sdk (Motion Mode): las piernas siguen con la locomocion de Unitree, que se maneja con el mando.
#   0) nadie mas publicando en rt/arm_sdk (otro teleop)
#   1) servidor de imagen (teleimager, D435i por ZMQ)   -> fondo (en el G1, sin sudo: el pyrealsense2 de conda ve la D435i)
#   2) driver de las manos (Modbus TCP <-> DDS)          -> fondo
#   3) teleop_hand_and_arm.py --motion                   -> PRIMER PLANO: r empieza, q sale
# ANTES: G1 de pie en modo Regular (R1+Y en este G1, FSM 501), colgado del arnes en las primeras pruebas, alguien con el mando y nadie
# al alcance de los brazos.
set -e
AQUI="$(cd "$(dirname "$0")" && pwd)"
IFACE=${IFACE:-eth1}   # la red interna (192.168.123.164): en este G1 es eth1, no eth0
export PYTHONNOUSERSITE=1
PY=$AQUI/env_tv/bin/python
mkdir -p $AQUI/logs
YAML=$AQUI/xr_teleoperate/teleop/teleimager/cam_config_server.yaml
if grep -q POR_RELLENAR "$YAML"; then
    echo "Falta el numero de serie de la D435i en $YAML (scripts_robot/README.md, valores propios del robot)."
    exit 1
fi
if ! "$PY" "$AQUI/estado_g1.py" "$IFACE" --arm-sdk; then
    echo "Para el otro teleop antes de lanzar este."; exit 1
fi
if ! pgrep -f "teleimager[.]image_server" >/dev/null; then
    echo "==> servidor de imagen"
    (cd $AQUI/xr_teleoperate/teleop/teleimager && nohup $PY -m teleimager.image_server --rs > $AQUI/logs/image_server.log 2>&1 &)
    sleep 8
fi
if ! pgrep -f "inspire_ftp_dual_driver[.]py" >/dev/null; then
    echo "==> driver de las manos"
    nohup $PY $HOME/inspire_ftp_dual_driver.py --network "$IFACE" --no-touch > $AQUI/logs/manos.log 2>&1 &
    sleep 3
fi
# La IP de las gafas: la de la primera interfaz inalambrica con IPv4
IP=""
for i in /sys/class/net/*; do
    [ -d "$i/wireless" ] || continue
    IP=$(ip -4 -o addr show "$(basename "$i")" | awk '{print $4}' | cut -d/ -f1 | head -1)
    [ -n "$IP" ] && break
done
echo
if [ -n "$IP" ]; then
    echo "==> En las Quest 3 (WiFi $(iwgetid -r 2>/dev/null || echo '?')), navegador:  https://$IP:8012/?ws=wss://$IP:8012"
else
    echo "==> AVISO: el robot no tiene IPv4 en ninguna WiFi; las gafas no podran conectarse"
fi
echo "    Aviso de certificado: Avanzado -> Continuar. Luego Virtual Reality (sin los mandos en la mano) y permitir todo."
echo "    El peso de arm_sdk sube en 2 s y los brazos se quedan como los tiene la locomocion. Pon los brazos como el"
echo "    robot y pulsa r aqui: en 2 s pasan a seguirte. q para salir: brazos a 0 grados, abrir las manos, brazos"
echo "    a la postura de la locomocion y el peso baja a 0 en 2 s. Si se corta el SSH, el teleop sale solo como con q."
echo
cd $AQUI
# El teleop escribe solo en su log; lo que se ve aqui es un tail. Con tee, un SSH cortado le romperia la
# salida o, con la WiFi caida, la bloquearia, y tiene que poder salir como con q (ver lanzar_teleop.py).
LOG=$AQUI/logs/teleop.log
: > $LOG
tail -n +1 -f $LOG &
VISOR=$!
RC=0
PYTHONUNBUFFERED=1 $PY lanzar_teleop.py --arm=G1_29 --ee=inspire_ftp --motion --input-mode=hand --headless \
     --network-interface="$IFACE" --img-server-ip=127.0.0.1 "$@" > $LOG 2>&1 || RC=$?
sleep 1; kill $VISOR 2>/dev/null || true
exit $RC
