"""FOUP Assembly Python Studio - 크기/웨이퍼 수를 고르고 CATIA 조립품 + 검토 보고서 생성.

실행:  python day2/foup_gui.py            (모의 모드: python day2/foup_gui.py --dry-run)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.gui_base import ToolApp
from day2 import foup


class FoupApp(ToolApp):
    TITLE = "FOUP Assembly Python Studio"
    SUBTITLE = "200 / 300 / 450 mm · 25슬롯 · 치수 점검 및 규격 검토 보고서 (수업용 단순화 모델)"

    def fields(self):
        return [("size", "FOUP 크기 (웨이퍼 지름 mm)", "300", ["200", "300", "450"]),
                ("wafers", "포함할 웨이퍼 개수 (0~25)", 25.0, None)]

    def _g(self, v):
        n = int(v["wafers"])
        if n != v["wafers"]:
            raise ValueError("웨이퍼 개수는 정수로 넣으세요")
        return foup.dims(int(v["size"]), n)

    def make_boxes(self, v):
        return foup.to_boxes(self._g(v))

    def info_text(self, v):
        g = self._g(v)
        return (f"슬롯 수 25개 / 간격 {g['pitch']} mm\n웨이퍼 두께 {g['t']} mm / 장착 {g['wafers']}장\n"
                f"외곽 {g['W']:.0f} x {g['D']:.0f} x {g['H']:.0f} mm\n"
                "0개: 웨이퍼 제외 / 1~25개: 아래부터 배치\nSEMI 적합 판정 미완료 / 수업용 모델")

    def run_catia(self, v):
        g = self._g(v)
        return foup.build_one(self.catia, g["size"], g["wafers"], "output")

    def extra_buttons(self):
        return [("3종(200/300/450) 배치", self.build_all), ("검토 보고서 보기", self.show_report)]

    def build_all(self):
        if self.catia is None:
            self.connect()
        try:
            out = foup.build_all(self.catia, int(self.values()["wafers"]), "output")
            self.log(f"[완료] 3종 배치: {out}")
        except Exception as e:
            self.log(f"[오류] {e}")

    def show_report(self):
        try:
            self.log(foup.report(self._g(self.values())))
        except Exception as e:
            self.log(f"[확인 필요] {e}")


if __name__ == "__main__":
    FoupApp(dry_run="--dry-run" in sys.argv).mainloop()
