# g1_edu_inspire_rh56e2_description

A self-contained ROS 2 description package for the **Unitree G1 EDU-U6** humanoid
robot (29 DOF, `mode_machine` 15) equipped with **Inspire RH56E2** five-finger hands,
or with the **fake hands** it ships with. All meshes are bundled inside the package —
no external dependencies on other description packages are required.

## Supported ROS 2

Tested with **ROS 2 Humble** on Ubuntu 22.04.

## Contents

| File | Description |
|---|---|
| `urdf/g1_29dof_body.urdf.xacro` | G1 body without hands (29 DOF) |
| `urdf/inspire_rh56e2_hand_left.urdf.xacro` | Left RH56E2 hand, xacro macro `inspire_hand_e2_left` (12 joints) |
| `urdf/inspire_rh56e2_hand_right.urdf.xacro` | Right RH56E2 hand, xacro macro `inspire_hand_e2_right` (12 joints) |
| `urdf/g1_fake_hand.urdf.xacro` | Fake hand (Unitree's rubber hand), xacro macro `g1_fake_hand` |
| `urdf/wrist_hand_coupler.urdf.xacro` | Wrist-hand coupler, xacro macro `wrist_hand_coupler` |
| `urdf/g1_with_inspire_rh56e2_hands.urdf.xacro` | Full robot — body + couplers + RH56E2 hands (53 revolute joints, 12 of them `<mimic>`) |
| `urdf/g1_with_fake_hands.urdf.xacro` | Full robot — body + couplers + fake hands (29 revolute joints) |
| `urdf/inspire_rh56e2_hand_left_standalone.urdf.xacro` | Left hand with a world link for isolated visualization |
| `urdf/inspire_rh56e2_hand_right_standalone.urdf.xacro` | Right hand with a world link for isolated visualization |
| `urdf/g1_29dof_with_RH56E2_hands.urdf` | **Flat URDF for Pinocchio and any plain-URDF consumer** (hands coupled by `<mimic>`, 38.167 kg) |
| `urdf/g1_29dof_with_fake_hands.urdf` | **Flat URDF, with the fake hands (29 DOF, 36.850 kg)** |
| `urdf/g1_29dof_handless.urdf` | **Flat URDF, body only (29 DOF, 36.390 kg)** |
| `tools/compute_hand_inertials.py` | Writes the RH56E2 inertials from the meshes and the scale reading |
| `tools/generate_flat_urdfs.py` | Regenerates the three flat URDFs from the xacro sources |
| `launch/display_*.launch.py` | RViz + joint sliders for each robot, the body, and each hand |

### Mesh directories

```
meshes/
├── g1/          ← Unitree G1 meshes (34 STL: body + the two rubber hands), byte-identical to unitree_ros
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
(`inspire_rh56e2_hand_description/urdf/inspire_hand_e2_*_macro.xacro`) with mesh
paths, colours and the inertials of 13 links changed (see *Inspire RH56E2
inertials*): same STL for visual and collision, same joints, limits and `<mimic>`
tags. It is instantiated with `prefix="left_"` / `prefix="right_"`, so every hand
link and joint name starts with the side.

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

### Wrist-hand couplers

Every hand goes on the robot with its own coupler: an aluminium part that goes into
the rectangular socket at the end of `*_wrist_yaw_link` and takes the hand on a ring
that sticks out of it (`G1 images/g1_wrist_coupler_*.jpeg`,
`wrist_hand_coupler_*.jpeg`). Each robot xacro adds one per wrist with the macro
`wrist_hand_coupler`:

```
left_wrist_yaw_link ──(left_inspire_coupler_joint / left_fake_hand_coupler_joint, fixed, xyz=0.041 0 0)──► left_*_coupler
```

The coupler is hidden by the hand, so the link has no geometry: only its mass,
**20.4 g** on the scale (the Inspire one; the fake hand's was not weighed alone and is
taken as the same), with its centre of mass on the wrist axis at the end face of the
wrist (about half of it is inside the socket, half in the ring) and the inertia of a
hollow aluminium cylinder along x, Ø38/Ø32 × 20 mm.

### Hand mounting points — Inspire RH56E2

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
`hand_mount_x = g1_wrist_end_face_x + wrist_flange_gap = 0.041 + 0.001`
(`g1_wrist_end_face_x` is defined in `wrist_hand_coupler.urdf.xacro`).

**Orientation.** Fingers along `+x` of `*_wrist_yaw_link`, thumb towards `+z` (the
wrist yaw axis) and palm facing the body (`-y` for the left hand, `+y` for the
right). This is how Unitree mounts its own Inspire hands on the G1 and how the photos
show the real robot: with the arms hanging, palms face inwards, the white covers
outwards and the thumbs forwards. Seen along the yaw axis, the screw of the flange
and the screw of the silver ring face the camera, and the flange's connector is on
the back-of-hand side, as in the photos.

### Fake hands

The hands the G1 ships with, Unitree's rubber hands (`left/right_rubber_hand.STL` from
`g1_29dof_mode_15.urdf`, link and joint names as Unitree's):

```
left_wrist_yaw_link  ──(left_hand_palm_joint,  fixed, xyz=0.041  0.003 0)──► left_rubber_hand
right_wrist_yaw_link ──(right_hand_palm_joint, fixed, xyz=0.041 -0.003 0)──► right_rubber_hand
```

Differences from Unitree's:

- **Position:** on the end face of the wrist, `x = 0.041` (Unitree: 0.0415): mounted,
  the rubber touches the wrist (`G1 images/g1_wrist_with_fakehand_*.jpeg`). `y` and
  orientation are Unitree's, and match the photos.
- **Mass:** a fake hand with its coupler weighs **230 g** on the scale (Unitree: 170 g
  without coupler). With the coupler as its own 20.4 g link, the rubber hand is
  **209.6 g**: Unitree's centre of mass, and Unitree's tensor scaled by
  209.6 / 170 = 1.2329, which keeps their mass distribution.
- **Look:** black like the real one (Unitree: white), and the mesh also as collision
  (Unitree: none).

The mesh is the rubber hand only; its coupler sits inside the rubber's wrist and the
wrist's socket.

### Colours

The body keeps Unitree's two colours (`g1_dark`, `g1_white`). The RH56E2 hands, one
colour per link as the meshes allow, as on the real hand: **silver** flange
(`*_hand_base_link`), **white** back cover (`*_palm_2`), everything else **black**
(`rh56e2_silver`, `rh56e2_white`, `rh56e2_black`, the same colours as
`h1_2_inspire_description`). The 9 mm silver ring is part of the palm mesh, so it is
drawn black. The fake hands are black (`g1_fake_hand_black`).

## Mass

All hand masses come from a scale.

| Part | Mass (kg) | Source |
|---|---|---|
| Body, no hands | 36.3900 | upstream `g1_29dof_mode_15.urdf` without its two 0.170 kg rubber hands |
| Wrist coupler, Inspire | 0.0204 | scale |
| Inspire RH56E2 hand (each) | 0.8681 | scale: 888.5 g with its coupler, minus the coupler |
| Wrist coupler, fake hand | 0.0204 | taken as the Inspire one (not weighed alone) |
| Fake hand (each) | 0.2096 | scale: 230 g with its coupler, minus the coupler |
| **G1 with RH56E2 hands** | **38.1670** | 36.390 + 2 × (0.8681 + 0.0204) |
| **G1 with fake hands** | **36.8500** | 36.390 + 2 × (0.2096 + 0.0204) |

Only one RH56E2 hand was weighed; both use its mass.

### Inspire RH56E2 inertials

The vendor's inertials could not be kept as they were:

- **The left hand's centres of mass are wrong.** All 12 digit links have their centre
  of mass outside the digit (63 mm away on `thumb_metacarpal`, about 15 mm on the
  fingers); the right hand's are within 9 mm of their meshes.
- **`left_pinky_intermediate` is a copy of `pinky_proximal`** (18.69 g, same centre
  of mass); the right one is 11.66 g. With it fixed, both vendor hands add up to the
  same 776.66 g.
- **The two `palm_1` meshes differ.** The right one holds the six linear actuators
  inside the housing, the left one only one of them; elsewhere the two agree to 0.1 mm
  once mirrored.
- **The vendor's total, 776.66 g, is 91.44 g short** of the real hand's 868.1 g.

So `tools/compute_hand_inertials.py` writes the inertials of `palm_1` and of the 12
digit links of each hand:

| Links | Mass | Centre of mass and tensor |
|---|---|---|
| 12 digits (thumb and fingers) | the vendor's (the right hand's) | the link's mesh at uniform density |
| `palm_1` | **475.26 g**: the rest of the 868.1 g (vendor: 383.82 g) | the right `palm_1` mesh at uniform density, mirrored for the left hand |
| `hand_base_link` (flange, 90 g), `palm_2`, force-sensor links | the vendor's | the vendor's (they agree with their meshes) |

The missing mass goes to the palm because that is where the six actuators and the
electronics are, the part a CAD export without its purchased parts leaves out; it
gives the palm housing with its actuators an average 2301 kg/m³. The same choice was
made in `h1_2_inspire_description`. Every centre of mass now lies inside its part,
every tensor satisfies the triangle inequality, and the left hand is the mirror of the
right (principal inertias equal to 4·10⁻⁵).

```bash
python3 tools/compute_hand_inertials.py           # after changing a mass or a mesh
python3 tools/compute_hand_inertials.py --check   # are the xacros up to date?
```

## ROS 2 Installation and Usage

```bash
cd ~/Documents/g1_utec/ros2_g1_ws
colcon build --symlink-install --packages-select g1_edu_inspire_rh56e2_description
source install/setup.bash
```

### Visualization in RViz

```bash
# G1 with both Inspire RH56E2 hands (joint sliders; the hands' mimic joints follow by themselves)
ros2 launch g1_edu_inspire_rh56e2_description display_g1_with_hands.launch.py

# G1 with its fake hands
ros2 launch g1_edu_inspire_rh56e2_description display_g1_with_fake_hands.launch.py

# G1 body only
ros2 launch g1_edu_inspire_rh56e2_description display_g1.launch.py

# Each RH56E2 hand alone
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
├── xacro:include → wrist_hand_coupler.urdf.xacro           (macro wrist_hand_coupler)
├── xacro:include → inspire_rh56e2_hand_left.urdf.xacro     (macro inspire_hand_e2_left)
├── xacro:include → inspire_rh56e2_hand_right.urdf.xacro    (macro inspire_hand_e2_right)
├── xacro:wrist_hand_coupler name="left_inspire_coupler" / "right_inspire_coupler"
├── xacro:inspire_hand_e2_left  prefix="left_"  parent="left_wrist_yaw_link"   → left_hand_connection_joint
└── xacro:inspire_hand_e2_right prefix="right_" parent="right_wrist_yaw_link"  → right_hand_connection_joint

g1_with_fake_hands.urdf.xacro
├── xacro:include → g1_29dof_body.urdf.xacro
├── xacro:include → wrist_hand_coupler.urdf.xacro           (macro wrist_hand_coupler)
├── xacro:include → g1_fake_hand.urdf.xacro                 (macro g1_fake_hand)
├── xacro:wrist_hand_coupler name="left_fake_hand_coupler" / "right_fake_hand_coupler"
└── xacro:g1_fake_hand side="left" / "right"                → left/right_hand_palm_joint
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
# model.nq == 48, model.nv == 47, pin.computeTotalMass(model) == 38.167

visual = pin.buildGeomFromUrdf(model, path, pin.GeometryType.VISUAL,
                               package_dirs=["/path/to/ros2_g1_ws/src"])
collision = pin.buildGeomFromUrdf(model, path, pin.GeometryType.COLLISION,
                                  package_dirs=["/path/to/ros2_g1_ws/src"])
# 96 visual objects, 99 collision objects
```

| Flat URDF | `nq` / `nv` (free flyer) | Mass (kg) | Visual / collision objects |
|---|---|---|---|
| `g1_29dof_with_RH56E2_hands.urdf` (`mimic=True`) | 48 / 47 | 38.167 | 96 / 99 |
| `g1_29dof_with_fake_hands.urdf` | 36 / 35 | 36.850 | 34 / 37 |
| `g1_29dof_handless.urdf` | 36 / 35 | 36.390 | 32 / 35 |

| Argument | If omitted |
|---|---|
| `mimic=True` | The 12 coupled phalanges become independent joints and `nv` goes from 47 to 59. |
| `pin.JointModelFreeFlyer()` | `pelvis` is welded to the `universe` body, so `computeTotalMass` skips its 3.813 kg. |

Links without geometry: `imu_in_torso`, `imu_in_pelvis`, `d435_link`, `mid360_link`,
the wrist couplers, and the hands' `*_base` and `*_tcp*` frames. `pelvis`,
`waist_yaw_link` and `waist_roll_link` have no collision mesh, as upstream.

### Regenerating the flat URDFs

They are generated, not maintained by hand. After any change to the xacro sources:

```bash
source install/setup.bash
python3 src/g1_edu_inspire_rh56e2_description/tools/generate_flat_urdfs.py
```

---

## Sources and licences

- G1 body and fake hands: [unitreerobotics/unitree_ros](https://github.com/unitreerobotics/unitree_ros),
  `robots/g1_description/g1_29dof_mode_15.urdf` and its meshes, commit `157ff95`
  (2026-11-13), BSD-3-Clause. Changes are listed at the top of `g1_29dof_body.urdf.xacro`
  and `g1_fake_hand.urdf.xacro`.
- Inspire RH56E2: `inspire_rh56e2_hand_description` from
  [renesas-rdk/inspire_rh56e2_hand](https://github.com/renesas-rdk/inspire_rh56e2_hand),
  Apache-2.0, generated by the vendor from Inspire's SolidWorks exports
  `RH56E2_L_2025_9_10` / `RH56E2_R_2025_9_11`. Its STL are stored with Git LFS;
  the ones here are the LFS objects, each checked against the SHA-256 of its pointer.
  Changes are listed at the top of each hand xacro.

## Maintainer

Sergio Morales — smorales@utec.edu.pe
Universidad de Ingeniería y Tecnología (UTEC), Lima, Peru
