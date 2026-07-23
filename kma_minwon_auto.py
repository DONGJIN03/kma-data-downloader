# -*- coding: utf-8 -*-
"""
기상청 전자민원 - 기상특보(해상) 신청 + PDF 자동 다운로드 [기본형]
==============================================================
■ 이 파일은 "개편이 걸치지 않은 모든 연도"에 사용한다.
  해당 연도: 2022~현재 / 2020 / 2015~2018 / 2013 이하 등
  (기간은 항상 1.1~12.31 1년 통짜, 파일명 꼬리표 없음)

■ 개편일이 한 해에 걸치는 연도(2021·2019·2014)는 이 파일로 하지 말 것.
  그 연도의 "먼바다"는 kma_minwon_auto_split.py(개편연도형)로 반기 보완해야 한다.
  자세한 사용법·연도별 ZONE_GROUPS 블록은 README.md 참고.

■ 연도를 바꾸려면: 아래 설정의 YEARS 와 ZONE_GROUPS 두 개만 교체하면 된다.
  (README.md의 연도별 블록을 복사해 ZONE_GROUPS 자리에 붙여넣기)
==============================================================
사전 준비:
  1) pip install playwright
  2) 엣지 디버깅 모드 실행 (cmd):
     "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --remote-debugging-port=9222 --user-data-dir="C:\\edge_automation"
  3) 그 창에서 전자민원 PASS 로그인
  4) python kma_minwon_auto.py

MODE:
  "dump" : 구역 이름 목록만 출력 (검수용)
  "dry"  : 확인 페이지까지 리허설, 신청/다운로드 안 함
  "run"  : 신청 + 신청 직후 PDF 자동 다운로드까지 수행

run 모드 동작 (1건당):
  신청 전 보관함 맨위 신청번호 기억 -> 신청 -> 보관함에 새 번호 뜨면
  그 행의 발급 파라미터로 PDF 요청 -> 폴더/파일명 규칙대로 저장
  저장 규칙: 다운로드루트\\연도\\해역\\구분\\기상특보(해상)_연도_특보명.pdf
"""

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import csv
import os
import re
import time
from datetime import datetime

# ==================== 설정 ====================
MODE = "run"                     # "dump" / "dry" / "run"
YEARS = [2024]                   # 1년치씩 진행
DELAY_SEC = 4                    # 신청 간 대기
LOG_FILE = "신청로그.csv"
DOWNLOAD_ROOT = r"C:\kma_auto\다운로드"   # PDF 저장 루트 폴더

BASE = "https://minwon.kma.go.kr"
REQ_URL = f"{BASE}/cr/mtProofReq.do"
CDP_URL = "http://localhost:9222"

# 민원보관함 주소: 엣지에서 나의민원 > 민원보관함 들어간 뒤 주소창 URL을 복사해 붙여넣기.
# 비워두면("") 상단 메뉴 '나의민원' 클릭으로 이동 시도.
BOARD_URL = "https://minwon.kma.go.kr/cl/civilCab.do"

WARNINGS = {"T": "태풍", "V": "풍랑"}                     # 로그용 짧은 이름
WARN_FULL = {"T": "태풍주의보", "V": "풍랑주의보"}          # 파일명용

# 구역 구분: (해역, 구분) -> 체크할 label 텍스트 (dump 결과와 동일해야 함)
ZONE_GROUPS = {
    ("동해중부", "앞바다"): ["동해중부앞바다", "강원북부앞바다", "강원중부앞바다",
                          "강원남부앞바다"],
    ("동해중부", "먼바다"): ["동해중부안쪽먼바다", "동해중부바깥먼바다"],

    ("동해남부", "앞바다"): ["동해남부앞바다", "울산앞바다", "경북남부앞바다",
                          "경북북부앞바다"],
    ("동해남부", "먼바다"): ["동해남부북쪽안쪽먼바다", "동해남부북쪽바깥먼바다",
                          "동해남부남쪽안쪽먼바다", "동해남부남쪽바깥먼바다"],

    ("서해중부", "앞바다"): ["서해중부앞바다", "인천·경기북부앞바다", "인천·경기남부앞바다",
                          "충남북부앞바다", "충남남부앞바다"],
    ("서해중부", "먼바다"): ["서해중부안쪽먼바다", "서해중부바깥먼바다"],

    ("서해남부", "앞바다(1)"): ["서해남부앞바다", "전북북부앞바다", "전북남부앞바다"],
    ("서해남부", "앞바다(2)"): ["전남북부서해앞바다", "전남중부서해앞바다", "전남남부서해앞바다"],
    ("서해남부", "먼바다"): ["서해남부북쪽안쪽먼바다", "서해남부북쪽바깥먼바다",
                          "서해남부남쪽안쪽먼바다", "서해남부남쪽바깥먼바다"],

    ("남해동부", "앞바다"): ["남해동부앞바다", "부산앞바다", "경남서부남해앞바다",
                          "경남중부남해앞바다", "거제시동부앞바다"],
    ("남해동부", "먼바다"): ["남해동부안쪽먼바다", "남해동부바깥먼바다"],

    ("남해서부", "앞바다"): ["남해서부앞바다", "전남서부남해앞바다", "전남동부남해앞바다"],
    ("남해서부", "먼바다"): ["남해서부서쪽먼바다", "남해서부동쪽먼바다"],

    ("제주도", "앞바다"): ["제주도앞바다", "제주도북부앞바다", "제주도동부앞바다",
                        "제주도남부앞바다", "제주도서부앞바다"],
    ("제주도", "먼바다"): ["제주도남서쪽안쪽먼바다", "제주도남동쪽안쪽먼바다",
                        "제주도남쪽바깥먼바다"],
}
# ==============================================


def log_row(row):
    def _write(path):
        new = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["신청시각", "연도", "해역", "구분", "특보", "구역수",
                            "신청상태", "다운로드", "비고"])
            w.writerow(row)
    try:
        _write(LOG_FILE)
    except PermissionError:
        # 엑셀 등으로 열어둔 경우: 대체 파일에 기록하고 계속 진행
        alt = LOG_FILE.replace(".csv", "_잠김대체.csv")
        print(f"   [경고] {LOG_FILE} 잠김 -> {alt} 에 기록 (엑셀 닫기 권장)")
        try:
            _write(alt)
        except PermissionError:
            print("   [경고] 로그 기록 실패, 계속 진행:", row)


# ---------------- 신청 페이지 ----------------

def open_haesang(page):
    """민원신청 페이지: 학술/연구 체크 + 기상특보>해상 선택"""
    page.goto(REQ_URL, wait_until="domcontentloaded")
    page.wait_for_selector("#useCode13", timeout=20000)
    page.check("#useCode13")

    page.wait_for_selector("#jstree_bbox", timeout=20000)
    if not page.locator("#A030002").is_visible():
        page.click("#A030 > a")
        page.wait_for_selector("#A030002", state="visible", timeout=10000)
    page.click("#A030002 > a")
    page.wait_for_selector('#stn_ibox label:text-is("동해남부앞바다")', timeout=20000)
    time.sleep(1.5)   # 구역 목록 ajax 재렌더링 안정화 대기


def dump_zone_names(page):
    open_haesang(page)
    names = page.eval_on_selector_all(
        "#stn_ibox label",
        "els => els.map(e => e.textContent.trim()).filter(t => t)")
    print("\n===== 구역 목록 (%d개) =====" % len(names))
    for n in names:
        print(repr(n))
    print("=" * 30)


def check_zone(page, name):
    input_id = page.evaluate(
        """(nm) => {
            const labels = document.querySelectorAll('#stn_bbox label');
            for (const l of labels) {
                if (l.textContent.trim() === nm) return l.getAttribute('for');
            }
            return null;
        }""", name)
    if not input_id:
        raise RuntimeError(f"구역을 찾을 수 없음: {name}")
    changed = page.evaluate(
        """(id) => {
            const cb = document.getElementById(id);
            if (!cb) return 'notfound';
            if (!cb.checked) { cb.click(); return 'clicked'; }
            return 'already';
        }""", input_id)
    if changed == 'notfound':
        raise RuntimeError(f"체크박스 없음: {name} (id={input_id})")


def run_apply(page, year, wcode, zones, dry):
    """한 건 신청. 반환 (상태, 비고)"""
    open_haesang(page)

    # 구역 + 특보종류 체크: 목록 재렌더링으로 체크가 풀릴 수 있어
    # '체크 -> 실제 유지 확인 -> 풀렸으면 재체크'를 최대 4회 반복
    bad = None
    for attempt in range(4):
        for z in zones:
            check_zone(page, z)
        page.evaluate(
            """(id) => { const cb = document.getElementById(id);
                         if (cb && !cb.checked) cb.click(); }""", wcode)
        time.sleep(0.5)
        bad = page.evaluate(
            """(v) => {
                const bad = [];
                const map = {};
                for (const l of document.querySelectorAll('#stn_bbox label')) {
                    map[l.textContent.trim()] = l.getAttribute('for');
                }
                for (const nm of v.names) {
                    const id = map[nm];
                    const cb = id ? document.getElementById(id) : null;
                    if (!cb || !cb.checked) bad.push(nm);
                }
                const w = document.getElementById(v.w);
                if (!w || !w.checked) bad.push('특보종류');
                return bad;
            }""", {"names": zones, "w": wcode})
        if not bad:
            break
        time.sleep(1.0)
    if bad:
        return "실패", f"체크가 유지되지 않음: {bad}"

    page.evaluate(
        """(v) => {
            const s = document.getElementById('day-stdate');
            const e = document.getElementById('day-eddate');
            if (!s || !e) return 'notfound';
            s.removeAttribute('readonly'); e.removeAttribute('readonly');
            s.value = v.start; e.value = v.end;
            for (const el of [s, e]) {
                el.dispatchEvent(new Event('change', {bubbles:true}));
                el.dispatchEvent(new Event('keyup', {bubbles:true}));
                el.dispatchEvent(new Event('blur', {bubbles:true}));
            }
            return 'ok';
        }""", {"start": f"{year}0101", "end": f"{year}1231"})

    page.click('a.btn_next[title="다음"]')

    try:
        page.wait_for_selector("#btnProc", timeout=20000)
    except PWTimeout:
        return "실패", "확인페이지 진입 실패(용량제한 의심)"

    body = page.inner_text("#contents")
    problems = []
    if WARNINGS[wcode] not in body:
        problems.append(f"특보 '{WARNINGS[wcode]}' 미확인")
    if str(year) not in body:
        problems.append(f"연도 {year} 미확인")
    for z in zones:
        zb = z.split("(~")[0]          # 옛 구역명이면 (~'YY..) 꼬리표 떼고 대조
        if zb not in body.replace(" ", ""):
            problems.append(f"구역 '{zb}' 미확인")
    if problems:
        page.click("#btnBack")
        return "검증실패", "; ".join(problems)

    if dry:
        page.click("#btnBack")
        return "리허설OK", "검증 통과 (신청 안 함)"

    page.click("#btnProc")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(1)
    return "신청완료", ""


# ---------------- 민원보관함 / 다운로드 ----------------

def goto_board(page):
    if BOARD_URL:
        page.goto(BOARD_URL, wait_until="domcontentloaded")
    else:
        page.click('a:has-text("나의민원")')
        page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector("table.tbl_board tbody tr", timeout=20000)


def top_row(page):
    """보관함 1페이지 맨 위 행의 (신청번호, 발급 onclick) 반환"""
    goto_board(page)
    row = page.locator("table.tbl_board tbody tr").first
    no = row.locator("td").nth(0).inner_text().strip()
    a = row.locator("td.last a").first
    onclick = a.get_attribute("onclick") or ""
    return no, onclick


def pdf_url_from_onclick(onclick):
    if "retrieveAppDownload" not in (onclick or ""):
        return None
    # 따옴표 안 값들을 전부 추출 (공백/줄바꿈에 관대)
    params = re.findall(r"'([^']*)'", onclick)
    if len(params) < 6:
        return None
    fee, knd, estyl, dmn, _dt, minno = params[:6]
    return (f"{BASE}/cl/civilPdfFileview.pop"
            f"?feeNo={fee}&minKnd={knd}&estylNo={estyl}&minDmnNo={dmn}&minNo={minno}")


def download_pdf(page, url, save_path):
    """로그인 세션 쿠키로 PDF 요청해 저장. 반환 (성공여부, 비고)"""
    resp = page.context.request.get(url)
    body = resp.body()
    if not body[:5].startswith(b"%PDF"):
        return False, f"PDF 응답 아님 (status {resp.status})"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(body)
    return True, f"{len(body) // 1024}KB"


def fetch_new_pdf(page, prev_no, year, sea, part, wcode):
    """신청 직후: 보관함 맨위에 새 건 뜨길 기다렸다가 PDF 저장"""
    onclick = None
    for _ in range(15):                 # 최대 약 30초 대기
        time.sleep(2)
        no, oc = top_row(page)
        if no and no != prev_no:
            onclick = oc
            break
    if not onclick:
        return "실패", "보관함에 새 신청건이 안 보임 (수동 확인 필요)"

    url = pdf_url_from_onclick(onclick)
    if not url:
        print(f"\n   [디버그] onclick = {onclick!r}")
        return "실패", "발급 파라미터 해석 실패 (위 디버그 출력 확인)"

    fname = f"기상특보(해상)_{year}_{sea}_{part}_{WARN_FULL[wcode]}.pdf"
    # 폴더명은 (1)(2) 등 괄호 꼬리를 떼어 통일(예: 앞바다(1)->앞바다),
    # 파일명(fname)에는 part 원본을 그대로 써서 (1)(2) 구분 유지
    folder_part = re.sub(r'\(.*?\)$', '', part)
    save_path = os.path.join(DOWNLOAD_ROOT, str(year), sea, folder_part, fname)
    ok, note = download_pdf(page, url, save_path)
    if ok:
        return "저장완료", f"{save_path} ({note})"
    return "실패", note


# ---------------- 메인 ----------------

def main():
    jobs = [(y, sea, part, w)
            for y in YEARS
            for (sea, part) in ZONE_GROUPS
            for w in WARNINGS]

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        page.on("dialog", lambda d: (print("  [팝업]", d.message), d.accept()))

        if MODE == "dump":
            dump_zone_names(page)
            return

        dry = (MODE == "dry")
        if not dry and not BOARD_URL:
            print("[중단] BOARD_URL이 비어 있습니다.")
            print("  엣지에서 나의민원 > 민원보관함 화면의 주소창 URL을 복사해서")
            print('  코드 상단 BOARD_URL = "" 안에 붙여넣고 저장 후 다시 실행하세요.')
            return
        print(f"총 {len(jobs)}건 / 모드: {MODE}")
        if not dry:
            print(f"PDF 저장 위치: {DOWNLOAD_ROOT}\n")

        for i, (year, sea, part, wcode) in enumerate(jobs, 1):
            zones = ZONE_GROUPS[(sea, part)]
            tag = f"{year}_{sea}_{part}_{WARNINGS[wcode]}"
            print(f"[{i}/{len(jobs)}] {tag}")

            dl_status, dl_note = "-", ""
            try:
                if not dry:
                    prev_no, _ = top_row(page)   # 신청 전 맨위 신청번호 기억
                print("   신청 ... ", end="", flush=True)
                status, note = run_apply(page, year, wcode, zones, dry)
                print(status, note)

                if status == "신청완료":
                    print("   다운로드 ... ", end="", flush=True)
                    dl_status, dl_note = fetch_new_pdf(
                        page, prev_no, year, sea, part, wcode)
                    print(dl_status, dl_note)
            except Exception as e:
                status, note = "오류", str(e)[:150]
                print("   오류:", note)

            log_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     year, sea, part, WARNINGS[wcode], len(zones),
                     status, dl_status, (note + " " + dl_note).strip()])
            time.sleep(DELAY_SEC)

        print(f"\n완료. 결과는 {LOG_FILE} 확인.")


if __name__ == "__main__":
    main()