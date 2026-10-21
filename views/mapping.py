import io
from datetime import datetime

import pandas as pd
import streamlit as st

from core import loader, mapper, state, ui

ui.header("수행·정산 › 비목 매핑", "비목 매핑 (K-water 정산시스템 → RCMS)",
          "K-water 계정과 적요를 넣으면 RCMS 비목·세목, 판정 근거, 필요한 증빙을 안내함. "
          "룰과 AI가 일치하면 <b>자동확정</b>, 엇갈리거나 확신이 낮으면 <b>검토필요</b>로 표시함.")

hm = state.get_mapper(state.model_version())
acc = loader.accounts()
acc_label = {r.code: f"{r.code} {r.name}" for r in acc.itertuples()}
semok_idx = loader.semok_index()
all_labels = [f"{v['bimok']} | {k}" for k, v in semok_idx.items()] + ["불인정 | 불인정(연구인력 지원비 제외 항목)", "불인정 | 불인정(시설·건설 목적)"]

tab1, tab2, tab3 = st.tabs(["단건 조회", "일괄 변환", "매핑 기준·모델"])

# ───────────────────────── 단건 ─────────────────────────
with tab1:
    c1, c2 = st.columns([1, 1.4])
    with c1:
        ui.section("K-water 정산시스템 (입력)")
        code = st.selectbox("K-water 계정", list(acc_label), index=list(acc_label).index("5260"),
                            format_func=lambda c: acc_label[c])
        desc = st.text_input("적요 / 품목", "수질 시료 PFAS 의뢰분석 20건")
        vendor = st.text_input("거래처 (선택)", "한국화학융합시험연구원")
        st.caption("예: 자문회의 도시락 · 에탄올 4L · AWS GPU 이용료 · Open Access APC · 기관 보유 장비 사용료")
        hint = acc.set_index("code").loc[code, "note"]
        if isinstance(hint, str) and hint:
            ui.note(f"<b>{acc_label[code]}</b> — {hint}")
    with c2:
        ui.section("RCMS (매핑 결과)")
        if desc.strip():
            r = hm.map_one(code, desc, vendor)
            st.markdown(
                f'<div class="kw-result"><div class="kw-kv">RCMS 비목 › 세목</div>'
                f'<div class="path">{r.bimok} › {r.semok}</div>'
                f'<div class="kw-kv">{ui.badge(r.status)} &nbsp; 근거: {r.basis}'
                + (f" · 룰 {r.rule.id} ({r.rule.name}, 매칭어 '{r.rule.matched}')" if r.rule else "")
                + "</div></div>", unsafe_allow_html=True)
            if r.warn:
                ui.note("⚠ " + r.warn, "warn")
            st.markdown("**필요 증빙**")
            for e in r.evidence or ["(세목별 증빙 정보 없음)"]:
                st.checkbox(e, key=f"ev_{e}", value=False)
            st.markdown("**AI 분류 상위 후보**")
            top = pd.DataFrame([{"후보": lab.replace("|", " › "), "확률": p} for lab, p in r.ml_top])
            st.dataframe(top, hide_index=True, width="stretch",
                         column_config={"확률": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)})

            with st.expander("판정 오류 시 — 올바른 비목으로 피드백·재학습"):
                fix = st.selectbox("올바른 RCMS 비목 | 세목", all_labels,
                                   index=all_labels.index(f"{r.bimok} | {r.semok}") if f"{r.bimok} | {r.semok}" in all_labels else 0)
                if st.button("피드백 저장", type="primary"):
                    b, s = [x.strip() for x in fix.split("|", 1)]
                    ok, msg = state.add_feedback({"account": code, "description": desc, "vendor": vendor,
                                        "rcms_bimok": b, "rcms_semok": s, "ts": datetime.now().isoformat(timespec="seconds")})
                    state.bump_model()
                    st.session_state["fb_msg"] = (ok, msg)
                    st.rerun()
        if "fb_msg" in st.session_state:
            _ok, _msg = st.session_state.pop("fb_msg")
            (st.success if _ok else st.warning)("피드백 저장 완료 — 모델 재학습. " + _msg)

# ───────────────────────── 일괄 ─────────────────────────
with tab2:
    st.markdown("K-water 정산시스템에서 내려받은 집행내역(CSV/XLSX)을 올리면 전체를 RCMS 비목으로 변환함. "
                "필수 열: `account`(계정코드), `description`(적요) · 선택: `vendor`, `amount`, `date`")
    up = st.file_uploader("집행내역 파일", type=["csv", "xlsx"], key="bulk")
    if up is not None:
        df = pd.read_excel(up, dtype={"account": str}) if up.name.endswith("xlsx") else pd.read_csv(up, dtype={"account": str}, encoding="utf-8-sig")
    else:
        st.caption("파일이 없으면 예시 집행내역 22건으로 표시함.")
        df = loader.load_csv("sample_ledger.csv")
    miss = {"account", "description"} - set(df.columns)
    if miss:
        st.error(f"필수 열 없음: {', '.join(miss)}")
    else:
        out = mapper.results_to_frame(df, hm.map_many(df))
        n = out["판정"].value_counts()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("전체", f"{len(out)}건")
        m2.metric("자동확정", f"{n.get('자동확정', 0)}건")
        m3.metric("검토필요", f"{n.get('검토필요', 0)}건")
        m4.metric("불인정", f"{n.get('불인정', 0)}건")
        sel = st.multiselect("판정 필터", ["자동확정", "검토필요", "불인정"], default=["자동확정", "검토필요", "불인정"])
        view = out[out["판정"].isin(sel)]
        cols = [c for c in ["판정", "date", "account", "description", "vendor", "amount", "RCMS 비목", "RCMS 세목", "근거", "AI 확신도", "주의", "필요 증빙"] if c in view.columns]
        st.dataframe(ui.style_status(view[cols], "판정"), hide_index=True, width="stretch", height=420,
                     column_config={"amount": st.column_config.NumberColumn("금액", format="localized"),
                                    "account": "계정", "description": "적요", "vendor": "거래처", "date": "일자",
                                    "AI 확신도": st.column_config.NumberColumn(format="%.2f")})
        buf = io.BytesIO()
        out.to_excel(buf, index=False)
        st.download_button("RCMS 비목 변환 결과 내려받기 (xlsx)", buf.getvalue(), "rcms_mapping.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ───────────────────────── 기준·모델 ─────────────────────────
with tab3:
    ui.section("K-water 계정 기본 대응표")
    st.dataframe(acc.rename(columns={"code": "계정코드", "name": "계정명", "type": "구분",
                                     "default_rcms_bimok": "기본 RCMS 비목", "note": "비고"}),
                 hide_index=True, width="stretch")
    ui.section("룰 목록")
    rules = pd.DataFrame([{"ID": r["id"], "이름": r["name"], "대상 계정": ", ".join(r.get("accounts", [])) or "전체",
                           "키워드": ", ".join(r["patterns"][:8]), "RCMS": f"{r['bimok']} › {r['semok']}",
                           "우선순위": r.get("priority"), "검증": "✓" if r.get("verified", True) else "확인필요"}
                          for r in loader.mapping_rules()])
    st.dataframe(rules, hide_index=True, width="stretch")
    ui.section("AI 분류 모델")
    m = hm.model
    c1, c2, c3 = st.columns(3)
    c1.metric("학습 집행건", f"{m.n_train:,}")
    c2.metric("담당자 피드백", f"{m.n_feedback:,}")
    c3.metric("검증 정확도(20% 홀드아웃)", f"{m.holdout_acc:.1%}")
    ui.note("TF-IDF(문자 2~4gram) + 로지스틱 회귀. <b>과거 K-water 집행내역 ↔ RCMS 최종 등록 비목</b> 쌍으로 학습함 "
            "(<code>data/train_ledger.csv</code>). 피드백 내용은 <code>data/feedback.csv</code>에 쌓이고 3배 가중으로 반영됨.")
    fb = state.read_feedback()
    if len(fb):
        st.dataframe(fb, hide_index=True, width="stretch")
    if st.button("모델 다시 학습"):
        state.bump_model()
        st.rerun()
