import streamlit as st

from core import loader, state, ui

ui.header("지원 › 규정·FAQ 검색", "규정·FAQ 검색",
          "연구개발비 사용 기준, KEITI 사례집 등 정산 관련 규정 요약에서 질문과 가까운 항목을 찾음.")

rs = state.get_search()
ex = {"회의 식대": "회의비 식대 참여연구원만 참석", "타 과제 장비 현물": "장비 현물 타 국가R&D 예산으로 산 장비",
      "연구수당 한도": "연구수당 한도", "연구혁신비": "연구혁신비 증빙 한도", "실적보고 기한": "사용실적보고 기한 제출서류",
      "분석 의뢰 한도": "외부 전문기술 활용비 분석 의뢰 한도"}
if "q" not in st.session_state:
    st.session_state.q = ex["회의 식대"]
st.caption("자주 묻는 질문")
cols = st.columns(len(ex))
for c, (label, query) in zip(cols, ex.items()):
    if c.button(label, width="stretch"):
        st.session_state.q = query
q = st.text_input("질문", key="q")

if q.strip():
    hits, conf = rs.search(q, k=4)
    lvl = conf["level"]
    kind = "note" if lvl == "근거 충분" else "warn"
    ui.note(f"<b>검색 신뢰도: {lvl}</b> · Top1 유사도 {conf['top1']:.2f} · Top1–Top2 마진 {conf['margin']:.2f} "
            "<span style='color:#8B95A1'>(연구원 RAG 지표 연구에서 검색 충분성 판별력이 높았던 두 지표를 표시)</span>", kind)
    for h in hits:
        st.markdown(
            f'<div class="kw-result" style="margin-top:8px"><div class="kw-kv">{ui.badge(h.category)} &nbsp; {h.id} · {h.article} · 유사도 {h.score:.2f}</div>'
            f'<div style="font-weight:700;margin:4px 0">{h.title}</div><div style="font-size:.9rem;color:#333D4B">{h.text}</div>'
            f'<div class="kw-kv" style="font-size:.78rem">출처: {h.source_name}</div></div>', unsafe_allow_html=True)

ui.note("요약문은 원문이 아님. 인용·소명 시에는 반드시 고시·지침 원문 조문 확인 필요. "
        "지식베이스는 <code>data/regulations.yaml</code>에서 항목 추가·수정 가능.")

ui.section("참고한 보고서·기준")
_reg = loader.regulations()
_cnt = {}
for _it in _reg["items"]:
    _cnt[_it["source"]] = _cnt.get(_it["source"], 0) + 1
_lines = []
for _k, _s in _reg["sources"].items():
    _name = f"[{_s['name']}]({_s['url']})" if _s.get("url") else _s["name"]
    _lines.append(f"- {_name} — {_cnt.get(_k, 0)}항목")
_lines.append("- 연구원 연구보고서: A Comprehensive Assessment of Reference-Free RAG Indicators for Korean Public Documents in the Water Sector — 검색 신뢰도 지표(Top1 유사도·Top1–Top2 마진)")
st.markdown("\n".join(_lines))
st.caption("링크는 대학 등에서 게시한 사본일 수 있어 인용·소명 시에는 발주기관 공식 원문을 확인할 것.")
