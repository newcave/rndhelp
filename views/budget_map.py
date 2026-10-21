"""비목 매핑 지도 — K-water 예산과목(경상개발비·조사설계비) ↔ 국가R&D 비목·세목 대응 관계.

데이터: data/budget_map.json (연구개발비 사용 기준 고시 제2026-38호 기준 매칭표에서 생성)
지도:   assets/budget_map.html (클릭·연결선 상호작용은 HTML/JS로 그림)
"""
import io
import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core import ui

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "budget_map.json").read_text(encoding="utf-8"))
TEMPLATE = (ROOT / "assets" / "budget_map.html").read_text(encoding="utf-8")
NAT = {n["key"]: n for n in DATA["national"]}
JUDGE_COLOR = {"가능": ("#1E6B3A", "#E6F4EA"), "조건부 가능": ("#1A56A8", "#E8F0FB"),
               "불가": ("#B42318", "#FDECEA"), "확인 필요": ("#4E5968", "#F2F4F6")}
TYPE_COLOR = {"일치": ("#1E6B3A", "#E6F4EA"), "조건부 일치": ("#1A56A8", "#E8F0FB"), "분리 매칭": ("#5B3FA0", "#EFEAFB"),
              "일부 불가": ("#9A5B00", "#FFF4E0"), "매칭 불가": ("#B42318", "#FDECEA"), "내역 확인": ("#4E5968", "#F2F4F6")}

ui.header("수행·정산 › 비목 매핑 지도", "비목 매핑 지도 (K-water 예산과목 ↔ 국가R&D)",
          "K-water 경상개발비·조사설계비 과목이 국가R&D 비목·세목 어디에 해당하는지, <b>조건</b>과 <b>불가 사유</b>까지 한눈에 봄. "
          "묶음·과목·세목을 누르면 세부 내용이 나옴.")
ui.note("계획서 <b>편성 단계</b>에서 과목별 대응 관계를 보는 화면. 실제 집행 건(계정+적요)의 세목 판정은 "
        '<a href="mapping" target="_self">비목 매핑 › 단건 조회</a>에서 확인. '
        f"<br><span style='color:#6B7684;font-size:.8rem'>{DATA['meta']['basis']} · {DATA['meta']['status']}</span>")


def color_cells(df, cols, table):
    def f(v):
        fg, bg = table.get(str(v), (None, None))
        return f"color:{fg};background-color:{bg};font-weight:600" if fg else ""
    return df.style.map(f, subset=[c for c in cols if c in df.columns])


def side_text(side: dict) -> str:
    """K-water 작성양식 총괄표 구분. 공통 과목이 체계마다 다르면 둘 다 표시 (예: 여비 — 경상 간접비 / 조사 직접비)."""
    vals = set(side.values())
    return vals.pop() if len(vals) == 1 else " / ".join(f"{s} {v}" for s, v in side.items())


def rule_rows():
    rows = []
    for k in DATA["kwater"]:
        for r in k["rules"]:
            rows.append({"체계": k["system"], "구분": side_text(k.get("side", {})), "묶음": k["group"], "K-water 과목": k["bimok"], "세부": k["sub"], "매칭 유형": k["type"],
                         "조건·용도": r["cond"], "국가R&D 세목": " + ".join(r["keys"]) or "-", "판정": r["judge"],
                         "충족 조건 / 불가 사유": r["req"], "근거": r["basis"],
                         "RCMS 항목/세부항목": " / ".join(dict.fromkeys(f"{NAT[x]['rcms_item']} / {NAT[x]['rcms_sub']}" for x in r["keys"]))
                                              if r["judge"] in ("가능", "조건부 가능") else ""})
    return pd.DataFrame(rows)


tab1, tab2, tab3 = st.tabs(["매핑 지도", "표로 보기", "K-water 특수 규정 비교"])

# ───────────────────────── 지도 ─────────────────────────
with tab1:
    payload = json.dumps(DATA, ensure_ascii=False).replace("</", "<\\/")
    html = (TEMPLATE.replace("/*DATA_JSON*/", payload)
            .replace("/*MAP_ONLY*/false", "true")
            .replace("<!--PREVIEW_HEADER-->", ""))
    components.html(html, height=880, scrolling=True)

# ───────────────────────── 표 ─────────────────────────
with tab2:
    df = rule_rows()
    c1, c2, c3 = st.columns([2, 1.2, 1.2])
    q = c1.text_input("검색 (과목·세목·조건)", placeholder="예: 회의비, 클라우드, 소모품")
    types = c2.multiselect("매칭 유형", list(TYPE_COLOR))
    judges = c3.multiselect("판정", list(JUDGE_COLOR))
    view = df
    if q.strip():
        key = q.replace(" ", "")
        view = view[view.apply(lambda r: key in "".join(map(str, r.values)).replace(" ", ""), axis=1)]
    if types:
        view = view[view["매칭 유형"].isin(types)]
    if judges:
        view = view[view["판정"].isin(judges)]
    st.caption(f"{len(view)} / {len(df)}행 — 과목 하나가 조건·용도별로 여러 행으로 나뉨")
    styled = color_cells(view, ["판정"], JUDGE_COLOR).map(
        lambda v: (lambda c: f"color:{c[0]};background-color:{c[1]};font-weight:600" if c else "")(TYPE_COLOR.get(str(v))),
        subset=["매칭 유형"])
    st.dataframe(styled, hide_index=True, width="stretch", height=520)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="세부 매칭 규칙", index=False)
        pd.DataFrame(DATA["national"]).to_excel(xw, sheet_name="국가R&D 세목", index=False)
        pd.DataFrame(DATA["compare"]).to_excel(xw, sheet_name="K-water 특수 규정 비교", index=False)
    st.download_button("엑셀 내려받기", buf.getvalue(), file_name="K-water_국가R&D_비목_매핑.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ───────────────────────── 규정 비교 ─────────────────────────
with tab3:
    ui.note("K-water 사내 R&D(경상개발비·조사설계비) 기준과 국가R&D 기준이 다른 점. 수탁과제는 국가R&D 기준이 우선함.")
    cmp = pd.DataFrame(DATA["compare"]).rename(columns={"item": "항목", "kwater": "K-water 기준(가이드라인)",
                                                       "national": "국가R&D 기준", "implication": "시사점"})
    st.dataframe(cmp, hide_index=True, width="stretch",
                 column_config={c: st.column_config.TextColumn(width="large") for c in cmp.columns[1:]})

    ui.section("국가R&D 세목별 K-water 대응")
    rev = []
    for n in DATA["national"]:
        hits = [(k, r) for k in DATA["kwater"] for r in k["rules"] if n["key"] in r["keys"]]
        usable = [h for h in hits if h[1]["judge"] in ("가능", "조건부 가능")]
        status = ("해당 없음" if n["apply"] == "×" else
                  "대응 있음" if any(h[1]["judge"] == "가능" for h in usable) else
                  "조건부 대응" if usable else "대응 없음")
        rev.append({"구분": n["group"], "비목": n["bimok"], "세목": n["semok"], "공기업 적용": n["apply"], "K-water 대응": status,
                    "대응 K-water 과목": " / ".join(f"{k['bimok']} › {k['sub']} [{r['judge']}]" for k, r in hits)})
    rv = pd.DataFrame(rev)
    st.dataframe(color_cells(rv, ["K-water 대응"], {"대응 있음": ("#1E6B3A", "#E6F4EA"), "조건부 대응": ("#1A56A8", "#E8F0FB"),
                                                  "대응 없음": ("#B42318", "#FDECEA"), "해당 없음": ("#4E5968", "#F2F4F6")}),
                 hide_index=True, width="stretch", height=480)
    st.caption("'대응 없음' 세목은 수탁과제 예산에서 국가R&D 비목으로 편성하고, 사내 회계 계정은 연구지원 부서가 정함.")
