import re

import altair as alt
import pandas as pd
import streamlit as st

from core import loader, ui

BLUE, TEAL, NAVY = "#005BAC", "#00A0B0", "#0B3B6E"
EOK = 1e8  # 억원

ui.header("지원 › 수탁과제 수행 현황", "수탁과제 수행 현황")


@st.cache_data
def load() -> pd.DataFrame:
    d = loader.load_csv("ongoing_projects.csv")
    for c in ["총 연구 시작", "총 연구 종료", "당해년도 시작", "당해년도 종료"]:
        d[c] = pd.to_datetime(d[c])
    d["당해(억)"] = d["당해년도 연구비"] / EOK
    d["총(억)"] = d["총 연구비"] / EOK
    d["기관"] = d["발주기관"].apply(lambda s: (re.search(r"\(([^)]+)\)", s).group(1) if isinstance(s, str) and "(" in s else s))
    return d


df = load()
years = sorted(df["연도"].unique())
cur = max(years)
d_cur = df[df["연도"] == cur]
d_prev = df[df["연도"] == cur - 1]

# ── KPI ──
amt, amt_p = d_cur["당해(억)"].sum(), d_prev["당해(억)"].sum()
natl = d_cur[d_cur["참여형태"] == "국가연구개발사업"]
ui.card_grid([
    (f"{cur}년 수행 과제", f"{len(d_cur)}건", f"전년 {len(d_prev)}건"),
    ("당해년도 연구비", f"{amt:,.1f}억원", f"전년 대비 {(amt / amt_p - 1):+.1%}"),
    ("총 연구비 (협약 전체)", f"{d_cur['총(억)'].sum():,.1f}억원", f"과제당 평균 {d_cur['총(억)'].mean():,.1f}억원"),
    ("국가연구개발사업", f"{len(natl)}건", f"연구비 비중 {natl['당해(억)'].sum() / amt:.0%}"),
])

# ── 연도별 금액 / 연도×연구소 히트맵 ──
c1, c2 = st.columns([1, 1.5])
with c1:
    ui.section("연도별 연구비 (억원)")
    yr = df.groupby("연도").agg(금액=("당해(억)", "sum"), 건수=("과제명", "count")).reset_index()
    base = alt.Chart(yr).encode(x=alt.X("연도:O", title=None, axis=alt.Axis(labelAngle=0)))
    bars = base.mark_bar(color=BLUE, size=46, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        y=alt.Y("금액:Q", title=None), tooltip=["연도", alt.Tooltip("금액:Q", format=",.1f"), "건수"])
    txt = base.mark_text(dy=-8, fontWeight="bold", color=NAVY).encode(y="금액:Q", text=alt.Text("금액:Q", format=",.1f"))
    st.altair_chart((bars + txt).properties(height=280), width="stretch")
with c2:
    ui.section("연구소 × 연도 히트맵 (당해년도 연구비, 억원)")
    hm = df.groupby(["연구소", "연도"], as_index=False)["당해(억)"].sum()
    order = list(df.groupby("연구소")["당해(억)"].sum().sort_values(ascending=False).index)
    h = alt.Chart(hm).encode(y=alt.Y("연구소:N", sort=order, title=None, axis=alt.Axis(labelLimit=170)), x=alt.X("연도:O", title=None, axis=alt.Axis(labelAngle=0)))
    rect = h.mark_rect(stroke="white").encode(color=alt.Color("당해(억):Q", scale=alt.Scale(range=["#EAF2FB", BLUE]), legend=None),
                                              tooltip=["연구소", "연도", alt.Tooltip("당해(억):Q", format=",.1f")])
    lab = h.mark_text(fontSize=12).encode(text=alt.Text("당해(억):Q", format=",.1f"),
                                           color=alt.condition(alt.datum["당해(억)"] > hm["당해(억)"].max() * 0.5, alt.value("white"), alt.value("#16202C")))
    st.altair_chart((rect + lab).properties(height=280), width="stretch")

# ── 발주기관 / 참여 구성 ──
c3, c4 = st.columns([1.2, 1])
with c3:
    ui.section(f"{cur}년 발주기관별 연구비 (억원)")
    ag = d_cur.groupby("기관").agg(금액=("당해(억)", "sum"), 건수=("과제명", "count")).reset_index().sort_values("금액", ascending=False)
    b = alt.Chart(ag).encode(y=alt.Y("기관:N", sort=list(ag["기관"]), title=None),
                             x=alt.X("금액:Q", title=None))
    st.altair_chart((b.mark_bar(color=TEAL, cornerRadiusEnd=3).encode(tooltip=["기관", alt.Tooltip("금액:Q", format=",.1f"), "건수"])
                     + b.mark_text(align="left", dx=4, color=NAVY).encode(text=alt.Text("금액:Q", format=",.1f"))).properties(height=280),
                    width="stretch")
with c4:
    ui.section(f"{cur}년 참여방법 · 참여형태 (건)")
    mix = d_cur.groupby(["참여형태", "참여방법"]).size().reset_index(name="건수")
    st.altair_chart(alt.Chart(mix).mark_bar().encode(
        y=alt.Y("참여형태:N", title=None, sort="-x"), x=alt.X("건수:Q", title=None),
        color=alt.Color("참여방법:N", scale=alt.Scale(domain=["주관", "공동", "위탁"], range=[NAVY, BLUE, "#9CC3E8"]), legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["참여형태", "참여방법", "건수"]).properties(height=280), width="stretch")

# ── 연구소 × 발주기관 히트맵 ──
ui.section(f"{cur}년 연구소 × 발주기관 (당해년도 연구비, 억원)")
x = d_cur.groupby(["연구소", "기관"], as_index=False).agg(금액=("당해(억)", "sum"), 건수=("과제명", "count"))
ag_order = list(ag["기관"])
h2 = alt.Chart(x).encode(y=alt.Y("연구소:N", sort=order, title=None, axis=alt.Axis(labelLimit=170)), x=alt.X("기관:N", sort=ag_order, title=None, axis=alt.Axis(labelAngle=-30)))
r2 = h2.mark_rect(stroke="white").encode(color=alt.Color("금액:Q", scale=alt.Scale(range=["#E6F6F8", TEAL]), legend=None),
                                          tooltip=["연구소", "기관", alt.Tooltip("금액:Q", format=",.1f"), "건수"])
t2 = h2.mark_text(fontSize=11).encode(text=alt.Text("금액:Q", format=",.1f"),
                                       color=alt.condition(alt.datum["금액"] > x["금액"].max() * 0.55, alt.value("white"), alt.value("#16202C")))
st.altair_chart((r2 + t2).properties(height=300), width="stretch")

# ── 타임라인 ──
ui.section(f"{cur}년 수행 과제 기간")
tl = d_cur.sort_values(["연구소", "총 연구 시작"]).copy()
tl["과제"] = tl["과제명"].str.slice(0, 26) + tl["과제명"].str.len().gt(26).map({True: "…", False: ""})
tl["시작"], tl["종료"] = tl["총 연구 시작"], tl["총 연구 종료"]
today = pd.DataFrame({"t": [pd.Timestamp.today().normalize()]})
g = alt.Chart(tl).mark_bar(height=9, cornerRadius=4).encode(
    y=alt.Y("과제:N", sort=list(tl["과제"]), title=None, axis=alt.Axis(labelLimit=260, labelFontSize=11)),
    x=alt.X("시작:T", title=None), x2="종료:T",
    color=alt.Color("연구소:N", legend=alt.Legend(orient="top", title=None)),
    tooltip=["연구소", "과제명", alt.Tooltip("시작:T", format="%Y-%m-%d"), alt.Tooltip("종료:T", format="%Y-%m-%d"),
             alt.Tooltip("당해(억):Q", format=",.2f", title="당해년도(억)")])
rule = alt.Chart(today).mark_rule(color="#B42318", strokeDash=[4, 3]).encode(x="t:T")
st.altair_chart((g + rule).properties(height=max(300, 17 * len(tl))), width="stretch")

# ── 목록 ──
ui.section("과제 목록")
f1, f2, f3 = st.columns(3)
yy = f1.selectbox("연도", years, index=len(years) - 1)
inst = f2.multiselect("연구소", order, placeholder="전체")
agy = f3.multiselect("발주기관", sorted(df[df["연도"] == yy]["기관"].dropna().unique()), placeholder="전체")
lst = df[df["연도"] == yy]
if inst:
    lst = lst[lst["연구소"].isin(inst)]
if agy:
    lst = lst[lst["기관"].isin(agy)]
show = lst[["연구소", "과제명", "발주기관", "참여방법", "참여형태", "총 연구 시작", "총 연구 종료", "총 연구비", "당해년도 연구비"]]
st.dataframe(show, hide_index=True, width="stretch", height=420,
             column_config={"총 연구 시작": st.column_config.DateColumn("시작", format="YYYY-MM-DD"),
                            "총 연구 종료": st.column_config.DateColumn("종료", format="YYYY-MM-DD"),
                            "총 연구비": st.column_config.NumberColumn("총 연구비(원)", format="localized"),
                            "당해년도 연구비": st.column_config.NumberColumn("당해년도(원)", format="localized"),
                            "과제명": st.column_config.TextColumn(width="large")})
st.caption(f"{len(lst)}건 · 당해년도 {lst['당해(억)'].sum():,.1f}억원")
