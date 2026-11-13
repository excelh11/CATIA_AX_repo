# AX CATIA 자동화 캠프 — 완성 코드 (Step 01 ~ 24)
> "클라우드에서 장비 CAD(STEP)를 분석하고, 그 치수로 Python이 CATIA V5 형상과 도면을 자동으로 만드는 설계 자동화" <br>
> ⚠️ 이 저장소에는 CAD 파일(`*.stp`), 비식별 대응표(`*_mapping.csv`), SSH 키(`*.pem`)가 **들어 있지 않습니다.** 강사에게 따로 받으세요.

---

## 0. 준비물 (설치로 해결되지 않는 것)

| 준비물 | 어디서 |
|---|---|
| Windows PC + **CATIA V5** (라이선스) | 강의장 PC |
| **엘리스 클라우드** 계정 · 실행 중인 인스턴스 · `.pem` 비밀키 | 엘리스 대시보드 |
| `LPM_OPENER.stp` (원본 STEP) | 강사 |

## 1. 내 PC 설치 (약 10분)

1. **Python 3.12** 설치 — 설치 첫 화면에서 **`Add python.exe to PATH` 반드시 체크**
2. **Git** 설치 (https://git-scm.com) — 기본값으로 계속 Next
3. **CMD** (PowerShell 아님) 를 열고:

```bat
git clone <이 저장소 주소> C:\CATIA_AX
cd C:\CATIA_AX\code
pip install -r requirements_local.txt
python check_env.py
```

## 2. STEP 파일 비식별화

`LPM_OPENER.stp` 를 **`C:\CATIA_AX\code\data\raw\`** 에 넣습니다. (`C:\CATIA_AX\data\` 가 아닙니다!)

```bat
cd C:\CATIA_AX\code
python day1/step_deid.py data/raw/LPM_OPENER.stp
```

✅ `code\data\deid\` 에 `LPM_OPENER_deid.stp` 와 `LPM_OPENER_mapping.csv` 가 생기면 성공.

## 3. 엘리스 클라우드 준비 (JupyterLab 터미널)

```bash
git clone <이 저장소 주소> ~/CATIA_AX
ln -s ~/CATIA_AX/code ~/code
sudo apt-get update && sudo apt-get install -y libosmesa6 libgl1 libgomp1 libglfw3 libegl1 libusb-1.0-0 libvulkan1 mesa-vulkan-drivers
cd ~/code && pip install -r requirements_cloud.txt
```


## 4. SSH 연결 확인 (내 PC · CMD)

엘리스 `[연결] → [빠른 연결]` 에서 비밀키를 받고, 이름을 **`my-elice.pem`** 으로 바꿔 `다운로드` 폴더에 둡니다.

```bat
icacls "%USERPROFILE%\Downloads\my-elice.pem" /inheritance:r
icacls "%USERPROFILE%\Downloads\my-elice.pem" /grant:r "%USERNAME%:(R)"
ssh -i "%USERPROFILE%\Downloads\my-elice.pem" -o UserKnownHostsFile="%USERPROFILE%\Downloads\known_hosts" elicer@<호스트> -p <포트>
```

처음 한 번 `yes` → 엘리스 프롬프트가 보이면 `exit`.
(빠른 연결 화면의 명령을 그대로 복사하면 키 파일을 못 찾습니다. 위처럼 경로를 바꾸세요.)

### 접속 정보 `.env` 만들기

호스트 · 포트 · PEM 경로는 코드에 적지 않고 `C:\CATIA_AX\.env` 에만 둡니다. (`.env` 는 GitHub 에 올라가지 않습니다)

```bat
cd C:\CATIA_AX
copy .env.example .env
code .env
```

`ELICE_HOST`, `ELICE_PORT` 를 빠른 연결 화면의 값으로 채우고 저장합니다.

```ini
ELICE_HOST=<빠른 연결의 @ 뒤 주소>
ELICE_PORT=<빠른 연결의 -p 뒤 숫자>
ELICE_USER=elicer
ELICE_PEM=%USERPROFILE%\Downloads\my-elice.pem
STEP_FILE=code/data/deid/LPM_OPENER_deid.stp
```

## 5. CATIA 준비 (CATIA V5 를 켠 상태에서)

```bat
cd C:\CATIA_AX
python scripts\build_template.py
```

✅ `TEMPLATE: C:\CATIA_AX\templates\CampBlock.CATPart` / `HEIGHT_MM: 30.0`

## 6. 전체 자동화 실행

```bat
cd C:\CATIA_AX
python scripts\run_full_gui.py
```

입력칸이 `.env` 값으로 채워져 있는지 확인하고 **[자동화 실행]**.
(CMD 로 실행하려면 `python scripts\run_full.py --height 60` — 접속 정보는 역시 `.env` 에서 읽습니다)

### ✅ 합격 기준

- 로그 끝에 `DONE` / `End-to-End 파이프라인 완료!`
- `C:\CATIA_AX\outputs\<최신 폴더>\report.json` 의 `"status": "full_pipeline_completed"`
- 같은 폴더에 `EFEM_CELL` 조립품과 도면(PDF)

---

## 폴더 구조

```text
C:\CATIA_AX\
├─ code\                 내 PC 실습 코드 (엘리스에서는 ~/code 로 연결)
│  ├─ common\            CATIA 연결 · 형상 도구 · 미리보기 · GUI 틀
│  ├─ day1\ day2\ day3\  Step 별 실습
│  ├─ data\raw\          ← 원본 STEP 을 여기에
│  ├─ make_request.py    엘리스용 요청서 생성기 (run_full.py 가 원격 실행)
│  └─ requirements_*.txt
├─ scripts\              템플릿 · 요청서 · 전체 자동화 (code\ 와 별개)
├─ templates\            build_template.py 가 CampBlock.CATPart 를 만드는 곳
├─ data\                 request.json 이 저장되는 곳
├─ .env.example          접속 정보 양식 (복사해서 .env 로)
└─ .env                  ← 내 접속 정보 (직접 만듦 · GitHub 에 안 올라감)
```

## 막혔을 때

| 증상 | 확인 |
|---|---|
| `step_deid.py` 가 아무 말 없이 끝남 | STEP 파일이 `code\data\raw\` 에 있는지 |
| `ssh` 가 비밀번호를 물음 | `-i` 뒤 경로가 `%USERPROFILE%\Downloads\my-elice.pem` 인지, CMD 에서 실행했는지 |
| `Failed to add the host to the list of known hosts` | `-o UserKnownHostsFile=...known_hosts` 를 붙였는지 |
| `ValueError: Y=... 허용 범위` | 엘리스의 `~/code` 가 이 저장소 최신 코드인지 (`cd ~/CATIA_AX && git pull`) |
| `Run build_template.py first` | 5번을 먼저 실행 |
| GUI 호스트 · 포트 칸이 비어 있음 / `접속 정보가 없습니다` | `C:\CATIA_AX\.env` 가 있는지, `ELICE_HOST` · `ELICE_PORT` 를 채웠는지 |
