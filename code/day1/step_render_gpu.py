"""CPU vs GPU 3D 렌더링 속도 비교 — step_inspect.py가 만든 메시를 GPU로 다시 렌더링한다.

이 스크립트는 **왜 클라우드 GPU 인스턴스를 쓰는가**를 눈으로 보여주기 위한 교육용 코드입니다.
같은 삼각형 메시를 matplotlib(CPU)과 Open3D(GPU)로 각각 렌더링하고 소요 시간을 비교합니다.

필요 패키지:
    pip install cadquery-ocp matplotlib numpy open3d

사용법:
    python day1/step_render_gpu.py data/deid/LPM_OPENER_deid.stp
    python day1/step_render_gpu.py data/deid/LPM_OPENER_deid.stp --deflection 10
"""
import argparse, json, os, time
import numpy as np
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from step_inspect import load_step, bounding_box, count_solids, triangles


def render_cpu(tris, out_png, title, max_tris=250_000):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    if len(tris) > max_tris:
        idx = np.linspace(0, len(tris)-1, max_tris).astype(int)
        tris = tris[idx]
    t0 = time.time()
    fig = plt.figure(figsize=(8,7), dpi=110)
    ax = fig.add_subplot(111, projection="3d")
    n = np.cross(tris[:,1]-tris[:,0], tris[:,2]-tris[:,0])
    n /= (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
    light = np.array([0.4,-0.6,0.7]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.abs(n @ light)
    colors = np.c_[0.35*shade, 0.5*shade, 0.75*shade, np.ones_like(shade)]
    ax.add_collection3d(Poly3DCollection(tris, facecolors=colors, linewidths=0))
    allp = tris.reshape(-1,3)
    lo, hi = allp.min(0), allp.max(0)
    c, r = (lo+hi)/2, (hi-lo).max()/2
    ax.set_xlim(c[0]-r,c[0]+r); ax.set_ylim(c[1]-r,c[1]+r); ax.set_zlim(c[2]-r,c[2]+r)
    ax.view_init(elev=22, azim=-55); ax.set_axis_off()
    ax.set_title(f"[CPU — matplotlib]  {title}")
    fig.tight_layout(); fig.savefig(out_png); plt.close(fig)
    return time.time() - t0


def render_gpu(tris, out_png, title, width=880, height=770):
    import open3d as o3d
    import open3d.visualization.rendering as rendering
    t0 = time.time()
    n_tris = len(tris)
    vertices = tris.reshape(-1, 3)
    faces = np.arange(n_tris * 3).reshape(-1, 3)
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(vertices)
    mesh.triangles = o3d.utility.Vector3iVector(faces)
    mesh.compute_vertex_normals()
    mesh.paint_uniform_color([0.35, 0.50, 0.75])
    renderer = rendering.OffscreenRenderer(width, height)
    renderer.scene.set_background([1.0, 1.0, 1.0, 1.0])
    mat = rendering.MaterialRecord()
    mat.shader = "defaultLit"
    mat.base_color = [0.35, 0.50, 0.75, 1.0]
    renderer.scene.add_geometry("efem", mesh, mat)
    bbox = mesh.get_axis_aligned_bounding_box()
    center = bbox.get_center()
    extent = bbox.get_max_extent()
    eye = center + np.array([extent*0.8, -extent*1.0, extent*0.6])
    renderer.setup_camera(60.0, center, eye, [0, 0, 1])
    img = renderer.render_to_image()
    o3d.io.write_image(out_png, img)
    return time.time() - t0


def main():
    ap = argparse.ArgumentParser(description="CPU vs GPU 3D 렌더링 속도 비교")
    ap.add_argument("file", help="STEP 파일 경로")
    ap.add_argument("--out", default="data/out")
    ap.add_argument("--deflection", type=float, default=20.0,
                    help="메시 거칠기(mm). 작을수록 정밀")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.file))[0]

    print("=" * 60)
    print("  CPU vs GPU 3D 렌더링 비교")
    print("=" * 60)
    print(f"\n[1/4] STEP 파일 로드 중... ({a.file})")
    shape = load_step(a.file)
    lo, hi = bounding_box(shape)
    size = [round(h-l, 1) for l, h in zip(lo, hi)]
    print(f"       외곽 치수: {size[0]} x {size[1]} x {size[2]} mm")

    print(f"[2/4] 삼각형 메시 생성 중... (deflection={a.deflection})")
    tris = triangles(shape, a.deflection)
    print(f"       삼각형 수: {len(tris):,}개")
    title = f"{stem}  {size[0]}x{size[1]}x{size[2]} mm"

    cpu_png = os.path.join(a.out, f"{stem}_cpu.png")
    print(f"\n[3/4] CPU 렌더링 (matplotlib)...")
    cpu_sec = render_cpu(tris, cpu_png, title)
    print(f"       완료: {cpu_sec:.2f}초 → {cpu_png}")

    gpu_png = os.path.join(a.out, f"{stem}_gpu.png")
    print(f"\n[4/4] GPU 렌더링 (Open3D)...")
    try:
        gpu_sec = render_gpu(tris, gpu_png, title)
        print(f"       완료: {gpu_sec:.2f}초 → {gpu_png}")
        gpu_ok = True
    except Exception as e:
        print(f"       GPU 렌더링 실패: {e}")
        print("       → GPU 드라이버 또는 Open3D 설치를 확인하세요.")
        gpu_sec = None
        gpu_ok = False

    print("\n" + "=" * 60)
    print("  렌더링 속도 비교 결과")
    print("=" * 60)
    print(f"  삼각형 수        : {len(tris):>10,}개")
    print(f"  CPU (matplotlib) : {cpu_sec:>10.2f}초")
    if gpu_ok:
        print(f"  GPU (Open3D)     : {gpu_sec:>10.2f}초")
        speedup = cpu_sec / gpu_sec if gpu_sec > 0 else float("inf")
        print(f"  ─────────────────────────────")
        print(f"  GPU가 약 {speedup:.1f}배 빠름")
    print("=" * 60)

    result = {
        "file": os.path.basename(a.file),
        "triangles": int(len(tris)),
        "deflection": a.deflection,
        "W_mm": size[0], "D_mm": size[1], "H_mm": size[2],
        "cpu_sec": round(cpu_sec, 3),
        "gpu_sec": round(gpu_sec, 3) if gpu_ok else None,
        "speedup": round(cpu_sec/gpu_sec, 1) if gpu_ok and gpu_sec > 0 else None,
        "cpu_image": f"{stem}_cpu.png",
        "gpu_image": f"{stem}_gpu.png" if gpu_ok else None,
    }
    json_path = os.path.join(a.out, f"{stem}_render_compare.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[저장] 비교 결과 → {json_path}")

if __name__ == "__main__":
    main()
