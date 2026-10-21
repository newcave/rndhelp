"""Streamlit 캐시 래퍼 — 모델 학습·검색 인덱스는 세션 간 공유."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from . import loader, mapper, search, store

FEEDBACK = loader.DATA / "feedback.csv"
INTERVIEWS = loader.DATA / "interviews.csv"


def read_feedback() -> pd.DataFrame:
    df = store.read("feedback.csv", dtype={"account": str})
    if df.empty:
        return pd.DataFrame(columns=["account", "description", "vendor", "rcms_bimok", "rcms_semok", "ts"])
    return df


def add_feedback(row: dict) -> tuple[bool, str]:
    return store.append("feedback.csv", row)


@st.cache_resource(show_spinner="비목 분류 모델 학습 중…")
def get_mapper(version: int = 0) -> mapper.HybridMapper:
    train = loader.load_csv("train_ledger.csv")
    model = mapper.train_model(train, read_feedback())
    return mapper.HybridMapper(model)


@st.cache_resource
def _search_index(sig: str) -> search.RegSearch:
    return search.RegSearch()


def get_search() -> search.RegSearch:
    """규정·FAQ 파일이나 검색 코드가 바뀌면(sig) 새 인덱스를 만든다 — 배포 후 옛 인덱스가 남는 문제 방지."""
    return _search_index(search.data_signature())


def model_version() -> int:
    """피드백 건수가 바뀌면 모든 사용자에게 새 모델이 쓰이도록 피드백 건수를 버전에 포함."""
    return len(read_feedback()) * 1000 + st.session_state.get("model_version", 0)


def bump_model() -> None:
    st.session_state["model_version"] = model_version() + 1


def read_interviews() -> pd.DataFrame:
    return store.read("interviews.csv")


def add_interview(row: dict) -> tuple[bool, str]:
    return store.append("interviews.csv", row)
