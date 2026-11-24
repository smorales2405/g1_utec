# g1_utec

Modelo del **Unitree G1 EDU-U6** (29 DOF, `mode_machine` 15) con manos
**Inspire RH56E2**, como el robot real del laboratorio, o con las **fake hands** de
Unitree. Las masas de las manos y de sus acoples son las de la balanza.

```
ros2_g1_ws/                               workspace ROS 2 (Humble)
└── src/
    └── g1_edu_inspire_rh56e2_description/    URDF/xacro, meshes, launch y RViz del G1 con las manos
        ├── urdf/        cuerpo, manos RH56E2, fake hands, acoples, robots completos y URDF planos (Pinocchio)
        ├── meshes/      g1/ (Unitree, con las fake hands), hand_left/ y hand_right/ (RH56E2)
        ├── launch/      visualización en RViz con sliders de joints
        ├── rviz/
        ├── tools/       inercias de la RH56E2 desde los meshes; regenera los URDF planos
        └── README.md    detalles: variante del G1, montaje de las manos, masas, uso
```

## Uso rápido

```bash
cd ros2_g1_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch g1_edu_inspire_rh56e2_description display_g1_with_hands.launch.py       # manos RH56E2
ros2 launch g1_edu_inspire_rh56e2_description display_g1_with_fake_hands.launch.py  # fake hands
```

La documentación completa está en
[`ros2_g1_ws/src/g1_edu_inspire_rh56e2_description/README.md`](ros2_g1_ws/src/g1_edu_inspire_rh56e2_description/README.md).
