"""핵심 로직 회귀 테스트:  python -m pytest -q"""
from datetime import date

import pandas as pd

from core import budget, checks, inkind, loader, mapper, search


def _hm():
    return mapper.HybridMapper(mapper.train_model(loader.load_csv("train_ledger.csv")))


def test_rule_and_ml_agree_on_analysis():
    r = _hm().map_one("5260", "PFAS 의뢰분석 10시료", "한국화학융합시험연구원")
    assert r.semok == "외부 전문기술 활용비" and r.status == "자동확정"


def test_ml_covers_words_without_rule():
    r = _hm().map_one("5240", "에탄올 500mL 구입", "덕산과학")
    assert r.rule is None and r.semok == "연구재료 구입비"


def test_meeting_meal_after_rule_change():
    df = pd.DataFrame([{"date": "2026-06-03", "account": "5220", "description": "내부 회의 식사", "vendor": "",
                        "amount": 150000, "pay_method": "법인카드", "evidence": "카드전표;회의록",
                        "external_attendee": "N", "note": "", "RCMS 비목": "연구활동비", "RCMS 세목": "회의비"}])
    f = checks.run_checks(df, checks.ProjectInfo(date(2025, 1, 1), date(2026, 12, 31), 10**9, 10**8))
    assert "참여연구자만 참석한 회의 식비" in set(f["title"])


def test_inkind_other_national_rnd_flagged():
    row = loader.load_csv("sample_inkind.csv").iloc[3]  # 타 국가R&D 재원 GPU 서버
    assert inkind.evaluate(row, date(2026, 1, 1)).grade == "불인정 위험"


def test_budget_default_passes():
    _, C = budget.evaluate(budget.default_table(), 250_000, 0.5, 0.15, 0.2)
    assert all(c.ok for c in C)


def test_search_finds_meeting_rule():
    hits, _ = search.RegSearch().search("회의비 식대 참여연구원만")
    assert "K03" in [h.id for h in hits[:3]]


def test_store_github_append(monkeypatch, tmp_path):
    """영구 저장소(GitHub) 모드: 접수 시 원격 파일에 행이 추가되고 sha 충돌 시 재시도."""
    import base64
    import requests
    from core import store

    remote = {"content": None, "sha": "s0", "puts": 0, "conflict_once": True}

    class R:
        def __init__(self, code, js=None):
            self.status_code, self._js = code, js or {}
            self.response = self
        def json(self): return self._js
        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(response=self)

    def fake_get(url, **kw):
        if remote["content"] is None:
            return R(404)
        return R(200, {"content": base64.b64encode(remote["content"]).decode(), "sha": remote["sha"]})

    def fake_put(url, **kw):
        if remote["conflict_once"]:
            remote["conflict_once"] = False
            return R(409)
        remote["content"] = base64.b64decode(kw["json"]["content"])
        remote["sha"] = f"s{remote['puts'] + 1}"
        remote["puts"] += 1
        return R(200)

    monkeypatch.setattr(store, "_cfg", lambda: {"repo": "x/y", "token": "t"})
    monkeypatch.setattr(store.requests, "get", fake_get)
    monkeypatch.setattr(store.requests, "put", fake_put)
    monkeypatch.setattr(store, "_local_path", lambda name: tmp_path / name)
    monkeypatch.setattr(store._cached_remote, "clear", lambda: None, raising=False)
    ok, _ = store.append("interviews.csv", {"연구소": "AI연구소", "상황": "테스트"})
    assert ok and remote["puts"] == 1
    ok, _ = store.append("interviews.csv", {"연구소": "물에너지연구소", "상황": "두번째"})
    text = remote["content"].decode("utf-8-sig")
    assert ok and "AI연구소" in text and "물에너지연구소" in text
