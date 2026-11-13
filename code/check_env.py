"""설치 점검 스크립트 - 수업 시작 전에 모든 PC에서 한 번 실행.

    python check_env.py            # 로컬 PC(Windows + CATIA)
    python check_env.py --cloud    # 엘리스 클라우드 서버
"""
import importlib
import platform
import sys


def check(mod, hint):
    try:
        m = importlib.import_module(mod)
        print(f"  [OK]  {mod:<12} {getattr(m, '__version__', '')}")
        return True
    except Exception as e:
        print(f"  [X]   {mod:<12} → {hint}   ({e.__class__.__name__})")
        return False


def main():
    cloud = "--cloud" in sys.argv
    print(f"Python {sys.version.split()[0]} / {platform.system()} {platform.release()}")
    if sys.version_info < (3, 9):
        print("  [X]   Python 3.9 이상이 필요합니다")
    ok = check("numpy", "pip install numpy") & check("matplotlib", "pip install matplotlib")
    if cloud:
        ok &= check("OCP", "pip install cadquery-ocp")
        import shutil, subprocess
        if shutil.which("nvidia-smi"):
            out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                 capture_output=True, text=True).stdout.strip()
            print(f"  [OK]  GPU          {out}")
        else:
            print("  [-]   GPU 정보 없음 (이번 실습은 GPU 없이도 동작)")
    else:
        try:
            import tkinter
            print(f"  [OK]  tkinter      {tkinter.TkVersion}")
        except Exception:
            print("  [X]   tkinter → Python 설치 시 'tcl/tk and IDLE' 체크 후 재설치"); ok = False
        if platform.system() != "Windows":
            print("  [-]   Windows가 아니므로 CATIA 연결은 모의(--dry-run) 모드만 가능")
        elif check("win32com.client", "pip install pywin32"):
            try:
                import win32com.client
                catia = win32com.client.GetActiveObject("CATIA.Application")
                print(f"  [OK]  CATIA 연결   {catia.Name} / 열린 문서 {catia.Documents.Count}개")
                doc = catia.Documents.Add("Part")
                doc.Close()
                print("  [OK]  새 Part 만들고 닫기 성공")
            except Exception as e:
                print(f"  [X]   CATIA 연결 실패 → CATIA V5를 먼저 실행하세요 ({e})"); ok = False
        else:
            ok = False
    print("\n결과:", "모두 정상" if ok else "위의 [X] 항목을 해결하세요")


if __name__ == "__main__":
    main()
