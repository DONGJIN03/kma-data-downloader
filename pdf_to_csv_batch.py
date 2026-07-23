# -*- coding: utf-8 -*-
"""
기상특보(해상) PDF -> 연도별 CSV 일괄 변환
==============================================================
입력:  C:\\kma_auto\\다운로드\\{연도}\\{해역}\\{바다}\\
       기상특보(해상)_{연도}_{해역}_{바다}_{특보}.pdf
출력:  C:\\kma_auto\\CSV변환\\기상특보(해상)_{연도}.csv
       (한 연도의 모든 PDF를 이어붙여 한 파일로)

칼럼:
  기상종류 / 연도 / 해역 / 바다 / 세부지역(구역) / 특보종류 /
  발표_발표 / 발표_발효 / 변경해제_발표 / 변경해제_발효 / 변경해제_내용

- 해역·바다·연도는 폴더 경로에서 읽는다 (rename 규칙 폴더 구조 전제).
- 세부지역(구역)은 PDF 표의 구역명에서 '~전해상' 접두어를 떼고 사용.
- 기간 꼬리표(_0101-0729 등)가 붙은 개편 연도 상·하반기 파일은 건너뛴다.

사전 준비:
  pip install pdfplumber

사용법:
  1) DOWNLOAD_ROOT / OUT_DIR 경로 확인
  2) 필요하면 ONLY_YEARS 로 특정 연도만 지정 (비우면 전체)
  3) python pdf_to_csv_batch.py
"""

import os
import re
import csv
import pdfplumber
from collections import defaultdict

# ==================== 설정 ====================
DOWNLOAD_ROOT = r"C:\kma_auto\다운로드"
OUT_DIR       = r"C:\kma_auto\CSV변환"
ONLY_YEARS = []          # 예: [2023, 2024]. 비우면 전체 연도
SKIP_SPLIT_YEARS = False  # 기간 꼬리표(_0101-... 등) 붙은 개편연도 파일 건너뛰기
# ==============================================

HEADER = ["기상종류", "연도", "해역", "바다", "세부지역(구역)", "특보종류",
          "발표_발표", "발표_발효", "변경해제_발표", "변경해제_발효", "변경해제_내용"]

# 파일명: 기상특보(해상)_{연도}_{해역}_{바다}_{특보}[_기간꼬리표].pdf
FNAME_RE = re.compile(
    r"^기상특보\(해상\)_(\d{4})_(.+?)_(.+?)_(태풍주의보|풍랑주의보)(_\d{4}-\d{4})?\.pdf$")

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def clean_zone(raw, sea=None):
    """PDF 표의 구역 셀에서 상위(해역) 접두어를 떼고 실제 구역명만 남긴다.

    먼바다: '동해중부전해상 동해\n중부바깥먼바다' -> '동해중부바깥먼바다'
    앞바다: '남해동부앞바다 거제시동부앞바다'      -> '거제시동부앞바다'
    단, 상위구역 자체 행('남해동부앞바다')은 그대로 둔다.
    """
    if not raw:
        return None
    z = raw.replace("\n", "").replace(" ", "")

    # 1) '~전해상' 접두어 제거 (먼바다)
    if "전해상" in z:
        z = z.split("전해상")[-1]

    # 2) '{해역}앞바다' 접두어 제거 (앞바다)
    #    예: 남해동부앞바다거제시동부앞바다 -> 거제시동부앞바다
    if sea:
        prefix = f"{sea}앞바다"
        if z.startswith(prefix) and len(z) > len(prefix):
            z = z[len(prefix):]
    return z


def extract_rows(pdf_path, year, sea, water):
    """PDF 한 개에서 표 행들을 뽑아 리스트로 반환."""
    rows = []
    cur_zone = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    if not r or len(r) < 6:
                        continue
                    # 헤더행 스킵
                    if r[0] == "구역" or r[1] in ("특보종류", "발표", None):
                        # 단, 구역명만 있고 특보칸이 빈 병합행일 수 있으니 구역 갱신은 시도
                        z = clean_zone(r[0], sea)
                        if z and r[1] in ("특보종류", "발표", None):
                            # 진짜 헤더가 아니라 구역만 있는 행이면 아래 로직에서 처리되므로 pass
                            if r[1] in ("특보종류",) or r[0] == "구역":
                                continue
                        else:
                            continue
                    z = clean_zone(r[0], sea)
                    if z:
                        cur_zone = z
                    warn_type = r[1]
                    if not warn_type:
                        continue
                    ann_pub, ann_eff = r[2], r[3]
                    c4, c5 = r[4], r[5]
                    chg_pub = chg_eff = chg_note = ""
                    if c4 and DATE_RE.match(c4):
                        chg_pub, chg_eff = c4, (c5 or "")
                    elif c4:
                        chg_note = c4
                    rows.append(["기상특보(해상)", year, sea, water,
                                 cur_zone, warn_type,
                                 ann_pub, ann_eff, chg_pub, chg_eff, chg_note])
    return rows


def main():
    only = set(str(y) for y in ONLY_YEARS)
    by_year = defaultdict(list)      # 연도 -> 행 리스트
    stats = defaultdict(lambda: {"파일": 0, "행": 0, "스킵": 0})

    for dirpath, _dirs, files in os.walk(DOWNLOAD_ROOT):
        rel = os.path.relpath(dirpath, DOWNLOAD_ROOT)
        parts = rel.split(os.sep)
        if len(parts) < 3:
            continue                 # 연도\해역\바다 깊이가 아니면 skip
        year_dir, sea_dir, water_dir = parts[0], parts[1], parts[2]
        if only and year_dir not in only:
            continue

        for fname in sorted(files):
            if not fname.lower().endswith(".pdf"):
                continue
            m = FNAME_RE.match(fname)
            if not m:
                print(f"  [스킵] 파일명 규칙 불일치: {fname}")
                continue
            year, sea, water, warn, tail = m.groups()
            if SKIP_SPLIT_YEARS and tail:
                stats[year]["스킵"] += 1
                print(f"  [스킵] 개편연도 꼬리표: {fname}")
                continue

            # 해역·바다는 '파일명' 기준을 신뢰한다.
            # (폴더명이 앞바다(1)처럼 괄호가 남아있는 연도가 있어 폴더는 참고만)
            water_base = re.sub(r"\(.*?\)$", "", water)   # 앞바다(1) -> 앞바다
            if sea != sea_dir or water_base != re.sub(r"\(.*?\)$", "", water_dir):
                print(f"  [참고] 폴더명 불일치(파일명 기준 사용): {fname} "
                      f"(폴더 {sea_dir}\\{water_dir})")

            path = os.path.join(dirpath, fname)
            try:
                # 바다 칼럼에는 (1)(2)를 뗀 통일형을 쓴다.
                # (1)(2)는 발급 단위일 뿐이라 CSV에는 남기지 않는다.
                rows = extract_rows(path, year, sea, water_base)
            except Exception as e:
                print(f"  [오류] {fname}: {e}")
                continue
            by_year[year].extend(rows)
            stats[year]["파일"] += 1
            stats[year]["행"] += len(rows)
            print(f"  [OK] {fname}: {len(rows)}행")

    if not by_year:
        print("변환할 PDF가 없습니다. 경로/연도 설정을 확인하세요.")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    for year in sorted(by_year):
        out = os.path.join(OUT_DIR, f"기상특보(해상)_{year}.csv")
        st = stats[year]

        def _write(path):
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(HEADER)
                w.writerows(by_year[year])

        try:
            _write(out)
            print(f"[저장] {out}  (파일 {st['파일']}개, {st['행']}행, "
                  f"스킵 {st['스킵']}개)")
        except PermissionError:
            # 엑셀 등으로 열어둔 경우: 대체 파일에 저장하고 계속 진행
            alt = out.replace(".csv", "_잠김대체.csv")
            print(f"   [경고] {out} 잠김(엑셀 열림?) -> 대체 파일로 저장")
            try:
                _write(alt)
                print(f"[저장] {alt}  (파일 {st['파일']}개, {st['행']}행, "
                      f"스킵 {st['스킵']}개)")
            except PermissionError:
                print(f"   [실패] {year}년 저장 불가. 엑셀을 닫고 재실행하세요.")

    print("\n완료.")


if __name__ == "__main__":
    main()