"""법령·규정 자료실 — 수탁과제 집행·정산 관련 법령·고시·훈령과 시스템 매뉴얼 원문 목록.

데이터: data/library.json (번호·시행일은 meta.checked 기준. 링크는 국가법령정보센터 '현행' 원문이라 개정되면 자동으로 최신본)
매뉴얼은 용량이 커서(15~55MB) 파일을 올리지 않고 공식 배포처로 연결. 정리 자료(FAQ·증빙 등)는 FAQ 검색에서 봄.
"""
import html
import json
from datetime import date
from pathlib import Path

import streamlit as st

from core import ui

ROOT = Path(__file__).resolve().parent.parent
LIB = json.loads((ROOT / "data" / "library.json").read_text(encoding="utf-8"))
LAW = "https://www.law.go.kr/"
CHECKED = date.fromisoformat(LIB["meta"]["checked"])
SCOPE_DESC = {"공통": "모든 국가R&D 과제에 적용", "환경부·KEITI": "한국환경산업기술원 과제(통합 RCMS)",
              "산업부·KEIT": "산업통상부 계열 과제(통합 RCMS)"}
SYS_DESC = {"통합 RCMS": "KEITI·KEIT 등 전문기관 과제의 연구비 집행", "통합 Ezbaro": "한국연구재단 등 과기정통부 계열 과제의 연구비 집행"}
KIND_COLOR = {"법률": ("#0B3B6E", "#E1EAF5"), "대통령령": ("#1A56A8", "#E8F0FB"), "부령": ("#3D6FB6", "#EEF3FA"),
              "고시": ("#1E6B3A", "#E6F4EA"), "훈령": ("#5B3FA0", "#EFEAFB")}

st.markdown("""<style>
.lib-row{display:flex;gap:14px;align-items:flex-start;border:1px solid #DDE3EA;border-radius:6px;padding:11px 14px;margin-bottom:7px;background:#fff}
.lib-row.key{border-left:4px solid #00A0B0}
.lib-row .bd{flex:1;min-width:0}
.lib-row .nm{font-weight:700;font-size:.97rem;color:#16202C}
.lib-row .mt{color:#6B7684;font-size:.8rem;margin-top:2px}
.lib-row .us{color:#333D4B;font-size:.87rem;margin-top:4px}
.lib-row a.go{flex-shrink:0;align-self:center;text-decoration:none;border:1px solid #B9D2F0;background:#E8F0FB;color:#005BAC;
  font-size:.82rem;font-weight:600;padding:6px 11px;border-radius:6px;white-space:nowrap}
.lib-row a.go:hover{background:#D6E6F8}
.lib-sub{font-weight:400;color:#8B95A1;font-size:.82rem;margin-left:6px}
@media (max-width:640px){.lib-row{flex-direction:column;gap:6px}.lib-row a.go{align-self:flex-start}}
</style>""", unsafe_allow_html=True)


def fmt(d: str) -> str:
    y, m, dd = d.split("-")
    return f"{y}.{int(m)}.{int(dd)}."


def recent(d: str) -> bool:
    x = date.fromisoformat(d)
    return 0 <= (CHECKED - x).days <= 92


def bdg(text: str, fg: str, bg: str, title: str = "") -> str:
    t = f' title="{html.escape(title)}"' if title else ""
    return f'<span class="kw-badge" style="color:{fg};background:{bg};margin-right:4px"{t}>{html.escape(text)}</span>'


def law_row(l: dict) -> str:
    b = bdg(l["kind"], *KIND_COLOR.get(l["kind"], ("#4E5968", "#F2F4F6")))
    if l.get("key"):
        b += bdg("핵심", "#00727E", "#E0F5F7")
    if recent(l["effective"]):
        b += bdg("최근 개정", "#9A5B00", "#FFF4E0")
    if l.get("pending"):
        b += bdg("시행 예정 개정", "#B42318", "#FDECEA", l["pending"])
    pend = f" · {html.escape(l['pending'])}" if l.get("pending") else ""
    return (f'<div class="lib-row{" key" if l.get("key") else ""}"><div class="bd"><div>{b}<span class="nm">{html.escape(l["title"])}</span></div>'
            f'<div class="mt">{html.escape(l["number"])} · 시행 {fmt(l["effective"])}{pend}</div>'
            f'<div class="us">{html.escape(l["use"])}</div></div>'
            f'<a class="go" href="{LAW + l["path"]}" target="_blank" rel="noopener">원문 보기 ↗</a></div>')


def manual_row(m: dict) -> str:
    b = bdg("핵심", "#00727E", "#E0F5F7") if m.get("key") else ""
    return (f'<div class="lib-row{" key" if m.get("key") else ""}"><div class="bd"><div>{b}<span class="nm">{html.escape(m["title"])}</span></div>'
            f'<div class="mt">{html.escape(m["edition"])} · {html.escape(m["issuer"])} · 배포처: {html.escape(m["where"])}</div>'
            f'<div class="us">{html.escape(m["use"])}</div></div>'
            f'<a class="go" href="{m["url"]}" target="_blank" rel="noopener">배포처 바로가기 ↗</a></div>')


ui.header("지원 › 법령·규정 자료실", "법령·규정 자료실",
          "수탁과제 집행·정산에 필요한 법령·고시·훈령과 시스템 매뉴얼을 한곳에 모음. 원문은 공식 사이트로 연결됨.")
ui.note(f"법령·고시·훈령 링크는 <b>국가법령정보센터 현행 원문</b>으로 열림 — 개정되면 링크가 자동으로 최신본을 보여 줌. "
        f"번호·시행일 확인일: <b>{fmt(LIB['meta']['checked'])}</b>")

laws, manuals = LIB["laws"], LIB["manuals"]
ui.card_grid([
    ("법령·고시·훈령", f"{len(laws)}건", f"핵심 {sum(1 for l in laws if l.get('key'))}건 · 공통/환경부/산업부"),
    ("최근 3개월 개정", f"{sum(1 for l in laws if recent(l['effective']))}건", "시행일 기준, 목록에 표시"),
    ("시스템 매뉴얼", f"{len(manuals)}종", "RCMS · Ezbaro · 혁신법 매뉴얼"),
    ("FAQ·증빙·불인정 사례", "바로 검색", "FAQ 검색 메뉴에서", "rules"),
])

tab1, tab2 = st.tabs(["법령·고시·훈령", "매뉴얼·시스템"])

with tab1:
    scopes = list(dict.fromkeys(l["scope"] for l in laws))
    c1, c2, c3 = st.columns([3, 1.4, 1])
    q = c1.text_input("법령명·용도로 찾기", placeholder="예: 사용 기준, 협약 변경, 장비")
    sc = c2.selectbox("범위", ["전체"] + scopes)
    c3.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
    key_only = c3.checkbox("핵심만")
    k = q.replace(" ", "")
    hit = [l for l in laws if (sc == "전체" or l["scope"] == sc) and (not key_only or l.get("key"))
           and (not k or k in (l["title"] + l["use"] + l["number"] + l["kind"]).replace(" ", ""))]
    st.caption(f"{len(hit)} / {len(laws)}건")
    if not hit:
        st.caption("찾는 법령이 없음")
    for s in scopes:
        rows = [l for l in hit if l["scope"] == s]
        if rows:
            st.markdown(f'<div class="kw-sec">{s}<span class="lib-sub">{SCOPE_DESC.get(s, "")}</span></div>'
                        + "".join(law_row(l) for l in rows), unsafe_allow_html=True)
    st.caption("※ 「산업기술혁신사업 연구개발비 산정, 관리 및 사용, 정산에 관한 요령」은 현행 행정규칙 목록에 없어 제외함"
               "(연구개발비는 「연구개발비 사용 기준」 적용). 학생인건비 계상기준·통합관리지침은 2021.1.1. 폐지됐고 공기업은 해당 없음.")

with tab2:
    ui.note("매뉴얼은 파일 용량이 커서(15~55MB) 사이트에 직접 올리지 않고 <b>공식 배포처</b>로 연결함. "
            "판(版)·발행일을 함께 적어 최신본인지 확인할 수 있게 함.")
    for s in dict.fromkeys(m["system"] for m in manuals):
        st.markdown(f'<div class="kw-sec">{s}<span class="lib-sub">{SYS_DESC.get(s, "")}</span></div>'
                    + "".join(manual_row(m) for m in manuals if m["system"] == s), unsafe_allow_html=True)

ui.note("<b>K-water 내부 자료</b>(연구계획서 예산편성 가이드라인·작성양식 등)는 공개 사이트에 올리지 않음. "
        "사내 공유 폴더 또는 연구지원 부서에서 받을 것.", "warn")
ui.note('함께 보기: <a href="rules" target="_self">FAQ 검색</a>(규정 요약·RCMS FAQ·불인정 사례·증빙자료) · '
        '<a href="budget-map" target="_self">비목 매핑 지도</a>(K-water 과목 ↔ 국가R&amp;D 세목)')
