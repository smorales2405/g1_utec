#!/usr/bin/env bash
# Instalacion de xr_teleoperate en el PC2 del G1 (Jetson Orin, aarch64), entorno conda env_tv en esta carpeta.
# Es el instalar.sh del H1-2 (x86_64) cambiado para ARM. SIN PROBAR EN EL ROBOT. Comprobado el 2026-11-26 sin el
# robot, con conda (CONDA_SUBDIR=linux-aarch64, --dry-run) y con PyPI:
#   - conda-forge linux-aarch64 tiene pinocchio 3.1.0 (con casadi 3.6.7), nlopt 2.7.1, pyqt 5.15.11 y la libreria
#     C de cyclonedds 0.10.5;
#   - PyPI tiene ruedas aarch64 de torch 2.3.0, casadi, pupil-labs-uvc, opencv-python y rerun-sdk; NO de cyclonedds
#     0.10.2, nlopt <2.8 ni PyQt5: por eso esos tres salen de conda o se compilan.
#   - Las ruedas aarch64 de pyrealsense2 de PyPI (2.55 a 2.59) piden glibc 2.32-2.34 y el Jetson (Ubuntu 20.04) tiene
#     la 2.31: no cargan. La de conda-forge (2.58.3, sin CUDA) si: probado en el G1 el 2026-11-26, ve la D435i sin sudo.
# Antes: conda para aarch64 y xr_teleoperate clonado en esta carpeta (scripts_robot/README.md, pasos 3 y 4). En el G1
# de UTEC es Miniforge en ~/miniforge3 (solo conda-forge: sin los terminos de uso de los canales de Anaconda).
#   ./instalar.sh 2>&1 | tee instalar.log
set -e
export PYTHONNOUSERSITE=1
AQUI="$(cd "$(dirname "$0")" && pwd)"
CONDA=${CONDA:-$HOME/miniforge3/bin/conda}
[ -x "$CONDA" ] || CONDA=$HOME/miniconda3/bin/conda
ENV=$AQUI/env_tv
PIP="$ENV/bin/python -m pip"
XR=$AQUI/xr_teleoperate
[ "$(uname -m)" = "aarch64" ] || echo "AVISO: esto es para el Jetson del G1 (aarch64) y aqui es $(uname -m)"
if [ ! -x "$ENV/bin/python" ]; then
    echo "### 0. entorno conda: python 3.10, pinocchio 3.1.0 (con casadi), nlopt, pyqt y la libreria C de cyclonedds"
    "$CONDA" create -y -p "$ENV" -c conda-forge --override-channels \
        python=3.10 pinocchio=3.1.0 numpy=1.26.4 "nlopt=2.7.1" "pyqt=5.15" "cyclonedds=0.10"
fi
echo "### 1. requirements base"
$PIP install -r $XR/requirements.txt
echo "### 2. teleimager (+ servidor: realsense, zmq, aiortc, uvc)"
$PIP install -e $XR/teleop/teleimager --no-deps
$PIP install logging_mp opencv-python pyyaml pyzmq aiohttp aiortc pupil-labs-uvc
$PIP uninstall -y pyrealsense2 2>/dev/null || true      # la de PyPI no carga en el Jetson (glibc)
"$CONDA" install -y -p "$ENV" -c conda-forge --override-channels "pyrealsense2=2.58.3=cpu_py310*"
echo "### 3. televuer (vuer[all]==0.0.60) + params-proto 2.x (la 3.x rompe vuer)"
$PIP install -e $XR/teleop/televuer
$PIP install "params-proto==2.13.2"
echo "### 4. dex-retargeting SIN deps (pediria pin de pip y pisaria el pinocchio de conda); nlopt ya viene de conda"
$PIP install -e $XR/teleop/robot_control/dex-retargeting --no-deps
$PIP install "torch==2.3.0" --index-url https://download.pytorch.org/whl/cpu
$PIP install "pytransform3d>=3.5.0" "trimesh>=4.4.0" "anytree>=2.12.0" "lxml>=5.2.2"
echo "### 5. cyclonedds de python (se compila contra la libreria C de conda), unitree_sdk2py e inspire_sdkpy"
CYCLONEDDS_HOME=$ENV $PIP install "cyclonedds==0.10.2"
$PIP install -e $HOME/pc2_offline/src/unitree_sdk2_python --no-deps
$PIP install -e $HOME/pc2_offline/src/inspire_hand_sdk --no-deps
$PIP install "pymodbus==3.6.9" pyserial pyqtgraph colorcet requests   # inspire_sdkpy importa Qt al cargarse
echo "### 6. comprobacion"
"$ENV/bin/python" - <<"PY"
import pinocchio, casadi, numpy, torch, vuer, televuer, teleimager, dex_retargeting, unitree_sdk2py, inspire_sdkpy, meshcat
import cyclonedds, pyrealsense2, pymodbus
from pinocchio import casadi as cpin
print("OK pinocchio", pinocchio.__version__, "numpy", numpy.__version__, "torch", torch.__version__)
PY
"$ENV/bin/python" "$AQUI/modelo_ik.py"
echo "### LISTO"
