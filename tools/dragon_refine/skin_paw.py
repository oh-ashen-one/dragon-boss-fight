#!/usr/bin/env python3
"""Weights-only toe articulation for the dragon's left front paw (leg 0) (2026-11-18). Pure NumPy.

Leg 0 has no toe bone: shin tripo::1_Left_Limb_0 -> {bone_9, tripo::1_Left_Limb_1} (siblings at the
ankle), and its toes ride ~97 % on bone_9, so the whole paw turns as one block. Leg 1 (right front)
has shin 0_Left_Limb_1 -> {bone_14, 0_Left_Limb_2 -> 0_Left_Limb_3 (toe)} with its toes blended
bone_14 ~0.7 + 0_Left_Limb_3 ~0.3, so its toes bend at the knuckles.

Without new bones, leg 0's paw copies leg 1's weight layout through the sagittal mirror (z -> -z,
nearest welded leg-1 vertex), with the bone map bone_14 -> bone_9, 0_Left_Limb_2 -> 1_Left_Limb_1,
0_Left_Limb_1 -> 1_Left_Limb_0, 0_Left_Limb_0 -> bone_7, bone_11 -> bone_6. Leg 1's toe share
(0_Left_Limb_3) goes to --toe-bone (default tripo::1_Left_Limb_1, which the unmirrored clips hold
fixed to the shin while bone_9 flexes up to 69 degrees; so the toe share lags the paw and the toes
bend at the knuckles instead of turning rigidly). Only leg-0 paw vertices below --max-height change,
blended in over a band so the ankle stays continuous.
"""
import numpy as np

from skin_smooth import weld, dense, sparse4

MAP = {'bone_14': 'bone_9', 'tripo::0_Left_Limb_2': 'tripo::1_Left_Limb_1', 'tripo::0_Left_Limb_1': 'tripo::1_Left_Limb_0',
       'tripo::0_Left_Limb_0': 'bone_7', 'bone_11': 'bone_6'}
LEG0 = ['tripo::1_Left_Limb_0', 'bone_9', 'tripo::1_Left_Limb_1']
LEG1 = ['tripo::0_Left_Limb_1', 'bone_14', 'tripo::0_Left_Limb_2', 'tripo::0_Left_Limb_3']


def paw_weights(P, J, W, names, toe_bone='tripo::1_Left_Limb_1', toe_scale=1.0, max_height=0.075, band=0.03):
    nj = len(names); ix = {n: i for i, n in enumerate(names)}
    D = dense(J, W, nj)
    leg0 = D[:, [ix[b] for b in LEG0]].sum(1) > 0.5
    leg1 = D[:, [ix[b] for b in LEG1]].sum(1) > 0.5
    sel0 = np.flatnonzero(leg0 & (P[:, 2] < 0) & (P[:, 1] < max_height))
    sel1 = np.flatnonzero(leg1 & (P[:, 2] > 0) & (P[:, 1] < max_height + band))
    Q = P[sel1] * np.array([1, 1, -1])
    out = D.copy()
    for s0 in range(0, len(sel0), 1024):
        chunk = sel0[s0:s0 + 1024]
        d = np.linalg.norm(P[chunk, None, :] - Q[None], axis=2)
        nearest = sel1[d.argmin(1)]
        src = D[nearest]
        tgt = np.zeros((len(chunk), nj))
        for j in np.flatnonzero(src.sum(0) > 0):
            name = names[j]
            if name == 'tripo::0_Left_Limb_3':
                tgt[:, ix[toe_bone]] += src[:, j] * toe_scale
                tgt[:, ix['bone_9']] += src[:, j] * (1 - toe_scale)
            else:
                tgt[:, ix[MAP.get(name, name)]] += src[:, j]
        # fade in from the ankle band so the weights stay continuous with the untouched leg
        y = P[chunk, 1]
        f = np.clip((max_height - y) / band, 0, 1); f = f * f * (3 - 2 * f)
        out[chunk] = (1 - f[:, None]) * D[chunk] + f[:, None] * tgt
    # twins share weights
    inv = weld(P); n = inv.max() + 1
    acc = np.zeros((n, nj)); c = np.zeros(n)
    np.add.at(acc, inv, out); np.add.at(c, inv, 1)
    out = (acc / c[:, None])[inv]
    J2, W2 = sparse4(out)
    changed = np.isin(inv, inv[sel0])
    J2[~changed] = J[~changed]; W2[~changed] = W[~changed]
    return J2, W2, dict(leg0PawVertices=int(changed.sum()), leg1Sources=int(len(sel1)))
