import io
from datetime import date

import pandas as pd
import streamlit as st

from core import checks, loader, mapper, state, ui

st.markdown('<div class="kw-crumb">수행·정산 › 정산 Adaptor</div>', unsafe_allow_html=True)
st.markdown('<div class="kw-title">정산 Adaptor<span class="kw-beta">BETA</span></div>', unsafe_allow_html=True)
st.markdown('<div class="kw-desc">K-water 내부 시스템의 집행·방침·과제 자료를 한곳에 모아, 정해진 매핑과 점검 절차에 따라 '
            '<b>RCMS 입력·정산용 자료로 변환</b>하는 어댑터. 연구원은 절차를 따라가며 확인·확정만 하면 됨.</div>',
            unsafe_allow_html=True)

hm = state.get_mapper(state.model_version())
rs = state.get_search()

# ───────────────────────── 개념 ─────────────────────────
ui.section("R&D 반복업무 절감을 위한 어댑터 활용 프로세스")
c1, c2 = st.columns([1.1, 1])
with c1:
    st.markdown(
        "- 어댑터는 집행 사실(금액·거래처·증빙)은 **바꾸지 않고**, 분류(비목·세목)와 형식만 RCMS 규격에 맞게 변환함.\n"
        "- 룰 기반 판정과 AI 분류로 1차 변환하고, <b>최종 확정은 연구원</b>이 함. (자동확정 / 검토필요 / 제외·소명으로 구분)",
        unsafe_allow_html=True)
with c2:
    ui.note("<b>현재 단계(베타)</b><br>시스템 직접 연계 전, 각 시스템에서 내려받은 파일(CSV/XLSX)을 올려 사용하는 방식으로 시험함. "
            "FMS·OASIS·STP와의 연계 범위와 방식은 시스템 담당 부서 협의 후 확정 예정.")

st.markdown(
    '<div class="kw-flow">'
    '<div class="col">'
    '<div class="box src">K-water FMS<small>재무통합 · 집행내역</small></div>'
    '<div class="box src">OASIS<small>관련 방침·지침 / 재무통합 · 집행내역(회계결의서, 영수증 등)</small></div>'
    '<div class="box src opt">STP<small>기술통합관리 · 과제정보 (필요시)</small></div></div>'
    '<div class="arr">→</div>'
    '<div class="box store">저장소(예산집행 전용, 비공개)<small>Adaptor 보관소 — 자료 보관·버전 관리</small></div>'
    '<div class="arr">→</div>'
    '<div class="box adp">정산 Adaptor<small>① 매핑 ② 점검 ③ 변환</small></div>'
    '<div class="arr">→</div>'
    '<div class="box dst">RCMS<small>입력용 자료 · 정산</small></div>'
    '</div>', unsafe_allow_html=True)

# ───────────────────────── 입력 ─────────────────────────
ui.section("과제·자료 선택")
with st.expander("과제 정보 (STP 과제정보에 해당)", expanded=False):
    a1, a2, a3 = st.columns(3)
    pname = a1.text_input("과제명", "AI 기반 정수장 미량오염물질 대응 기술 개발")
    start = a2.date_input("협약 시작일", date(2025, 4, 1))
    end = a3.date_input("협약 종료일", date(2026, 12, 31))
    b1, b2 = st.columns(2)
    direct_total = b1.number_input("직접비 총액(현물 포함, 백만원)", value=900, step=10) * 1_000_000
    personnel = b2.number_input("수정인건비(현물 포함, 백만원)", value=260, step=10) * 1_000_000

up = st.file_uploader("FMS 집행내역 (CSV/XLSX) — 열: date, account, description, vendor, amount, pay_method, evidence, external_attendee, note",
                      type=["csv", "xlsx"], key="adaptor_up")
if up is not None:
    src = pd.read_excel(up, dtype={"account": str}) if up.name.endswith("xlsx") else pd.read_csv(up, dtype={"account": str}, encoding="utf-8-sig")
else:
    src = loader.load_csv("sample_ledger.csv")
    st.caption("파일을 올리지 않으면 예시 집행내역 22건으로 진행함.")

mapped = mapper.results_to_frame(src, hm.map_many(src)).reset_index(drop=True)
pinfo = checks.ProjectInfo(start, end, int(direct_total), int(personnel))
find = checks.run_checks(mapped, pinfo)

sev_by_row: dict[int, set] = {}
for r in find.itertuples():
    if pd.notna(r.row):
        sev_by_row.setdefault(int(r.row), set()).add(r.severity)


def lane(i: int, row: pd.Series) -> str:
    sv = sev_by_row.get(i, set())
    if row["판정"] == "불인정" or "불인정" in sv:
        return "제외·소명"
    if row["판정"] == "검토필요" or sv:
        return "확인 후 입력"
    return "입력 가능"


mapped["처리 구분"] = [lane(i, r) for i, r in mapped.iterrows()]
mapped["참고·확인 사항"] = [
    "; ".join(sorted({x.title for x in find.itertuples() if pd.notna(x.row) and int(x.row) == i})
              or ([r["주의"]] if r["주의"] else []))
    for i, r in mapped.iterrows()]
cnt = mapped["처리 구분"].value_counts()

# ───────────────────────── 한 건 따라가기 ─────────────────────────
ui.section("예시 한 건으로 보기")
opts = {f"#{i + 1} · {r['description']} ({int(r['amount']):,}원)": i for i, r in mapped.iterrows()}
default = next((k for k, i in opts.items() if "PFAS" in k), list(opts)[0])
pick = st.selectbox("집행 건 선택", list(opts), index=list(opts).index(default))
row = mapped.loc[opts[pick]]
left, mid, right = st.columns([1, 0.15, 1.2])
with left:
    st.markdown("**FMS (K-water)**")
    acc_name = dict(zip(loader.accounts()["code"].astype(str), loader.accounts()["name"])).get(str(row["account"]), "")
    st.markdown(f"- 계정: {row['account']} {acc_name}\n- 적요: {row['description']}\n- 거래처: {row['vendor']}\n- 금액: {int(row['amount']):,}원\n- 증빙: {row['evidence']}")
with mid:
    st.markdown("<div style='text-align:center;font-size:1.6rem;color:#8B95A1;padding-top:2.2rem'>→</div>", unsafe_allow_html=True)
with right:
    st.markdown("**RCMS 입력 자료**")
    st.markdown(f"- 비목 › 세목: **{row['RCMS 비목']} › {row['RCMS 세목']}**\n- 판정: {row['판정']} ({row['근거']})\n- 처리 구분: **{row['처리 구분']}**"
                + (f"\n- 참고·확인 사항: {row['참고·확인 사항']}" if row["참고·확인 사항"] else "")
                + f"\n- 필요 증빙: {row['필요 증빙']}")

# ───────────────────────── 절차 ─────────────────────────
ui.section("어댑터 절차")
t1, t2, t3, t4, t5 = st.tabs(["① 자료 보관", "② 비목 매핑", "③ 사전 점검", "④ RCMS 변환", "⑤ 확정"])

with t1:
    st.markdown("연계 대상 자료를 **저장소(예산집행 전용, 비공개)** 에 모아 두고, 과제별로 같은 기준 자료를 사용함.")
    st.dataframe(pd.DataFrame([
        {"자료": "집행내역", "출처": "K-water FMS (재무통합)", "용도": "RCMS 비목 변환 대상", "필요": "필수", "수신 현황": f"{len(mapped)}건"},
        {"자료": "관련 방침·지침", "출처": "OASIS", "용도": "내부 정산 방침·절차 기준", "필요": "필수", "수신 현황": "규정 아카이브와 함께 관리"},
        {"자료": "과제·기술 정보", "출처": "STP (기술통합관리)", "용도": "협약기간·과제 구성 등 확인", "필요": "필요시", "수신 현황": f"{pname} · {start:%Y.%m.%d}~{end:%Y.%m.%d}"},
    ]), hide_index=True, width="stretch")
    st.caption("보관소는 각 시스템 원본을 대체하지 않고, 정산 작업용 사본과 변환 이력만 관리하는 별도 공간으로 구상함.")

with t2:
    st.markdown("정해진 **매핑 룰**과 AI 분류로 K-water 계정·적요를 RCMS 비목·세목으로 변환함.")
    n = mapped["판정"].value_counts()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("전체", f"{len(mapped)}건")
    m2.metric("자동확정", f"{n.get('자동확정', 0)}건")
    m3.metric("검토필요", f"{n.get('검토필요', 0)}건")
    m4.metric("불인정", f"{n.get('불인정', 0)}건")
    st.dataframe(ui.style_status(mapped[["date", "account", "description", "amount", "RCMS 비목", "RCMS 세목", "판정", "근거"]], "판정"),
                 hide_index=True, width="stretch", height=300,
                 column_config={"date": "일자", "account": "계정", "description": "적요", "amount": st.column_config.NumberColumn("금액", format="localized")})

with t3:
    st.markdown("정산에서 자주 지적되는 항목(협약기간·회의 식비·현금 지출·증빙·한도 등)을 **변환 전에 점검**함.")
    sv = find["severity"].value_counts() if len(find) else pd.Series(dtype=int)
    k1, k2, k3 = st.columns(3)
    k1.metric("불인정(회수 위험)", f"{sv.get('불인정', 0)}건")
    k2.metric("보완 필요", f"{sv.get('보완', 0)}건")
    k3.metric("담당자 확인", f"{sv.get('확인', 0)}건")
    if len(find):
        tb = find.copy()
        tb["건"] = tb["row"].apply(lambda r: "과제 전체" if pd.isna(r) else f"#{int(r) + 1}")
        st.dataframe(ui.style_status(tb[["건", "severity", "title", "detail"]], "severity"), hide_index=True, width="stretch", height=300,
                     column_config={"severity": "등급", "title": "점검 항목", "detail": st.column_config.TextColumn("설명", width="large")})
    st.caption("상세 점검과 근거 규정은 '정산 사전점검' 메뉴에서 확인할 수 있음.")

with t4:
    st.markdown("점검 결과에 따라 **세 가지로 나누어** RCMS 입력용 자료를 만듦.")
    g1, g2, g3 = st.columns(3)
    with g1:
        ui.card("입력 가능", f"{cnt.get('입력 가능', 0)}건", "그대로 RCMS에 입력")
    with g2:
        ui.card("확인 후 입력", f"{cnt.get('확인 후 입력', 0)}건", "증빙·소명 확인 뒤 입력")
    with g3:
        ui.card("제외·소명", f"{cnt.get('제외·소명', 0)}건", "RCMS 입력 제외 또는 별도 소명")
    out_cols = ["처리 구분", "date", "RCMS 비목", "RCMS 세목", "description", "vendor", "amount", "evidence", "필요 증빙", "참고·확인 사항"]
    names = {"date": "집행일", "description": "적요", "vendor": "거래처", "amount": "금액(원)", "evidence": "보유 증빙"}
    rc = mapped[out_cols].rename(columns=names)
    pick_lane = st.radio("구분", ["전체", "입력 가능", "확인 후 입력", "제외·소명"], horizontal=True, label_visibility="collapsed")
    view = rc if pick_lane == "전체" else rc[rc["처리 구분"] == pick_lane]
    st.dataframe(view, hide_index=True, width="stretch", height=320,
                 column_config={"금액(원)": st.column_config.NumberColumn(format="localized")})
    summ = mapped[mapped["처리 구분"] != "제외·소명"].groupby(["RCMS 비목", "RCMS 세목"], as_index=False)["amount"].agg(["count", "sum"]).rename(columns={"count": "건수", "sum": "금액(원)"})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as xw:
        rc[rc["처리 구분"] == "입력 가능"].to_excel(xw, sheet_name="RCMS입력_가능", index=False)
        rc[rc["처리 구분"] == "확인 후 입력"].to_excel(xw, sheet_name="확인후입력", index=False)
        rc[rc["처리 구분"] == "제외·소명"].to_excel(xw, sheet_name="제외·소명", index=False)
        summ.to_excel(xw, sheet_name="비목별요약", index=False)
    st.download_button("RCMS 입력용 자료 내려받기 (xlsx)", buf.getvalue(), "rcms_adaptor_output.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

with t5:
    st.markdown("업로드 전 **연구원이 확인·확정**하는 단계. 어댑터는 판단을 대신하지 않고 확인 대상을 좁혀 줌.")
    checklist = [
        "'확인 후 입력' 건의 증빙·소명 자료를 확보했는가",
        "'제외·소명' 건은 RCMS에 입력하지 않고 소명 또는 기관 부담으로 처리했는가",
        "비목별 합계가 협약 예산(비목별 한도)을 넘지 않는가",
        "회의비 식비 등 2026.5.6. 개정 기준 적용 시점을 확인했는가",
        "변환 결과를 RCMS 입력 후 정산 담당 부서와 최종 대조했는가",
    ]
    done = [st.checkbox(c, key=f"adp_chk_{i}") for i, c in enumerate(checklist)]
    st.progress(sum(done) / len(done), text=f"확인 {sum(done)}/{len(done)}")
    ui.note("본 어댑터의 결과는 사전 점검·변환 보조 자료이며, RCMS 입력과 정산 책임은 연구책임자·정산 담당 부서에 있음.")
