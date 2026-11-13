"""FRAME / 3030 GUI - 디자인과 치수를 고르고 버튼으로 CATIA 조립품 생성.

실행:  python day2/frame_gui.py            (모의 모드: python day2/frame_gui.py --dry-run)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.gui_base import ToolApp
from day2 import frame3030 as fr

LABELS = [f"{k} - {v}" for k, v in fr.DESIGNS.items()]


class FrameApp(ToolApp):
    TITLE = "FRAME / 3030"
    SUBTITLE = "디자인 선택 · 치수 입력 · CATIA 조립품 생성 (프로파일 1개 = CATPart 1개)"

    def fields(self):
        return [("design", "디자인", LABELS[0], LABELS),
                ("W", "가로 W (mm)", 600.0, None),
                ("D", "깊이 D (mm)", 500.0, None),
                ("H", "높이 H (mm)", 600.0, None),
                ("panel", "상판", "없음", ["없음", "있음"])]

    def _parse(self, v):
        return v["design"].split(" - ")[0], v["W"], v["D"], v["H"], v["panel"] == "있음"

    def make_boxes(self, v):
        d, W, D, H, panel = self._parse(v)
        if min(W, D, H) < 4 * fr.P:
            raise ValueError(f"각 치수는 {4*fr.P:.0f}mm 이상이어야 합니다")
        return fr.to_boxes(fr.members(d, W, D, H), panel, W, D, H)

    def info_text(self, v):
        d, W, D, H, panel = self._parse(v)
        mem = fr.members(d, W, D, H)
        cuts = ", ".join(f"{L:.0f}mm×{n}" for L, n in fr.cut_list(mem))
        warn = "\n".join("[!] " + m for m in fr.check(d, W, D, H))
        return f"프로파일 {len(mem)}개 / 총 {sum(m[3] for m in mem)/1000:.2f} m\n절단: {cuts}\n{warn}"

    def run_catia(self, v):
        d, W, D, H, panel = self._parse(v)
        out, _ = fr.build(self.catia, d, W, D, H, "output", panel)
        return out


if __name__ == "__main__":
    FrameApp(dry_run="--dry-run" in sys.argv).mainloop()
