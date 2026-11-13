"""STEP 형상을 클라우드 서버에서 열어 외곽 치수(바운딩 박스)를 재고 미리보기 이미지를 만든다.

필요 패키지:  pip install cadquery-ocp matplotlib numpy
시스템 패키지: sudo apt-get update && sudo apt-get install -y libosmesa6 libgl1

사용법:
    python day1/step_inspect.py data/deid/LPM_OPENER_deid.stp
"""
import argparse, json, os, re, time
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopoDS import TopoDS
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location

def _static(cls, name):
    return getattr(cls, name + "_s", None) or getattr(cls, name)

to_face = _static(TopoDS, "Face")
bnd_add = _static(BRepBndLib, "Add")
get_triangulation = _static(BRep_Tool, "Triangulation")


def load_step(path):
    reader = STEPControl_Reader()
    if reader.ReadFile(path) != IFSelect_RetDone:
        raise RuntimeError(f"STEP 읽기 실패: {path}")
    reader.TransferRoots()
    return reader.OneShape()


def bounding_box(shape):
    box = Bnd_Box()
    bnd_add(shape, box)
    pmin, pmax = box.CornerMin(), box.CornerMax()
    return [pmin.X(), pmin.Y(), pmin.Z()], [pmax.X(), pmax.Y(), pmax.Z()]


def count_solids(shape):
    exp, n = TopExp_Explorer(shape, TopAbs_SOLID), 0
    while exp.More():
        n += 1; exp.Next()
    return n


def triangles(shape, deflection):
    BRepMesh_IncrementalMesh(shape, deflection, False, 0.8, True)
    tris = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = to_face(exp.Current())
        loc = TopLoc_Location()
        tri = get_triangulation(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            pts = [tri.Node(i).Transformed(trsf) for i in range(1, tri.NbNodes() + 1)]
            pts = np.array([[p.X(), p.Y(), p.Z()] for p in pts])
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                tris.append(pts[[a-1, b-1, c-1]])
        exp.Next()
    return np.array(tris)


def render(tris, out_png, title, max_tris=250000):
    if len(tris) > max_tris:
        idx = np.linspace(0, len(tris)-1, max_tris).astype(int)
        tris = tris[idx]
    fig = plt.figure(figsize=(8, 7), dpi=110)
    ax = fig.add_subplot(111, projection="3d")
    n = np.cross(tris[:,1]-tris[:,0], tris[:,2]-tris[:,0])
    n /= (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
    light = np.array([0.4, -0.6, 0.7]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.abs(n @ light)
    colors = np.c_[0.35*shade, 0.5*shade, 0.75*shade, np.ones_like(shade)]
    ax.add_collection3d(Poly3DCollection(tris, facecolors=colors, linewidths=0))
    allp = tris.reshape(-1, 3)
    lo, hi = allp.min(0), allp.max(0)
    c, r = (lo+hi)/2, (hi-lo).max()/2
    ax.set_xlim(c[0]-r, c[0]+r); ax.set_ylim(c[1]-r, c[1]+r); ax.set_zlim(c[2]-r, c[2]+r)
    ax.view_init(elev=22, azim=-55)
    ax.set_axis_off(); ax.set_title(title)
    fig.tight_layout(); fig.savefig(out_png); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--out", default="data/out")
    ap.add_argument("--deflection", type=float, default=20.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.file))[0]

    t0 = time.time()
    shape = load_step(a.file)
    t1 = time.time()
    lo, hi = bounding_box(shape)
    size = [round(h-l, 1) for l, h in zip(lo, hi)]
    tris = triangles(shape, a.deflection)
    t2 = time.time()
    render(tris, os.path.join(a.out, f"{stem}_preview.png"),
           f"{stem}  {size[0]} x {size[1]} x {size[2]} mm")

    summary = {
        "file": os.path.basename(a.file),
        "bbox_min": [round(v,1) for v in lo],
        "bbox_max": [round(v,1) for v in hi],
        "W_mm": size[0], "D_mm": size[1], "H_mm": size[2],
        "solids": count_solids(shape),
        "triangles": int(len(tris)),
        "load_sec": round(t1-t0, 1),
        "mesh_sec": round(t2-t1, 1),
    }
    with open(os.path.join(a.out, f"{stem}_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("[형상 요약]", json.dumps(summary, ensure_ascii=False))

if __name__ == "__main__":
    main()
