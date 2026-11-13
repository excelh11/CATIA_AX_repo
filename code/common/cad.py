"""CATIA 형상 만들기 도우미 함수 모음.

모든 실습(프레임, FOUP, FFU)이 이 함수들만 조합해서 형상을 만든다.
좌표계: X=가로(폭), Y=세로(깊이), Z=높이, 단위 mm

핵심 아이디어
  1) 원점 평면(XY/YZ/ZX)을 원하는 위치만큼 띄운 평면을 만들고
  2) 그 위에 스케치(사각형, 다각형, 원)를 그린 다음
  3) Pad(돌출)로 두께/길이를 준다.
조립품의 각 부품(Part)은 조립품 원점과 같은 좌표를 쓰므로, 형상을 '제자리'에 만들면 따로 이동시킬 필요가 없다.
"""
import os
import time

# 돌출 방향별: (원점 평면 이름, 스케치 가로축 H, 세로축 V)
#   H x V = 평면의 법선(돌출 방향)이 되도록 잡았다.
AXES = {
    "Z": ("PlaneXY", (1, 0, 0), (0, 1, 0)),   # 스케치 (u,v) = (x,y), 위로(+Z) 돌출
    "X": ("PlaneYZ", (0, 1, 0), (0, 0, 1)),   # (u,v) = (y,z), +X로 돌출
    "Y": ("PlaneZX", (0, 0, 1), (1, 0, 0)),   # (u,v) = (z,x), +Y로 돌출
}


# ---------------------------------------------------------------- 문서/조립품
def new_part(catia, name):
    doc = catia.Documents.Add("Part")
    doc.Product.PartNumber = name
    return doc, doc.Part


def new_product(catia, name):
    doc = catia.Documents.Add("Product")
    doc.Product.PartNumber = name
    return doc, doc.Product


def add_part(product, name):
    """조립품 안에 새 부품(CATPart)을 추가하고 (컴포넌트, Part 객체)를 돌려준다."""
    comp = product.Products.AddNewComponent("Part", name)
    part = comp.ReferenceProduct.Parent.Part
    return comp, part


# ---------------------------------------------------------------- 스케치/돌출
def _geo_set(part):
    hbs = part.HybridBodies
    return hbs.Item(1) if hbs.Count > 0 else hbs.Add()


def _support(part, axis, offset):
    """돌출 시작면이 될 평면의 Reference. offset=0이면 원점 평면 그대로."""
    base = getattr(part.OriginElements, AXES[axis][0])
    base_ref = part.CreateReferenceFromObject(base)
    if abs(offset) < 1e-9:
        return base_ref
    plane = part.HybridShapeFactory.AddNewPlaneOffset(base_ref, float(offset), False)
    _geo_set(part).AppendHybridShape(plane)
    part.UpdateObject(plane)
    return part.CreateReferenceFromObject(plane)


def _origin(axis, offset):
    return {"Z": (0, 0, offset), "X": (offset, 0, 0), "Y": (0, offset, 0)}[axis]


def extrude(part, axis, start, length, outline=None, circles=(), name=None, pocket=False):
    """평면(axis에 수직, 위치 start)에 단면을 그리고 length만큼 돌출(Pad) 또는 제거(Pocket).

    outline : [(u,v), ...] 닫힌 다각형 꼭짓점 (마지막 점=첫 점 아님)
    circles : [(u, v, r), ...] 원. outline 안쪽이면 구멍, outline이 없으면 원기둥
    """
    _, h, v = AXES[axis]
    body = part.MainBody
    part.InWorkObject = body
    sketch = body.Sketches.Add(_support(part, axis, start))
    ox, oy, oz = _origin(axis, start)
    sketch.SetAbsoluteAxisData([ox, oy, oz, h[0], h[1], h[2], v[0], v[1], v[2]])
    f2d = sketch.OpenEdition()
    if outline:
        pts = [f2d.CreatePoint(float(a), float(b)) for a, b in outline]
        n = len(outline)
        for i in range(n):
            (a1, b1), (a2, b2) = outline[i], outline[(i + 1) % n]
            line = f2d.CreateLine(float(a1), float(b1), float(a2), float(b2))
            line.StartPoint = pts[i]
            line.EndPoint = pts[(i + 1) % n]
    for (cu, cv, r) in circles:
        f2d.CreateClosedCircle(float(cu), float(cv), float(r))
    sketch.CloseEdition()
    part.InWorkObject = body
    if pocket:
        feat = part.ShapeFactory.AddNewPocket(sketch, float(length))
    else:
        feat = part.ShapeFactory.AddNewPad(sketch, float(length))
    if name:
        feat.Name = name
    return feat


def rect(u0, v0, du, dv):
    return [(u0, v0), (u0 + du, v0), (u0 + du, v0 + dv), (u0, v0 + dv)]


def box(part, x, y, z, dx, dy, dz, name=None):
    """(x,y,z)를 한쪽 모서리로 하는 dx×dy×dz 직육면체."""
    return extrude(part, "Z", z, dz, outline=rect(x, y, dx, dy), name=name)


def cylinder(part, cx, cy, z, r, h, name=None):
    """바닥 중심 (cx,cy,z), 반지름 r, 높이 h 원기둥 (Z 방향)."""
    return extrude(part, "Z", z, h, circles=[(cx, cy, r)], name=name)


def finish(part):
    part.Update()


# ---------------------------------------------------------------- 표시/저장
def set_color(doc, obj, rgb):
    """조립품 문서에서 컴포넌트(obj) 색 바꾸기. 실패해도 형상에는 영향 없음."""
    try:
        sel = doc.Selection
        sel.Clear()
        sel.Add(obj)
        sel.VisProperties.SetRealColor(int(rgb[0]), int(rgb[1]), int(rgb[2]), 1)
        sel.Clear()
    except Exception as e:                    # 색은 부가 기능이라 경고만
        print(f"  (색 지정 건너뜀: {e})")


def make_out_dir(base, name):
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.abspath(os.path.join(base, f"{stamp}_{name}"))
    os.makedirs(path, exist_ok=True)
    return path


def save_assembly(product_doc, folder):
    """조립품과 연결된 모든 CATPart를 같은 폴더에 저장 → 폴더째 옮기면 다른 PC에서도 열림."""
    root = product_doc.Product
    saved = []
    for i in range(1, root.Products.Count + 1):
        comp = root.Products.Item(i)
        doc = comp.ReferenceProduct.Parent
        path = os.path.join(folder, f"{comp.PartNumber}.CATPart")
        doc.SaveAs(path)
        saved.append(path)
    prod_path = os.path.join(folder, f"{root.PartNumber}.CATProduct")
    product_doc.SaveAs(prod_path)
    saved.append(prod_path)
    return prod_path


def export_step(doc, path):
    doc.ExportData(os.path.abspath(path), "stp")
    return path


def capture(catia, path, iso=True):
    """현재 3D 창을 이미지(JPG)로 저장."""
    viewer = catia.ActiveWindow.ActiveViewer
    if iso:
        try:
            vp = viewer.Viewpoint3D
            vp.PutSightDirection([-1, 1, -1])      # 등각 방향에서 내려다보기
            vp.PutUpDirection([0, 0, 1])
        except Exception:
            pass
    viewer.Reframe()
    viewer.Update()
    viewer.CaptureToFile(5, os.path.abspath(path))   # 5 = catCaptureFormatJPEG
    return path


class Timer:
    def __init__(self, label):
        self.label = label

    def __enter__(self):
        self.t = time.time()
        return self

    def __exit__(self, *a):
        print(f"[시간] {self.label}: {time.time() - self.t:.1f}초")
