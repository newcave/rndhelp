"""수탁과제 수행 현황 엑셀(연도별 시트) → data/ongoing_projects.csv

- 책임자·실무자(개인 이름)는 공개 저장소에 올리지 않으므로 의도적으로 제외한다.
- 부서 열은 병합셀이라 앞 행 값으로 채우고, 합계 행(구분 없음)은 제거한다.
사용:  python scripts/build_status_data.py <엑셀 경로>
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "ongoing_projects.csv"
DEPT = {"경영": "경영연구소", "수자원환경": "수자원환경연구소", "상하수도": "상하수도연구소", "물인프라안전": "물인프라안전연구소",
        "물에너지": "물에너지연구소", "수자원위성": "수자원위성연구소", "연구관리처": "연구관리처", "AI": "AI연구소"}
AGENCY_FIX = {"한국환경산업기술원(KETI)": "한국환경산업기술원(KEITI)"}  # 원본 표기 오타로 판단해 통일


def main(path: str) -> None:
    rows = []
    for name, d in pd.read_excel(path, sheet_name=None).items():
        year = int(name[:4])
        d = d.copy()
        d["부서"] = d["부서"].ffill()
        d = d[d["구분"].notna()]
        for c in ["총 연구 시작", "총 연구 종료", "당해년도 시작", "당해년도 종료"]:
            d[c] = pd.to_datetime(d[c].astype(str).str[:10]).dt.strftime("%Y-%m-%d")
        d["연구소"] = d["부서"].map(DEPT).fillna(d["부서"])
        d["발주기관"] = d["발주기관"].replace(AGENCY_FIX)
        d["연도"] = year
        rows.append(d[["연도", "연구소", "과제명", "총 연구 시작", "총 연구 종료", "당해년도 시작", "당해년도 종료",
                       "총 연구비", "당해년도 연구비", "참여방법", "참여형태", "발주기관"]])
    out = pd.concat(rows, ignore_index=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(out.groupby("연도").agg(과제=("과제명", "count"), 당해=("당해년도 연구비", "sum")))


if __name__ == "__main__":
    main(sys.argv[1])
