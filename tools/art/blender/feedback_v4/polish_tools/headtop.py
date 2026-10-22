import sys, glob, numpy as np
from PIL import Image
D = sys.argv[1]; X = []; Y = []
for fn in sorted(glob.glob(D + "/front-full-*.png")):
    a = np.asarray(Image.open(fn).convert("RGB")).astype(int); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    bg = (abs(r - g) < 12) & (abs(g - b) < 14) & (r < 75); orange = (r > 90) & (r > g * 1.35) & (r > b * 1.8); sil = ~bg & ~orange
    ys, xs = np.nonzero(sil); top = ys.min(); sel = ys <= top + 12; X.append(xs[sel].mean()); Y.append(ys[sel].mean())
dx = [round(X[i + 1] - X[i], 1) for i in range(len(X) - 1)]; d = [round(((X[i + 1] - X[i]) ** 2 + (Y[i + 1] - Y[i]) ** 2) ** .5, 1) for i in range(len(X) - 1)]
print("dx", dx); print("d ", d)
