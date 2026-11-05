"""CPU silhouettes of the dragon against the source clip's panel masks (numpy + cv2 only).
The cameras of the clip are ortho, so each panel is an affine map  pixel = X @ A.T + b  (armature space -> the panel's own pixels,
pixel j covers [j, j+1)); `views.npz` (written by prep_wings_rl.py) keeps A, b and the panel's crop of the 1280x720 mask frame.
"""
import numpy as np, cv2

class Views:
    def __init__(self, path, masks_path=None):
        z = np.load(path, allow_pickle=True)
        self.names = [str(n) for n in z["names"]]; self.A = z["A"]; self.b = z["b"]; self.crop = z["crop"].astype(int)   # crop [V,4] = x0, y0, w, h
        self.masks = None if masks_path is None else np.load(masks_path)["masks"]
    @property
    def n(self): return len(self.names)
    def panel_mask(self, f, k):
        x0, y0, w, h = self.crop[k]; return self.masks[f, y0:y0 + h, x0:x0 + w]
    def project(self, X, k): return X @ self.A[k].T + self.b[k]
    def fill(self, X, tris, k, img=None):
        """filled silhouette (uint8 0/1) of triangles `tris` of vertex array X in panel k, drawn onto `img` when given"""
        x0, y0, w, h = self.crop[k]
        if img is None: img = np.zeros((h, w), np.uint8)
        if len(tris) == 0: return img
        P = np.round((self.project(X, k) - 0.5) * 16).astype(np.int32)
        for t in P[tris]: cv2.fillConvexPoly(img, t, 1, cv2.LINE_8, 4)       # one call per triangle: fillPoly on a list fills overlaps even-odd (holes)
        return img
def iou(a, b):
    a = a.astype(bool); b = b.astype(bool); u = (a | b).sum(); return float((a & b).sum() / u) if u else 1.0
def extents(mask):
    """(top row, bottom row, left col, right col) of a bool panel mask, or None"""
    ys, xs = np.where(mask)
    return None if not len(ys) else (int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max()))
