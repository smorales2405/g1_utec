#!/usr/bin/env bash
# Prueba lanzar_teleop.py en este PC, sin robot ni gafas: simulador (sim_g1_arm_sdk.py) + controlador real de
# Unitree con los parches (prueba_teleop_g1.py), en cuatro casos: normal, sin pulsar r y con fallos en la salida
# con las RH56E2 (el G1 .151), y normal con las manos de goma (el G1 .152: solo brazos, robot.conf con MANOS=goma).
#
#   ./probar.sh                 los cuatro casos
#   ./probar.sh normal|sin-r|falla-brazos|goma
#   VISOR=1 ./probar.sh normal  con el visor de MuJoCo
#
# Necesita:
#   - python3 del sistema con mujoco y unitree_sdk2py (el simulador);
#   - PY_TV: un python con lo del teleop (pinocchio, casadi, torch, dex_retargeting, logging_mp...). Por defecto
#     el entorno conda tv de este PC;
#   - XR: un xr_teleoperate en el commit del robot (817fb00) con sus submodulos. Solo se lee: se copia teleop/.
# pymodbus (lo importa inspire_sdkpy) se instala aparte, en ~/.cache/g1_teleoperation_sim, la primera vez.
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
G1T="$(dirname "$AQUI")"
TELEOP_SRC=$G1T/scripts_robot/home_unitree/utec/teleoperacion
SDK=$G1T/scripts_robot/home_unitree/pc2_offline/src
PY_TV=${PY_TV:-$HOME/miniconda3/envs/tv/bin/python}
XR=${XR:-$HOME/Documents/UTEC/CAPACITACION/code_cap/meta/xr_teleoperate}
CACHE=${XDG_CACHE_HOME:-$HOME/.cache}/g1_teleoperation_sim
export PYTHONNOUSERSITE=1

[ "$(git -C "$XR" rev-parse --short=7 HEAD 2>/dev/null)" = "817fb00" ] || echo "AVISO: $XR no esta en 817fb00"
if [ ! -d "$CACHE/pydeps/pymodbus" ]; then
    "$PY_TV" -m pip install -q --target "$CACHE/pydeps" "pymodbus==3.6.9" pyserial
fi
TMP=$(mktemp -d /tmp/g1_teleop_prueba.XXXXXX)
trap 'kill $SIM 2>/dev/null || true; rm -rf "$TMP"' EXIT
# Una carpeta como ~/utec/teleoperacion: los ficheros de este repo y una copia de teleop/ de xr_teleoperate
P=$TMP/teleoperacion
mkdir -p "$P/xr_teleoperate"
ln -s "$TELEOP_SRC/lanzar_teleop.py" "$TELEOP_SRC/modelo_ik.py" "$TELEOP_SRC/config_robot.py" "$TELEOP_SRC/modelo" "$P/"
cp -a "$XR/teleop" "$P/xr_teleoperate/"
rm -f "$P/xr_teleoperate/teleop/"*_model_cache.pkl
ln -s "$XR/assets" "$P/xr_teleoperate/assets"
TV_PATH="$SDK/unitree_sdk2_python:$SDK/inspire_hand_sdk:$CACHE/pydeps:${PYTHONPATH:-}"

caso() {
    # $1 = nombre, $2 = MANOS (rh56e2 | goma); el resto, para prueba_teleop_g1.py
    local nombre=$1 manos=$2; shift 2
    echo; echo "################ $nombre (MANOS=$manos)"
    # El robot.conf del robot que se prueba, como el de scripts_robot/robots/
    printf 'NOMBRE="simulador (MANOS=%s)"\nMANOS=%s\nIFACE=lo\nD435I=000000000000\n' "$manos" "$manos" > "$P/robot.conf"
    env -u PYTHONNOUSERSITE python3 "$AQUI/sim_g1_arm_sdk.py" --manos "$manos" --manos-cerradas --log "$TMP/$nombre.csv" \
        ${VISOR:+--visor} > "$TMP/$nombre.sim.log" 2>&1 &
    SIM=$!
    sleep 3
    local rc=0
    PYTHONPATH="$TV_PATH" "$PY_TV" -u "$AQUI/prueba_teleop_g1.py" "$P" "$@" > "$TMP/$nombre.prueba.log" 2>&1 || rc=1
    grep -v "Publish cmd\|R=\[\|Waiting to subscribe" "$TMP/$nombre.prueba.log" || true
    sleep 1; kill -TERM $SIM; wait $SIM || true
    cat "$TMP/$nombre.sim.log"
    env -u PYTHONNOUSERSITE python3 "$AQUI/prueba_teleop_g1.py" analizar "$TMP/$nombre.csv" "$@" || rc=1
    [ $rc = 0 ] && echo "==> $nombre: OK" || echo "==> $nombre: FALLO"
    return $rc
}

RC=0
case "${1:-todos}" in
    normal)       caso normal rh56e2 || RC=1 ;;
    sin-r)        caso sin-r rh56e2 --sin-r || RC=1 ;;
    falla-brazos) caso falla-brazos rh56e2 --falla-brazos || RC=1 ;;
    goma)         caso goma goma --goma || RC=1 ;;
    todos)        caso normal rh56e2 || RC=1; caso sin-r rh56e2 --sin-r || RC=1
                  caso falla-brazos rh56e2 --falla-brazos || RC=1; caso goma goma --goma || RC=1 ;;
    *)            sed -n '2,8p' "$0"; exit 1 ;;
esac
echo; [ $RC = 0 ] && echo "TODO OK" || echo "HAY FALLOS"
exit $RC
