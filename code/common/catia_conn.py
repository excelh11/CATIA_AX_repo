"""CATIA V5 연결 모듈 (모든 실습 스크립트가 공통으로 사용).

- Windows + CATIA V5 실행 중  → pywin32(COM)로 실제 CATIA에 연결
- 그 외(리눅스 클라우드, CATIA 없는 PC) 또는 --dry-run → '모의(Mock) CATIA'로 연결
  모의 모드에서는 CATIA에 보낼 명령을 화면/로그로만 출력하므로 코드 흐름을 미리 점검할 수 있다.

사용 예:
    from common.catia_conn import get_catia
    catia = get_catia()                  # 자동 판단
    catia = get_catia(dry_run=True)      # 강제로 모의 모드
"""
import os
import sys

LOG = []                       # 모의 모드에서 호출된 명령 기록


def log(msg):
    LOG.append(msg)
    if os.environ.get("CATIA_MOCK_VERBOSE") == "1":
        print("  [mock]", msg)


class Mock:
    """어떤 속성/메서드를 불러도 에러 없이 Mock을 돌려주는 가짜 CATIA 객체."""

    _counter = 0

    def __init__(self, path="CATIA"):
        object.__setattr__(self, "_path", path)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name == "Count":
            return 0
        if name in ("Name", "PartNumber", "FullName", "Path"):
            return f"{self._path}.{name}"
        return Mock(f"{self._path}.{name}")

    def __setattr__(self, name, value):
        log(f"{self._path}.{name} = {value!r}")

    def __call__(self, *args, **kwargs):
        Mock._counter += 1
        short = ", ".join(repr(a) if not isinstance(a, Mock) else a._path.split(".")[-1] for a in args)
        log(f"{self._path}({short})")
        return Mock(f"{self._path.split('.')[-1]}#{Mock._counter}")

    def __iter__(self):
        return iter([])

    def __bool__(self):
        return True

    def __repr__(self):
        return f"<Mock {self._path}>"


def is_windows():
    return sys.platform.startswith("win")


def get_catia(dry_run=False, visible=True):
    """CATIA Application 객체를 돌려준다. 실패하면 이유를 알려주는 RuntimeError."""
    if dry_run or os.environ.get("CATIA_DRY_RUN") == "1" or not is_windows():
        print("[연결] 모의(Mock) CATIA 모드 - 실제 CATIA는 움직이지 않습니다.")
        return Mock("CATIA")
    try:
        import win32com.client            # pip install pywin32
    except ImportError as e:
        raise RuntimeError("pywin32가 없습니다.  명령 프롬프트에서:  pip install pywin32") from e
    try:
        catia = win32com.client.GetActiveObject("CATIA.Application")   # 이미 켜진 CATIA에 붙기
    except Exception:
        try:
            catia = win32com.client.Dispatch("CATIA.Application")      # 없으면 새로 실행
        except Exception as e:
            raise RuntimeError("CATIA V5에 연결할 수 없습니다. CATIA를 먼저 실행했는지 확인하세요.") from e
    catia.Visible = visible
    catia.DisplayFileAlerts = False      # 저장 시 '덮어쓸까요?' 같은 팝업 끄기
    print(f"[연결] CATIA 연결 성공: {catia.Name}")
    return catia


def is_mock(obj):
    return isinstance(obj, Mock)
