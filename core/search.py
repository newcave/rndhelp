"""FAQ 검색 (경량 RAG의 검색 단계).

검색 대상: data/regulations.yaml 의 규정 요약(K01~) + data/knowledge/*.md 의 정리 자료
(RCMS FAQ·불인정 사례·비목별 증빙자료·RCMS 사용법). 다른 화면은 K 항목 id로 근거를 찾으므로(get) id는 유지한다.

신뢰도 표시는 연구원 RAG 지표 연구(Top1 점수·Top1–Top2 마진이 검색 충분성 판별에 유효)를 참고해
Top1 유사도와 Top1–Top2 마진으로 '근거 충분/부족'을 함께 보여준다. 임계값은 현재 지식베이스 기준 임시값.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import loader

KNOW = loader.DATA / "knowledge"

# 정리 자료: 파일, 종류, id 접두어, 출처 키, 출처(목록 하단 '참고한 기준'에 표시)
KNOWLEDGE = [
    ("rcms_faq.md", "RCMS FAQ", "FAQ", "RCMS_FAQ",
     {"name": "RCMS 실무자 교육매뉴얼 V1(2026.3.4) FAQ — 통합RCMS", "url": "https://www.rcms.go.kr"}),
    ("rcms_cases.md", "불인정 사례", "CASE", "RCMS_CASE",
     {"name": "RCMS 실무자 교육매뉴얼 V1(2026.3.4) 주요 불인정 사례 — 통합RCMS", "url": "https://www.rcms.go.kr"}),
    ("evidence_list.md", "증빙자료", "EVI", "MANUAL_EVI",
     {"name": "국가연구개발혁신법 매뉴얼(2026.7) 제3장 비목별 증명자료 표 — 과학기술정보통신부", "url": "https://www.iris.go.kr"}),
    ("rcms_guide.md", "RCMS 사용법", "GUIDE", "RCMS_GUIDE",
     {"name": "RCMS 초보자용 매뉴얼 v1.0(2026.7.23)·사용자 매뉴얼 v1.6 — 통합RCMS", "url": "https://www.rcms.go.kr"}),
]
TITLE_W = 0.4  # 제목 유사도 가중
# 질문 의도 단어: 검색어에서 빼고(어느 항목에나 있어 변별력이 없음) 해당 자료 종류에 가산점
INTENT = [(r"증빙\s*자료|증명\s*자료|증빙|구비\s*서류|서류", "증빙자료"), (r"불인정|인정\s*안|지적", "불인정 사례")]
INTENT_BONUS = 0.08
KINDS = ["규정 요약"] + [k[1] for k in KNOWLEDGE]


@dataclass
class Hit:
    id: str
    title: str
    category: str
    text: str
    article: str
    source_name: str
    source_url: str
    score: float
    kind: str = "규정 요약"
    body: str = ""          # 정리 자료 원문(마크다운 목록 유지). 규정 요약은 text와 같음


def _md_items(fname: str, kind: str, prefix: str, source: str) -> list[dict]:
    """'## 제목' 단위로 항목을 만들고, 바로 아래 '출처:' 줄은 조항(article) 자리에 둔다."""
    md = (KNOW / fname).read_text(encoding="utf-8")
    items = []
    for n, part in enumerate(re.split(r"^## ", md, flags=re.M)[1:], 1):
        head, _, body = part.partition("\n")
        body = body.strip()
        src = ""
        if body.startswith("출처:"):
            src, _, body = body.partition("\n")
            src = src.removeprefix("출처:").strip()
        head = head.strip()
        cat = kind
        if m := re.match(r"RCMS FAQ Q(\d+)\s*\[([^\]]+)\]\s*(.*)", head):      # RCMS FAQ Q01 [인증서] 제목
            rid, cat, head = f"FAQ-{m.group(1)}", m.group(2), m.group(3)
        elif m := re.match(r"불인정 사례 (\d+):\s*(.*)", head):
            rid, head = f"CASE-{m.group(1)}", m.group(2)
        else:
            rid = f"{prefix}-{n:02d}"
            if " > " in head:                                                   # 인건비 > 내부 인건비 증명자료
                cat = head.split(" > ")[0]
        items.append({"id": rid, "title": head, "category": cat, "source": source, "article": src,
                      "text": body.strip(), "kind": kind})
    return items


class RegSearch:
    def __init__(self):
        kb = loader.regulations()
        self.sources = dict(kb["sources"])
        self.items = [{**it, "kind": "규정 요약"} for it in kb["items"]]
        for fname, kind, prefix, skey, src in KNOWLEDGE:
            if (KNOW / fname).exists():
                self.sources[skey] = src
                self.items += _md_items(fname, kind, prefix, skey)
        syn = loader.load_yaml("search_synonyms.yaml") if (loader.DATA / "search_synonyms.yaml").exists() else {}
        self.synonyms = syn.get("synonyms") or {}
        # 한글은 띄어쓰기가 들쭉날쭉하므로 공백을 지운 뒤 글자 2~3그램으로 비교.
        # 본문이 긴 항목이 불리하지 않도록 제목(+분류) 유사도와 본문 유사도를 섞는다.
        docs = [self._norm(f"{it['title']} {it['category']} {it['article']} {it['text']}") for it in self.items]
        self.vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 3), sublinear_tf=True)
        self.M = self.vec.fit_transform(docs)
        self.T = self.vec.transform([self._norm(f"{it['title']} {it['category']}") for it in self.items])

    @staticmethod
    def _norm(s: str) -> str:
        return re.sub(r"\s+", "", str(s)).lower()

    def expand(self, q: str) -> list[str]:
        """실무 표현 → 규정 용어 (예: 식대 → 회의비, 식비). 질문에 더해 검색한다."""
        qn = self._norm(q)
        add = []
        for k, vs in self.synonyms.items():
            if self._norm(k) in qn:
                add += [v for v in vs if self._norm(v) not in qn and v not in add]
        return add

    def _hit(self, i: int, score: float) -> Hit:
        it = self.items[i]
        src = self.sources.get(it["source"], {})
        flat = " ".join(it["text"].split())
        return Hit(it["id"], it["title"], it["category"], flat, it["article"], src.get("name", it["source"]),
                   src.get("url", ""), float(score), it["kind"], flat if it["kind"] == "규정 요약" else it["text"])

    def search(self, q: str, k: int = 4, kinds: list[str] | None = None) -> tuple[list[Hit], dict]:
        extra = self.expand(q)
        core, boost = q, set()
        for pat, kind in INTENT:
            if re.search(pat, core):
                boost.add(kind)
                core = re.sub(pat, " ", core)
        qv = self.vec.transform([self._norm(" ".join([core if core.strip() else q] + extra))])
        sims = TITLE_W * cosine_similarity(qv, self.T)[0] + (1 - TITLE_W) * cosine_similarity(qv, self.M)[0]
        if boost:
            sims = sims + np.array([INTENT_BONUS if it["kind"] in boost else 0.0 for it in self.items])
        if kinds:
            sims = np.where([it["kind"] in kinds for it in self.items], sims, -1.0)
        order = [i for i in np.argsort(sims)[::-1][:k] if sims[i] >= 0]
        hits = [self._hit(i, sims[i]) for i in order]
        top1 = hits[0].score if hits else 0.0
        margin = top1 - (hits[1].score if len(hits) > 1 else 0.0)
        if top1 >= 0.2 and margin >= 0.03:
            level = "근거 충분"
        elif top1 >= 0.12:
            level = "근거 일부"
        else:
            level = "근거 부족 — 담당자 문의"
        return hits, {"top1": top1, "margin": margin, "level": level, "expanded": extra}

    def by_kind(self, kind: str) -> list[Hit]:
        return [self._hit(i, 0.0) for i, it in enumerate(self.items) if it["kind"] == kind]

    def get(self, rid: str) -> dict | None:
        for it in self.items:
            if it["id"] == rid:
                src = self.sources.get(it["source"], {})
                return {**it, "source_name": src.get("name", ""), "source_url": src.get("url", "")}
        return None
