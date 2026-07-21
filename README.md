# 기상청 해상 기상특보 자료 수집 자동화

기상청 전자민원(minwon.kma.go.kr)의 기상현상증명에서 **해상 기상특보(태풍·풍랑)**
과거 자료를 연도별로 자동 신청하고 PDF까지 내려받는 Playwright 스크립트 모음.

한 번에 신청 가능한 용량 제한 때문에 구역을 나눠 수십 번 반복해야 하는데,
이 반복(구역 체크 → 기간 입력 → 신청 → 발급 PDF 저장)을 자동화했다.

---

## 스크립트 구성

| 파일 | 용도 | 연도당 작업 수 |
|---|---|---|
| `kma_minwon_auto.py` | 2022년 이후 (현행 구역명, 1년) | 30건 |
| `kma_minwon_auto_pre2021.py` | 2020년 이하 (옛 ~'21.07.29 구역명, 1년) | 30건 |
| `kma_minwon_auto_2021_상반기.py` | 2021년 먼바다 1.1~7.29 보완 | 12건 |
| `kma_minwon_auto_2019_상반기.py` | 2019년 동해남부·서해남부 먼바다 1.1~4.30 보완 | 4건 |
| `rename_files.py` | 내려받은 PDF 파일명 일괄 정리 (유틸) | - |

신청 스크립트 4개는 실행 방법·동작이 모두 같고, 대상 구역·기간·파일명 꼬리표만 다르다.
연도별로 어떤 스크립트를 쓰는지는 아래 "연도별 사용법" 참고.

---

## 사전 준비

```bash
# 파이썬 환경 (conda 예시)
conda create -n kma python=3.11 -y
conda activate kma
pip install playwright
```

> Playwright 전용 브라우저 설치(`playwright install`)는 **불필요**.
> 이미 열려 있는 엣지(Edge)에 접속하는 방식이라서다.

---

## 실행 방법

### 1. 엣지를 디버깅 모드로 실행 + 로그인

기존 엣지 창을 모두 닫고, 새 명령 프롬프트에서:

```bash
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="C:\edge_automation"
```

뜬 엣지 창에서 전자민원에 **PASS 로그인**을 마친다. 이 창은 작업이 끝날 때까지
닫지도 조작하지도 않는다. (로그인은 세션당 1회만 사람이 하면 됨)

### 2. 스크립트 설정 (파일 상단)

| 설정 | 의미 |
|---|---|
| `MODE` | `"dump"` / `"dry"` / `"run"` (아래 참조) |
| `YEARS` | 처리할 연도. 예: `[2023]` |
| `DOWNLOAD_ROOT` | PDF 저장 루트 폴더 |
| `BOARD_URL` | 민원보관함 주소 (나의민원 > 민원보관함 진입 후 주소창 URL) |
| `DELAY_SEC` | 신청 간 대기(기본 4초, 줄이지 말 것) |

**MODE 3단계**
- `dump` : 사이트의 구역 체크박스 이름을 출력만 함 (ZONE_GROUPS 검수용)
- `dry`  : 신청 확인 페이지까지 리허설, 실제 신청·다운로드 안 함
- `run`  : 실제 신청 + 신청 직후 PDF 자동 저장

### 3. 실행

```bash
conda activate kma
cd /d C:\kma_auto
python kma_minwon_auto.py
```

**처음 돌리는 연도라면** `dump`(필요 시) → `dry` 전체 통과 확인 →
1건만 `run` 테스트 → 전체 `run` 순서를 권장.

---

## 연도별 사용법

먼바다 구역명이 아래 날짜에 개편되어, **개편일이 걸친 연도**는 기간을 쪼개
두 번(개편 전/후) 신청해야 1년이 완성된다. 앞바다는 개편 영향이 없다.

| 개편일 |크
https://app.notion.com/p/3a44729efa2a8001afa2df3a32e4526c?source=copy_link
