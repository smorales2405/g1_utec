# g1_edu_inspire_rh56e2_description

A self-contained ROS 2 description package for the **Unitree G1 EDU-U6** humanoid
robot (29 DOF, `mode_machine` 15) equipped with **Inspire RH56E2** five-finger hands.
All meshes are bundled inside the package — no external dependencies on other
description packages are required.

## Supported ROS 2

Tested with **ROS 2 Humble** on Ubuntu 22.04.

## Contents

| File | Description |
|---|---|
| `urdf/g1_29dof_body.urdf.xacro` | G1 body without hands (29 DOF) |
| `urdf/inspire_rh56e2_hand_left.urdf.xacro` | Left RH56E2 hand, xacro macro `inspire_hand_e2_left` (12 joints) |
| `urdf/inspire_rh56e2_hand_right.urdf.xacro` | Right RH56E2 hand, xacro macro `inspire_hand_e2_right` (12 joints) |
| `urdf/g1_with_inspire_rh56e2_hands.urdf.xacro` | Full robot — body + both hands (53 revolute joints, 12 of them `<mimic>`) |
| `urdf/inspire_rh56e2_hand_left_standalone.urdf.xacro` | Left hand with a world link for isolated visualization |
| `urdf/inspire_rh56e2_hand_right_standalone.urdf.xacro` | Right hand with a world link for isolated visualization |
| `urdf/g1_29dof_with_RH56E2_hands.urdf` | **Flat URDF for Pinocchio and any plain-URDF consumer** (hands coupled by `<mimic>`) |
| `urdf/g1_29dof_handless.urdf` | **Flat URDF, body only (29 DOF, 36.390 kg)** |
| `tools/generate_flat_urdfs.py` | Regenerates the two flat URDFs from the xacro sources |
| `launch/display_*.launch.py` | RViz + joint sliders for the full robot, the body, and each hand |

### Mesh directories

```
meshes/
├── g1/          ← Unitree G1 body meshes (32 STL), byte-identical to unitree_ros
├── hand_left/   ← Inspire RH56E2 left hand meshes (32 STL), visual and collision
└── hand_right/  ← Inspire RH56E2 right hand meshes (32 STL), visual and collision
```

Every mesh file name is unique across the package (the vendor's two `base_link.STL`
are `left_base_link.STL` and `right_base_link.STL` here), so tools that name meshes
after their file, such as MuJoCo, do not mix them up.

## Which G1

Unitree publishes one URDF per hardware variant (`robots/g1_description/README.md` in
[unitree_ros](https://github.com/unitreerobotics/unitree_ros)). The body here is
**`g1_29dof_mode_15.urdf`**, picked from photos of the real robot and confirmed with
its *Machine Type* (Unitree app: Device → Data → Robot → Machine Type = 15):

| Feature on the real robot | URDF variants it rules in |
|---|---|
| 3-DOF waist, 3-DOF wrists | the `29dof` ones |
| Wrist yaw link: flat oval cover as wide as its base block, disc around it ≈ 1.3× wider | **5010** wrist motors (modes 13–18); the 4010 wrist has a narrow dome on a flared lip, disc ≈ 1.6× wider |
| Pelvis: square cover on the front, rounded panel and notch at the back | **`pelvis_ver0529.STL`** (modes 15, 16, 18) |

Modes 15, 16 and 18 share kinematics and meshes; 16 locks the waist roll/pitch and
18 has 100 N·m waist roll/pitch motors. With another `mode_machine`, take its file
from unitree_ros instead. Note that the 5010 wrist is not just a mesh change:
`*_wrist_yaw_joint` sits at `x = 0.051` on the pitch link (0.046 with the 4010).

## Kinematics summary

### G1 body (29 DOF)
- 6 DOF per leg × 2 (hip pitch/roll/yaw, knee, ankle pitch/roll)
- 3 DOF waist (yaw, roll, pitch)
- 7 DOF per arm × 2 (shoulder pitch/roll/yaw, elbow, wrist roll/pitch/yaw)

At `q = 0` the forearms point forward with the elbows bent, as in Unitree's model.

### Inspire RH56E2 hands (12 joints each)

The hand xacro is the vendor's macro
(`inspire_rh56e2_hand_description/urdf/inspire_hand_e2_*_macro.xacro`) with only
mesh paths and colours changed: same STL for visual and collision, same joints,
limits, `<mimic>` tags and inertials. It is instantiated with `prefix="left_"` /
`prefix="right_"`, so every hand link and joint name starts with the side.

| DOF | Actuated joint | Range (rad) | Mimic joint(s) | Multiplier |
|---|---|---|---|---|
| thumb rotation | `*_thumb_proximal_yaw_joint` | 0 … 1.658 | — | |
| thumb bending | `*_thumb_proximal_pitch_joint` | 0 … 0.62 | `*_thumb_intermediate_joint`, `*_thumb_distal_joint` | 0.8392, 0.7477272 |
| index | `*_index_proximal_joint` | 0 … 1.4381 | `*_index_intermediate_joint` | 1.0843 |
| middle | `*_middle_proximal_joint` | 0 … 1.4381 | `*_middle_intermediate_joint` | 1.0843 |
| ring | `*_ring_proximal_joint` | 0 … 1.4381 | `*_ring_intermediate_joint` | 1.0843 |
| little | `*_pinky_proximal_joint` | 0 … 1.4381 | `*_pinky_intermediate_joint` | 1.0843 |

`q = 0` is the open hand and every joint closes as `q` grows. Both mimics of the thumb
follow `thumb_proximal_pitch_joint` directly (Inspire's export chains `thumb_4` on
`thumb_3` with 0.891; 0.8392 × 0.891 = 0.7477), so consumers that do not support
chained mimics, such as Pinocchio, read them right. The coupling of the real hand is
not linear; the mimics are the vendor's linear approximation (a measured coupling as
in `h1_2_inspire_description` is not part of this package yet).

Other hand frames from the vendor: `*_base` (top of the flange), `*_hand_base_link`
(the vendor CAD frame, `*_base` turned by π about x), `*_tcp` and
`*_tcp_three_fingers`, `*_tcp_pinch`, `*_tcp_full_hand`, plus a fixed link per
force-sensor pad (`*_<digit>_force_sensor_<n>`, `*_palm_force_sensor`).

### Hand mounting points

```
left_wrist_yaw_link  ──(left_hand_connection_joint,  fixed, xyz=0.042 0 0, rpy=-π/2 0 -π/2)──► left_base
right_wrist_yaw_link ──(right_hand_connection_joint, fixed, xyz=0.042 0 0, rpy= π/2 0  π/2)──► right_base
```

From the wrist outwards, measured on the real robot
(`G1 images/g1_arm_hand_coupling_dimensions.jpeg`):

| Part | Size | In the model |
|---|---|---|
| End face of `*_wrist_yaw_link` (5010) | — | `x = 0.041`, Unitree's mesh |
| Gap | 1 mm | `x = 0.041 … 0.042` |
| Hand flange, aluminium | Ø50 × 30 mm | `*_base_link.STL`, `x = 0.042 … 0.072` |
| Silver ring (label, screw), then the black palm | 9 mm | top of `*_plam_1.STL`, which the vendor's model puts 1 mm after the flange |

The mount offset is a property of `g1_with_inspire_rh56e2_hands.urdf.xacro`:
`hand_mount_x = wrist_end_face_x + wrist_flange_gap = 0.041 + 0.001`.

**Orientation.** Fingers along `+x` of `*_wrist_yaw_link`, thumb towards `+z` (the
wrist yaw axis) and palm facing the body (`-y` for the left hand, `+y` for the
right). This is how Unitree mounts its own Inspire hands on the G1 and how the photos
show the real robot: with the arms hanging, palms face inwards, the white covers
outwards and the thumbs forwards. Seen along the yaw axis, the screw of the flange
and the screw of the silver ring face the camera, and the flange's connector is on
the back-of-hand side, as in the photos.

### Colours

The body keeps Unitree's two colours (`g1_dark`, `g1_white`). The hands, one colour
per link as the meshes allow, as on the real hand: **silver** flange
(`*_hand_base_link`), **white** back cover (`*_palm_2`), everything else **black**
(`rh56e2_silver`, `rh56e2_white`, `rh56e2_black`, the same colours as
`h1_2_inspire_description`). The 9 mm silver ring is part of the palm mesh, so it is
drawn black.

### Mass

| Part | Mass (kg) | Source |
|---|---|---|
| Body, no hands | 36.3900 | upstream `g1_29dof_mode_15.urdf` without its two 0.170 kg rubber hands |
| Left hand | 0.78369 | vendor URDF (sum of 33 links) |
| Right hand | 0.77666 | vendor URDF (sum of 33 links) |
| **Full robot with both hands** | **37.9504** | |

The hand masses are the vendor's CAD export, not a scale reading.

## ROS 2 Installation and Usage

```bash
cd ~/Documents/g1_utec/ros2_g1_ws
colcon build --symlink-install --packages-select g1_edu_inspire_rh56e2_description
source install/setup.bash
```

### Visualization in RViz

```bash
# Full robot with both hands (joint sliders; the hands' mimic joints follow by themselves)
ros2 launch g1_edu_inspire_rh56e2_description display_g1_with_hands.launch.py

# G1 body only
ros2 launch g1_edu_inspire_rh56e2_description display_g1.launch.py

# Each hand alone
ros2 launch g1_edu_inspire_rh56e2_description display_hand_left.launch.py
ros2 launch g1_edu_inspire_rh56e2_description display_hand_right.launch.py
```

Every launch takes `gui:=false` (plain `joint_state_publisher`, no sliders) and
`rviz_config:=<file>`. robot_state_publisher warns that KDL ignores the inertia of the
root link `pelvis`; Unitree's URDFs all do that and it does not affect TF.

### Xacro architecture

```
g1_with_inspire_rh56e2_hands.urdf.xacro
├── xacro:include → g1_29dof_body.urdf.xacro
├── xacro:include → inspire_rh56e2_hand_left.urdf.xacro   (macro inspire_hand_e2_left)
├── xacro:include → inspire_rh56e2_hand_right.urdf.xacro  (macro inspire_hand_e2_right)
├── xacro:inspire_hand_e2_left  prefix="left_"  parent="left_wrist_yaw_link"   → left_hand_connection_joint
└── xacro:inspire_hand_e2_right prefix="right_" parent="right_wrist_yaw_link"  → right_hand_connection_joint
```

---

## Using the model with Pinocchio

`urdf/g1_29dof_with_RH56E2_hands.urdf` is the xacro tree flattened into a single
plain URDF.

```python
import pinocchio as pin

path = "/path/to/ros2_g1_ws/src/g1_edu_inspire_rh56e2_description/urdf/g1_29dof_with_RH56E2_hands.urdf"
model = pin.buildModelFromUrdf(path, pin.JointModelFreeFlyer(), mimic=True)
data = model.createData()
# model.nq == 48, model.nv == 47, pin.computeTotalMass(model) == 37.95036

visual = pin.buildGeomFromUrdf(model, path, pin.GeometryType.VISUAL,
                               package_dirs=["/path/to/ros2_g1_ws/src"])
collision = pin.buildGeomFromUrdf(model, path, pin.GeometryType.COLLISION,
                                  package_dirs=["/path/to/ros2_g1_ws/src"])
# 96 visual objects, 99 collision objects
```

`urdf/g1_29dof_handless.urdf` is the body alone (`nq == 36`, `nv == 35`, 36.390 kg).

| Argument | If omitted |
|---|---|
| `mimic=True` | The 12 coupled phalanges become independent joints and `nv` goes from 47 to 59. |
| `pin.JointModelFreeFlyer()` | `pelvis` is welded to the `universe` body, so `computeTotalMass` skips its 3.813 kg. |

Links without geometry: `imu_in_torso`, `imu_in_pelvis`, `d435_link`, `mid360_link`
and the hands' `*_base` and `*_tcp*` frames. `pelvis`, `waist_yaw_link` and
`waist_roll_link` have no collision mesh, as upstream.

### Regenerating the flat URDFs

They are generated, not maintained by hand. After any change to the xacro sources:

```bash
source install/setup.bash
python3 src/g1_edu_inspire_rh56e2_description/tools/generate_flat_urdfs.py
```

---

## Sources and licences

- G1 body: [unitreerobotics/unitree_ros](https://github.com/unitreerobotics/unitree_ros),
  `robots/g1_description/g1_29dof_mode_15.urdf` and its meshes, commit `157ff95`
  (2026-11-13), BSD-3-Clause. Changes are listed at the top of `g1_29dof_body.urdf.xacro`.
- Inspire RH56E2: `inspire_rh56e2_hand_description` from
  [renesas-rdk/inspire_rh56e2_hand](https://github.com/renesas-rdk/inspire_rh56e2_hand),
  Apache-2.0, generated by the vendor from Inspire's SolidWorks exports
  `RH56E2_L_2025_9_10` / `RH56E2_R_2025_9_11`. Its STL are stored with Git LFS;
  the ones here are the LFS objects, each checked against the SHA-256 of its pointer.
  Changes are listed at the top of each hand xacro.

## Maintainer

Sergio Morales — smorales@utec.edu.pe
Universidad de Ingeniería y Tecnología (UTEC), Lima, Peru
