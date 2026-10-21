"""제안서(연구개발계획서) 연구개발비 편성 검증 — 1개 연차 기준."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

BUDGET_ROWS = [
    "인건비", "학생인건비", "연구시설·장비비", "연구재료비", "연구활동비",
    "  └ 외부 전문기술 활용비", "연구혁신비", "연구수당", "위탁연구개발비", "간접비",
]
INKIND_ALLOWED = {"인건비", "연구시설·장비비", "연구재료비", "연구활동비"}  # 연구활동비는 SW 활용비 현물에 한함
DIRECT = [r for r in BUDGET_ROWS if r not in ("간접비", "  └ 외부 전문기술 활용비")]


@dataclass
class BudgetCheck:
    ok: bool
    item: str
    value: str
    limit: str
    ref: str
    note: str = ""


def default_table() -> pd.DataFrame:
    """공기업 주관, 정부출연 3억원 例示 (단위: 천원)."""
    data = {
        "인건비": (0, 210_000), "학생인건비": (0, 0), "연구시설·장비비": (40_000, 60_000),
        "연구재료비": (45_000, 0), "연구활동비": (95_000, 0), "  └ 외부 전문기술 활용비": (60_000, 0),
        "연구혁신비": (12_000, 0), "연구수당": (38_000, 0), "위탁연구개발비": (60_000, 0), "간접비": (25_000, 0),
    }
    return pd.DataFrame([{"비목": k, "현금(천원)": v[0], "현물(천원)": v[1]} for k, v in data.items()])


def evaluate(tbl: pd.DataFrame, gov: int, gov_max: float, cash_min: float, indirect_rate: float,
             exclude_from_modified: tuple[str, ...] = ("현물", "위탁연구개발비")) -> tuple[dict, list[BudgetCheck]]:
    t = tbl.set_index("비목")
    cash = t["현금(천원)"].fillna(0).astype(float)
    ink = t["현물(천원)"].fillna(0).astype(float)
    direct_cash = sum(cash.get(r, 0) for r in DIRECT)
    direct_ink = sum(ink.get(r, 0) for r in DIRECT)
    direct = direct_cash + direct_ink
    total = direct + cash.get("간접비", 0) + ink.get("간접비", 0)
    total_cash = direct_cash + cash.get("간접비", 0)
    org = total - gov
    org_cash = total_cash - gov
    personnel = cash.get("인건비", 0) + ink.get("인건비", 0)
    mod_direct = direct
    if "현물" in exclude_from_modified:
        mod_direct -= direct_ink
    if "위탁연구개발비" in exclude_from_modified:
        mod_direct -= cash.get("위탁연구개발비", 0)
    if "국제공동연구개발비" in exclude_from_modified:
        mod_direct -= cash.get("국제공동연구개발비", 0)

    s = {
        "총 연구개발비": total, "정부지원": gov, "기관부담": org, "기관부담 현금": org_cash,
        "기관부담 현물": direct_ink, "직접비": direct, "수정직접비": mod_direct,
    }
    C: list[BudgetCheck] = []
    gr = gov / total if total else 0
    C.append(BudgetCheck(gr <= gov_max + 1e-9, "정부지원 비율", f"{gr:.1%}", f"≤ {gov_max:.0%}", "K13"))
    ocr = org_cash / org if org > 0 else 0
    C.append(BudgetCheck(ocr >= cash_min - 1e-9, "기관부담 중 현금 비율", f"{ocr:.1%}", f"≥ {cash_min:.0%}", "K13",
                         "현금은 연차 종료 3개월 전까지 납부"))
    C.append(BudgetCheck(org_cash >= 0, "현금 재원 정합성", f"현금 편성 {total_cash:,.0f} / 정부지원 {gov:,.0f}",
                         "현금 편성 ≥ 정부지원", "K13", "현금 편성액이 정부지원보다 작으면 정부지원 일부가 편성되지 않은 상태"))
    allow = cash.get("연구수당", 0) + ink.get("연구수당", 0)
    C.append(BudgetCheck(allow <= 0.2 * personnel + 1e-9, "연구수당", f"{allow:,.0f}", f"≤ 수정인건비 20% ({0.2*personnel:,.0f})", "K06"))
    ext = cash.get("  └ 외부 전문기술 활용비", 0) + ink.get("  └ 외부 전문기술 활용비", 0)
    C.append(BudgetCheck(ext <= 0.4 * direct + 1e-9, "외부 전문기술 활용비", f"{ext:,.0f}", f"≤ 직접비 40% ({0.4*direct:,.0f})", "K05"))
    act = cash.get("연구활동비", 0) + ink.get("연구활동비", 0)
    C.append(BudgetCheck(ext <= act + 1e-9, "외부 전문기술 ⊂ 연구활동비", f"{ext:,.0f}", f"≤ 연구활동비 ({act:,.0f})", "K01"))
    cons = cash.get("위탁연구개발비", 0)
    C.append(BudgetCheck(cons <= 0.4 * direct + 1e-9, "위탁연구개발비", f"{cons:,.0f}", f"≤ 직접비 40% ({0.4*direct:,.0f})", "K21"))
    inno = cash.get("연구혁신비", 0)
    base = cash.get("연구재료비", 0) + ink.get("연구재료비", 0) + act
    inno_lim = min(0.1 * base, 50_000)
    C.append(BudgetCheck(inno <= inno_lim + 1e-9, "연구혁신비", f"{inno:,.0f}", f"≤ min(재료+활동 10%, 5천만원) = {inno_lim:,.0f}", "K02"))
    ind = cash.get("간접비", 0)
    C.append(BudgetCheck(ind <= mod_direct * indirect_rate + 1e-9, "간접비 (참고)", f"{ind:,.0f}",
                         f"≤ 수정직접비 × {indirect_rate:.1%} ({mod_direct*indirect_rate:,.0f})", "K09",
                         "공기업 수탁과제에는 고시비율 미해당이며 참고용 값임"))
    bad = [r for r in ink.index if ink.get(r, 0) > 0 and r.strip("└ ").strip() not in INKIND_ALLOWED]
    C.append(BudgetCheck(not bad, "현물 계상 가능 비목", ", ".join(bad) if bad else "적합",
                         "인건비·장비비·재료비·SW활용비", "K09"))
    if ink.get("연구시설·장비비", 0) > 0:
        C.append(BudgetCheck(True, "현물 장비 사전 반영", "확인 필요", "보유현황 표에 장비 단위 기재", "K11",
                             "장비별 자산번호·취득재원·산정근거를 계획서 단계에서 확정해 두면 정산 마찰이 크게 줄어듦"))
    return s, C
