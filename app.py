import streamlit as st
from sectors import ORDER
from app_common import CSS, run

st.set_page_config(page_title="TIME ETF 밸류 스크리너 · 국장", layout="wide", initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)

KR_CRITERIA = """
<div class="card"><div class="eyebrow">통과 기준</div>
<p style="margin:6px 0 10px">아래 <b>6개를 전부 충족</b>해야 통과. 섹터 구분 없이 동일 적용. 부족하다고 완화하지 않음.</p>
<table class="t"><thead><tr><th class="l">지표</th><th>기준</th><th class="l">계산</th></tr></thead><tbody>
<tr><td class="l">PEG(매출) 1y</td><td>≤ 1.0</td><td class="l">fPER ÷ 매출증가율(전년 → 당해E, %)</td></tr>
<tr><td class="l">PEG(영익)</td><td>≤ 1.0</td><td class="l">fPER ÷ 영업이익증가율(1y). <b>기저효과</b>면 2y CAGR 기준으로 대체</td></tr>
<tr><td class="l">ROE(E)</td><td>≥ 10%</td><td class="l">네이버 당해 추정 ROE(지배주주)</td></tr>
<tr><td class="l">영업이익률(E)</td><td>≥ 10%</td><td class="l">당해E 영업이익 ÷ 매출</td></tr>
<tr><td class="l">fPER</td><td>≤ 30</td><td class="l">시가총액 ÷ 당해E 순이익</td></tr>
<tr><td class="l">전년 영업이익률</td><td>≥ 5%</td><td class="l"><b>확정 실적</b> 기준(직전 회계연도). 컨센만 좋은 턴어라운드 스토리를 거르는 유일한 과거 지표</td></tr>
</tbody></table></div>

<div class="card"><div class="eyebrow">기저효과 규칙</div>
<p style="margin:6px 0 0">전년 영업이익 ≤ 0, 전년 영업이익률 &lt; 3%, 또는 당해 영익증가율 &gt; 150% 중 하나면 1년 성장률이 왜곡된 것으로 보고 PEG(영익)을 <b>2년 CAGR</b>로 계산. 플래그 <span class="bd flag">기저효과</span> 표시.</p></div>

<div class="card"><div class="eyebrow">판정 라벨</div>
<p style="margin:6px 0 0"><span class="bd pass">통과</span> 5개 전부 충족 &nbsp; <span class="bd fail">탈락</span> 1개 이상 미달(탈락조건 칸에 사유) &nbsp; <span class="bd hold">금융</span> 은행·증권·보험은 영업이익·PEG 개념이 달라 기준 미적용, 별도 판단 &nbsp; <span class="bd keep">보류</span> 컨센서스 없음</p></div>

<div class="card"><div class="eyebrow">플래그 (탈락 사유 아님)</div>
<p style="margin:6px 0 0"><b>기저효과</b> 위 규칙 해당 · <b>비지배괴리</b> 직접 계산 fPER과 네이버 PER(E)가 30% 이상 차이 — 비지배지분·EPS 기준 차이 가능성, 수기 확인 권장</p></div>

<div class="card"><div class="eyebrow">밸류점수 (0~100, 정렬용)</div>
<p style="margin:6px 0 0">모집단 전체 백분위 가중합: 유효PEG 35% · fPER 25% · ROE 20% · 영업이익률 10% · 매출성장 10%. 상대 점수라 통과/탈락과 무관하며 <b>같은 통과 종목끼리 줄 세우는 용도</b>.</p></div>

<div class="card"><div class="eyebrow">데이터</div>
<p style="margin:6px 0 0">모집단: 타임폴리오 국내 ETF 8종 구성종목 합집합(현금·ETF 제외), 매 평일 18:30 수집 · 컨센서스·시총: 네이버증권 기업실적분석 표(당해E) · fPOR = 시총 ÷ 영업이익(E)</p></div>
"""

run(dict(
    result="data/result.csv", holdings_glob="data/holdings_*.csv", watch="data/watchlist.csv",
    order=ORDER, mcap_col="시총(억)",
    eyebrow="TIME ETF · 국내 8종 · 보유종목 밸류 모니터", title="타임폴리오 보유종목 밸류 스크리너 — 국장",
    source_note="타임폴리오 구성종목 + 네이버증권 컨센서스 · fPOR=시총÷영업이익(E) · fPER=시총÷순이익(E) · 개인용",
    mc_slider_label="시총 상한(조원, 0=제한 없음)", mc_slider_max=500, mc_slider_step=5, mc_slider_mult=10000,
    criteria_html=KR_CRITERIA,
))
