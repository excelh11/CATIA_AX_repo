"""FFU / CATIA DESIGNER GUI - 크기를 입력하면 팬·필터·하우징 조립품을 새로 생성.

실행:  python day3/ffu_gui.py            (모의 모드: python day3/ffu_gui.py --dry-run)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.gui_base import ToolApp
from day3 import ffu

PRESET_LABELS = ["직접 입력"] + list(ffu.PRESETS)


class FfuApp(ToolApp):
    TITLE = "FFU / CATIA DESIGNER"
    SUBTITLE = "사이즈를 입력하면 팬·필터·하우징 조립품을 새로 생성합니다 (수업용 간이 계산)"

    def fields(self):
        return [("preset", "규격 프리셋", "1175x575", PRESET_LABELS),
                ("X", "X 가로 길이 (400~1800)", 1175.0, None),
                ("Y", "Y 세로 폭 (400~1400)", 575.0, None),
                ("Z", "Z 전체 높이 (250~600)", 350.0, None),
                ("t", "하우징 판 두께 (1.0~2.5)", 1.2, None),
                ("filter_depth", "필터 깊이 (60~110)", 70.0, None),
                ("grade", "필터 등급", "ULPA", list(ffu.FILTER_DP)),
                ("fans", "팬 수 (1~4)", 1.0, None),
                ("fan_dia", "팬 지름 (0=자동)", 0.0, None),
                ("velocity", "목표 면풍속 m/s (0.3~0.6)", 0.45, None)]

    def _calc(self, v):
        X, Y, fans = v["X"], v["Y"], int(v["fans"])
        if v["preset"] in ffu.PRESETS:              # 프리셋을 고르면 X/Y/팬 수를 덮어씀
            X, Y, fans = ffu.PRESETS[v["preset"]]
            self.vars["X"].set(str(X)); self.vars["Y"].set(str(Y)); self.vars["fans"].set(str(fans))
        return ffu.calc(X, Y, v["Z"], v["t"], v["filter_depth"], v["grade"], fans, v["fan_dia"], v["velocity"])

    def make_boxes(self, v):
        return ffu.to_boxes(self._calc(v))

    def info_text(self, v):
        c = self._calc(v)
        return (f"필터 면적 {c['area_m2']} m²\n풍량 {c['Q_m3h']} m³/h (팬 1대 {c['q_per_fan_m3h']})\n"
                f"팬 Ø{c['fan_dia']} x {c['fans']}대 / 정압 {c['static_Pa']} Pa\n모터 동력 추정 {c['power_W']} W")

    def run_catia(self, v):
        return ffu.build(self.catia, self._calc(v), "output")

    def extra_buttons(self):
        return [("계산서 보기", lambda: self.log(ffu.report(self._calc(self.values()))))]


if __name__ == "__main__":
    FfuApp(dry_run="--dry-run" in sys.argv).mainloop()
