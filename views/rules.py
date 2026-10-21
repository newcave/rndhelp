import html
import re

import streamlit as st

from core import state, ui
from core.search import KINDS

ui.header("지원 › FAQ 검색", "FAQ 검색",
          "궁금한 점을 문장으로 입력하면 <b>규정 요약</b>(연구개발비 사용 기준·KEITI 운영규정 등), <b>RCMS FAQ</b>, "
          "<b>불인정 사례</b>, <b>비목별 증빙자료</b>, <b>RCMS 사용법</b>에서 가까운 항목을 찾음.")

rs = state.get_search()
KIND_COLOR = {"규정 요약": ("#0B3B6E", "#E1EAF5"), "RCMS FAQ": ("#1A56A8", "#E8F0FB"), "불인정 사례": ("#B42318", "#FDECEA"),
              "증빙자료": ("#1E6B3A", "#E6F4EA"), "RCMS 사용법": ("#5B3FA0", "#EFEAFB")}


def kind_badge(kind: str) -> str:
    fg, bg = KIND_COLOR.get(kind, ("#4E5968", "#F2F4F6"))
    return f'<span class="kw-badge" style="color:{fg};background:{bg}">{html.escape(kind)}</span>'


def body_html(text: str) -> str:
    """정리 자료의 목록(-, ∙, 1.)을 줄 단위로 살려서 보여 줌."""
    rows = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        ln = html.escape(ln)
        if re.match(r"^[-∙•]\s?", ln):
            ln = "· " + re.sub(r"^[-∙•]\s?", "", ln)
        rows.append(ln)
    return "<br>".join(rows)


def result_card(h, extra: str = "") -> str:
    src = (f'<a href="{h.source_url}" target="_blank">{html.escape(h.source_name)}</a>'
           if h.source_url else html.escape(h.source_name))
    where = f" · {html.escape(h.article)}" if h.article else ""
    return (f'<div class="kw-result" style="margin-top:8px"><div class="kw-kv">{kind_badge(h.kind)} '
            f'{ui.badge(h.category) if h.category != h.kind else ""} &nbsp; {h.id}{where}{extra}</div>'
            f'<div style="font-weight:700;margin:4px 0">{html.escape(h.title)}</div>'
            f'<div style="font-size:.9rem;color:#333D4B;line-height:1.6">{body_html(h.body)}</div>'
            f'<div class="kw-kv" style="font-size:.78rem">출처: {src}</div></div>')


tab1, tab2 = st.tabs(["질문으로 찾기", "자료별로 보기"])

# ───────────────────────── 질문으로 찾기 ─────────────────────────
with tab1:
    ex = {"회의 식대": "회의비 식대 참여연구원만 참석", "타 과제 장비 현물": "장비 현물 타 국가R&D 예산으로 산 장비",
          "연구수당 한도": "연구수당 한도", "연구혁신비": "연구혁신비 증빙 한도",
          "실적보고 기한": "사용실적보고 기한 제출서류", "출장비 증빙": "출장비 증빙자료",
          "카드 결제일": "카드 결제일 전에 등록 안 하면?", "부가세 복원": "부가세 복원 방법"}
    if "q" not in st.session_state:
        st.session_state.q = ex["회의 식대"]
    st.caption("자주 묻는 질문")
    labels = list(ex)
    for row in (labels[:4], labels[4:]):
        for c, label in zip(st.columns(4), row):
            if c.button(label, width="stretch"):
                st.session_state.q = ex[label]
    c1, c2 = st.columns([3, 2])
    q = c1.text_input("질문", key="q", placeholder="예: 학회 참가비에 식비가 포함돼 있으면?")
    kinds = c2.multiselect("자료 종류", KINDS, placeholder="전체")

    if q.strip():
        hits, conf = rs.search(q, k=5, kinds=kinds or None)
        if conf["expanded"]:
            st.caption("함께 찾은 규정 용어: " + ", ".join(conf["expanded"]))
        lvl = conf["level"]
        ui.note(f"<b>검색 신뢰도: {lvl}</b> · Top1 유사도 {conf['top1']:.2f} · Top1–Top2 마진 {conf['margin']:.2f} "
                "<span style='color:#8B95A1'>(연구원 RAG 지표 연구에서 검색 충분성 판별력이 높았던 두 지표를 표시)</span>",
                "note" if lvl == "근거 충분" else "warn")
        st.markdown("".join(result_card(h, f" · 유사도 {h.score:.2f}") for h in hits), unsafe_allow_html=True)

# ───────────────────────── 자료별로 보기 ─────────────────────────
with tab2:
    c1, c2 = st.columns([2, 3])
    kind = c1.selectbox("자료", KINDS, format_func=lambda k: f"{k} ({len(rs.by_kind(k))})")
    f = c2.text_input("이 자료 안에서 찾기", placeholder="예: 카드, 회의록, 이체")
    items = rs.by_kind(kind)
    if f.strip():
        key = f.replace(" ", "")
        items = [h for h in items if key in (h.title + h.category + h.body + h.article).replace(" ", "")]
    st.caption(f"{len(items)}개 항목")
    for h in items:
        with st.expander(f"{h.id} · {h.title}", expanded=bool(f.strip()) and len(items) <= 5):
            st.markdown(result_card(h), unsafe_allow_html=True)

ui.note("요약·정리 자료는 원문이 아님. 인용·소명 시에는 반드시 고시·지침 원문 조문 확인 필요. "
        "규정 요약은 <code>data/regulations.yaml</code>, 정리 자료는 <code>data/knowledge/*.md</code>, "
        "동의어는 <code>data/search_synonyms.yaml</code>에서 추가·수정 가능.")

ui.section("참고한 기준·자료")
_cnt = {}
for _it in rs.items:
    _cnt[_it["source"]] = _cnt.get(_it["source"], 0) + 1
_lines = []
for _k, _s in rs.sources.items():
    if not _cnt.get(_k):
        continue
    _name = f"[{_s['name']}]({_s['url']})" if _s.get("url") else _s["name"]
    _lines.append(f"- {_name} — {_cnt[_k]}항목")
_lines.append("- 연구원 연구보고서: A Comprehensive Assessment of Reference-Free RAG Indicators for Korean Public Documents in the Water Sector — 검색 신뢰도 지표(Top1 유사도·Top1–Top2 마진)")
st.markdown("\n".join(_lines))
st.caption("법령·고시·훈령 링크는 국가법령정보센터 현행 원문으로 연결됨. 사례집 등 전문기관 자료는 배포처 게시본을 확인할 것.")
