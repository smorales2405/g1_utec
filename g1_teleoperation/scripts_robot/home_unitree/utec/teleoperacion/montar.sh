#!/usr/bin/env bash
# Montaje inicial (2026-11-26): xr_teleoperate 817fb00, Miniforge y env_tv. Log en ~/utec/teleoperacion/montar.log
set -ex
cd ~/utec/teleoperacion
if [ ! -d xr_teleoperate ]; then
    git clone https://github.com/unitreerobotics/xr_teleoperate.git
    cd xr_teleoperate && git checkout 817fb00 && git submodule update --init --recursive
    cp teleop/teleimager/cam_config_server.yaml teleop/teleimager/cam_config_server.yaml.orig
    cp /tmp/cam_config_server.yaml.g1 teleop/teleimager/cam_config_server.yaml
    git log --oneline -1; git submodule status; cd ..
fi
if [ ! -x ~/miniforge3/bin/conda ]; then
    wget -q https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh -O /tmp/Miniforge3.sh
    bash /tmp/Miniforge3.sh -b -p ~/miniforge3
    rm /tmp/Miniforge3.sh
fi
bash ~/utec/teleoperacion/instalar.sh
echo "### MONTAJE TERMINADO"
[ -f ~/utec/teleoperacion/robot.conf ] || echo "### FALTA ~/utec/teleoperacion/robot.conf: el de este robot, de g1_teleoperation/scripts_robot/robots/ (scripts_robot/README.md, §5)"
