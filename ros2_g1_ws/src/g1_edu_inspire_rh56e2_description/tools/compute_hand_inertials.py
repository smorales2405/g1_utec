#!/usr/bin/env python3
"""Inertials of the Inspire RH56E2 hand links, from the meshes and the scale reading.

    python3 tools/compute_hand_inertials.py           # rewrites the two hand xacros
    python3 tools/compute_hand_inertials.py --check   # are they up to date? (exit 1 if not)

What it writes, in urdf/inspire_rh56e2_hand_{left,right}.urdf.xacro, is the <inertial>
of palm_1 and of the 12 digit links (thumb_proximal ... pinky_intermediate):

  - Mass. Each hand weighs HAND_MASS: 888.5 g on the scale with its wrist coupler,
    minus the coupler's 20.4 g (the coupler is its own link, in the robot xacro). The
    digits keep the vendor's masses (DIGIT_MASS, the right hand's: the left hand's
    pinky_intermediate was a copy of pinky_proximal). hand_base_link (the flange),
    palm_2 (back cover) and the force-sensor links keep the vendor's inertials, which
    agree with their meshes. palm_1, where the six actuators and the electronics are,
    takes the rest.
  - Centre of mass and inertia tensor: those of the link's closed mesh at uniform
    density, scaled to the link's mass. The vendor's left-hand values put the CoM of
    all 12 digits outside the digit itself; the right hand's were within 9 mm.
  - palm_1 uses the right hand's mesh for both hands, mirrored (y -> -y, z - 0.5 mm in
    the palm_1 frame) for the left: it holds the six linear actuators, the left mesh
    only one. The two meshes agree to 0.1 mm everywhere else.
"""
import os
import re
import struct
import sys

import numpy as np

PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URDF = os.path.join(PKG_DIR, 'urdf', 'inspire_rh56e2_hand_{side}.urdf.xacro')
MESH = os.path.join(PKG_DIR, 'meshes', 'hand_{side}', '{side}_{part}.STL')

COUPLER_MASS = 0.0204                  # kg, on the scale
HAND_MASS = 0.8885 - COUPLER_MASS      # kg, hand + coupler on the scale = 888.5 g

# link -> (mesh part, vendor mass in kg, the right hand's)
DIGIT_MASS = {
    'thumb_proximal': ('thumb_1', 0.01537),
    'thumb_metacarpal': ('thumb_2', 0.11034),
    'thumb_intermediate': ('thumb_3', 0.01779),
    'thumb_distal': ('thumb_4', 0.00766),
    'index_proximal': ('index_1', 0.01869),
    'index_intermediate': ('index_2', 0.01102),
    'middle_proximal': ('middle_1', 0.01866),
    'middle_intermediate': ('middle_2', 0.01767),
    'ring_proximal': ('ring_1', 0.01869),
    'ring_intermediate': ('ring_2', 0.01102),
    'pinky_proximal': ('little_1', 0.01869),
    'pinky_intermediate': ('little_2', 0.01166),
}
PALM = 'palm_1'
# left palm_1 frame = right palm_1 frame mirrored in y and shifted -0.5 mm in z
PALM_MIRROR = np.diag([1.0, -1.0, 1.0])
PALM_LEFT_SHIFT = np.array([0.0, 0.0, -0.0005])


def load_stl(path):
    data = open(path, 'rb').read()
    n = struct.unpack('<I', data[80:84])[0]
    assert 84 + 50 * n == len(data), f'{path}: not a binary STL'
    rec = np.frombuffer(data[84:], dtype=np.dtype([
        ('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]), count=n)
    return rec['v'].astype(float)


def mesh_inertia(path):
    """Volume, centroid, and inertia about the centroid at unit density, of a closed mesh."""
    t = load_stl(path)
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    d = np.einsum('ij,ij->i', a, np.cross(b, c))           # 6 x signed volume of each tet
    V = d.sum() / 6
    com = (d[:, None] * (a + b + c)).sum(0) / (24 * V)
    S = np.zeros((3, 3))                                    # int x_i x_j dV
    for i in range(3):
        for j in range(3):
            S[i, j] = (d * (2 * (a[:, i] * a[:, j] + b[:, i] * b[:, j] + c[:, i] * c[:, j])
                            + a[:, i] * b[:, j] + a[:, j] * b[:, i] + a[:, i] * c[:, j]
                            + a[:, j] * c[:, i] + b[:, i] * c[:, j] + b[:, j] * c[:, i])).sum() / 120
    S -= V * np.outer(com, com)
    return V, com, np.trace(S) * np.eye(3) - S


def inertial_xml(mass, com, I, indent):
    p = indent
    return (f'<inertial>\n'
            f'{p}  <origin xyz="{com[0]:.7f} {com[1]:.7f} {com[2]:.7f}" rpy="0 0 0"/>\n'
            f'{p}  <mass value="{mass:.6f}"/>\n'
            f'{p}  <inertia ixx="{I[0, 0]:.6e}" ixy="{I[0, 1]:.6e}" ixz="{I[0, 2]:.6e}" '
            f'iyy="{I[1, 1]:.6e}" iyz="{I[1, 2]:.6e}" izz="{I[2, 2]:.6e}"/>\n'
            f'{p}</inertial>')


def link_block(text, link):
    m = re.search(r'<link name="\$\{prefix\}' + link + r'">.*?</link>', text, re.S)
    assert m, link
    return m


def masses(text):
    return {m.group(1): float(re.search(r'<mass value="([^"]*)"', m.group(2)).group(1))
            for m in re.finditer(r'<link name="\$\{prefix\}([a-z0-9_]+)">(.*?)</link>', text, re.S)
            if '<mass' in m.group(2)}


def replace_inertial(text, link, mass, com, I):
    m = link_block(text, link)
    block = m.group(0)
    im = re.search(r'( *)<inertial>.*?</inertial>', block, re.S)
    new_block = block[:im.start()] + im.group(1) + inertial_xml(mass, com, I, im.group(1)) \
        + block[im.end():]
    return text[:m.start()] + new_block + text[m.end():]


def compute(side, text):
    """The new file text for one hand, and a report of what it holds."""
    report = []
    for link, (part, mass) in DIGIT_MASS.items():
        V, com, I1 = mesh_inertia(MESH.format(side=side, part=part))
        text = replace_inertial(text, link, mass, com, I1 * mass / V)
        report.append((link, mass, mass / V))
    others = sum(m for l, m in masses(text).items() if l != PALM)
    palm_mass = HAND_MASS - others
    V, com, I1 = mesh_inertia(MESH.format(side='right', part='plam_1'))
    I = I1 * palm_mass / V
    if side == 'left':
        com = PALM_MIRROR @ com + PALM_LEFT_SHIFT
        I = PALM_MIRROR @ I @ PALM_MIRROR
    text = replace_inertial(text, PALM, palm_mass, com, I)
    report.append((PALM, palm_mass, palm_mass / V))
    total = sum(masses(text).values())
    return text, report, total


def main():
    check = '--check' in sys.argv
    stale = False
    for side in ('left', 'right'):
        path = URDF.format(side=side)
        old = open(path).read()
        new, report, total = compute(side, old)
        print(f'{side}: hand {total * 1000:.2f} g (+ coupler {COUPLER_MASS * 1000:.1f} g = '
              f'{(total + COUPLER_MASS) * 1000:.2f} g)')
        for link, m, rho in report:
            print(f'    {link:22s} {m * 1000:8.2f} g   {rho:6.0f} kg/m3')
        if check:
            if new != old:
                print(f'  {os.path.relpath(path, PKG_DIR)} is NOT up to date')
                stale = True
        elif new != old:
            open(path, 'w').write(new)
            print(f'  wrote {os.path.relpath(path, PKG_DIR)}')
    sys.exit(1 if stale else 0)


if __name__ == '__main__':
    main()
