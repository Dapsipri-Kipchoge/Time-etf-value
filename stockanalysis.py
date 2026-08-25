"""StockAnalysis.com 파서 (Forecast + Statistics + Company) → 국장과 동일한 지표 dict
단위: 매출·이익 $M, 시총 $M. 회계연도: FY0 = 최근 확정, FY1 = 당해 추정(E), FY2 = 차기 추정(E)
"""
import re, time
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
           "Accept-Language": "en-US,en;q=0.9"}
BASE = "https://stockanalysis.com/stocks/{t}/{page}/"


def _get(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code == 404:
        raise RuntimeError("404")
    r.raise_for_status()
    return r.text


def to_num(s):
    """'395.23B' '-6.57B' '74.88%' '$6.53' 'n/a' 'Upgrade' → float ($M 단위로 통일)"""
    if s is None: return None
    s = str(s).strip().replace(",", "").replace("$", "").rstrip(".")
    if s in ("", "-", "n/a", "N/A", "Upgrade", "Pro", "—"): return None
    m = re.fullmatch(r"(-?[\d.]+)\s*([TBMK%]?)", s)
    if not m: return None
    v, u = float(m.group(1)), m.group(2)
    return v * {"T": 1e6, "B": 1e3, "M": 1, "K": 1e-3, "%": 1, "": 1}[u]


def _table_rows(soup, must_have):
    """must_have 문자열이 들어있는 table → {첫열: [나머지 열]}"""
    for tbl in soup.select("table"):
        txt = tbl.get_text(" ")
        if all(k in txt for k in must_have):
            rows = {}
            for tr in tbl.select("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
                if len(cells) >= 2:
                    rows[cells[0]] = cells[1:]
            return rows
    return None


def fetch_forecast(t):
    soup = BeautifulSoup(_get(BASE.format(t=t, page="forecast")), "lxml")
    rows = _table_rows(soup, ["Fiscal Year", "Revenue"])
    if not rows: raise RuntimeError("forecast 표 없음")
    years = rows.get("Fiscal Year") or rows.get("Year")
    ends = rows.get("Period Ending", [])
    # 추정연도 판별: No. Analysts 행에 숫자가 있으면 추정
    an = rows.get("No. Analysts", [])
    est_flags = [to_num(a) is not None for a in an] if an else [False] * len(years)
    # 첫 추정연도 인덱스
    try:
        i1 = est_flags.index(True)
    except ValueError:
        raise RuntimeError("추정치 없음")
    i0 = i1 - 1
    def col(name, i):
        r = rows.get(name)
        return to_num(r[i]) if r and i < len(r) and i >= 0 else None
    d = {"FY1": years[i1], "FY0": years[i0] if i0 >= 0 else None}
    for k, name in (("rev", "Revenue"), ("op", "Operating Income"), ("ni", "Net Income"), ("eps", "EPS"), ("fpe_site", "Forward PE")):
        d[f"{k}0"] = col(name, i0); d[f"{k}1"] = col(name, i1); d[f"{k}2"] = col(name, i1 + 1)
    d["rev_1"] = col("Revenue", i0 - 1); d["op_1"] = col("Operating Income", i0 - 1)
    # 요약 카드: Revenue Next Year / EPS Next Year (FY2) — 표가 Pro 잠김일 때 보완
    txt = soup.get_text(" ")
    m = re.search(r"Revenue Next Year\s*([\d.]+[TBMK]?)", txt)
    if m and d.get("rev2") is None: d["rev2"] = to_num(m.group(1))
    m = re.search(r"EPS Next Year\s*(-?[\d.]+)", txt)
    if m and d.get("eps2") is None: d["eps2"] = to_num(m.group(1))
    m = re.search(r"average price target of \$([\d,]+(?:\.\d+)?)", txt)
    d["목표주가"] = to_num(m.group(1)) if m else None
    m = re.search(r"Financial currency is ([A-Z]{3})", txt)
    d["통화"] = m.group(1) if m else "USD"
    return d


def fetch_stats(t):
    soup = BeautifulSoup(_get(BASE.format(t=t, page="statistics")), "lxml")
    txt = soup.get_text(" ")
    def grab(label, pat=r"(-?[\d.,]+[TBMK%]?)"):
        m = re.search(re.escape(label) + r"\s*" + pat, txt)
        return to_num(m.group(1)) if m else None
    name = soup.select_one("h1")
    name = re.sub(r"\s*Statistics.*$", "", name.get_text(strip=True)) if name else t
    price = None
    mp = re.search(r"([\d,]+\.\d{2})\s+[-+][\d.]+\s+\([-+][\d.]+%\)", txt)
    if mp: price = to_num(mp.group(1))
    m = re.search(r"revenue of \$([\d.,]+)\s*(trillion|billion|million)", txt)
    ttm_usd = to_num(m.group(1) + {"trillion": "T", "billion": "B", "million": "M"}[m.group(2)]) if m else None
    shares = grab("Shares Outstanding")
    opm_ttm = grab("Operating Margin")
    if price is None and shares and grab("Market Cap"):
        price = round(grab("Market Cap") / shares, 2)
    return {"기업": name, "현재가": price, "주식수(M)": shares, "TTM매출($M)": ttm_usd, "영업이익률TTM": opm_ttm,
            "시총($M)": grab("Market Cap"), "ROE(E)": grab("Return on Equity (ROE)"),
            "ROIC": grab("Return on Invested Capital (ROIC)"), "WACC": grab("Weighted Average Cost of Capital (WACC)"),
            "배당수익률": grab("Dividend Yield"), "부채자본비율": grab("Debt / Equity"), "fPER(사이트)": grab("Forward PE"),
            "PEG(사이트)": grab("PEG Ratio"), "52주변동": grab("52-Week Price Change")}


def fetch_industry(t):
    try:
        soup = BeautifulSoup(_get(BASE.format(t=t, page="company")), "lxml")
        txt = soup.get_text(" ")
        m = re.search(r"Industry\s*[:\-]?\s*([A-Za-z&,\-/ ]+?)\s{2,}|Industry\s+([A-Za-z&,\-/ ]+?)\s+(?:Sector|Founded|IPO|Employees)", txt)
        return (m.group(1) or m.group(2)).strip() if m else ""
    except Exception:
        return ""


def implied_fx(t, ttm_usd):
    """/revenue/ 페이지 TTM(현지통화) ÷ statistics TTM(USD) = 환율"""
    try:
        txt = BeautifulSoup(_get(BASE.format(t=t, page="revenue")), "lxml").get_text(" ")
        m = re.search(r"last twelve months to ([\d.,]+[TBMK]?)", txt)
        loc = to_num(m.group(1)) if m else None
        return loc / ttm_usd if loc and ttm_usd else None
    except Exception:
        return None


def cagr(cur, base, n):
    if cur is None or base is None or base <= 0 or cur <= 0: return None
    return ((cur / base) ** (1 / n) - 1) * 100


def compute_us(ticker: str) -> dict:
    f = fetch_forecast(ticker); time.sleep(1.0)
    s = fetch_stats(ticker)
    mcap = s["시총($M)"]
    fx = 1.0
    if f.get("통화", "USD") != "USD":
        time.sleep(1.0); fx = implied_fx(ticker, s.get("TTM매출($M)"))
        if not fx: raise RuntimeError(f"{f['통화']} 환율 산출 실패")
        for k in list(f):
            if k[:3] in ("rev", "op0", "op1", "op2", "op_", "ni0", "ni1", "ni2") and isinstance(f[k], (int, float)):
                f[k] = f[k] / fx
    rev0, rev1, rev2, op0, op1, ni1 = f["rev0"], f["rev1"], f["rev2"], f["op0"], f["op1"], f["ni1"]
    fpor = mcap / op1 if mcap and op1 and op1 > 0 else None
    eps1 = f.get("eps1"); price = s.get("현재가")
    if f.get("통화", "USD") != "USD" and eps1:                      # ADR: 표의 EPS가 현지통화 기준이면 환산
        eps1 = eps1 / fx if (price and eps1 / price > 1.0) else eps1  # EPS가 주가보다 크면 현지통화로 판단
    fper = price / eps1 if price and eps1 and eps1 > 0 else None    # non-GAAP 조정 EPS 기준 (사이트 Forward PE와 동일 정의)
    if fper is None and s.get("fPER(사이트)"): fper = s["fPER(사이트)"]
    ni1_adj = mcap / fper if mcap and fper else None
    op_proxy = ""
    if op1 is None and s.get("영업이익률TTM") and rev1:
        op1 = rev1 * s["영업이익률TTM"] / 100; op0 = rev0 * s["영업이익률TTM"] / 100 if rev0 else None
        op_proxy = "영익 컨센 없음→TTM 이익률 대용"
    g_rev1, g_op1 = cagr(rev1, rev0, 1), cagr(op1, op0, 1)
    if op_proxy:
        g_op1 = cagr(f.get("eps1"), f.get("eps0"), 1)   # 대용 시 증가율은 EPS 기준
        if fpor is None and mcap and op1 and op1 > 0: fpor = mcap / op1
    g_rev2 = cagr(rev2, rev0, 2)
    g_eps2 = cagr(f["eps2"], f["eps0"], 2) if f.get("eps2") and f.get("eps0") else None   # 영익 FY2 미제공 → EPS 2y CAGR 대용
    opm1 = op1 / rev1 * 100 if op1 is not None and rev1 else None
    opm0 = op0 / rev0 * 100 if op0 is not None and rev0 else None
    base = op0 is None or op0 <= 0 or (opm0 is not None and opm0 < 3)
    def peg(g): return None if fper is None or g is None or g <= 0 else fper / g
    d = {"종목코드": ticker, **s, "추정연도": f["FY1"], "전년도": f["FY0"],
         "매출(E)": rev1, "영업이익(E)": op1, "순이익(E)": ni1, "순이익(E,조정)": ni1_adj, "EPS(E)": eps1,
         "fPOR": fpor, "fPER": fper,
         "PEG(매출)1y": peg(g_rev1), "PEG(영익)1y": None if base else peg(g_op1),
         "PEG(매출)2y": peg(g_rev2), "PEG(영익)2y": peg(g_eps2), "PEG(영익)3y": None,
         "영업이익률(E)": opm1, "전년영업이익률": opm0,
         "매출증가율1y": g_rev1, "영익증가율1y": g_op1, "목표주가": f["목표주가"],
         "통화": f.get("통화", "USD"), "환율": round(fx, 3) if fx != 1.0 else None,
         "비고": " · ".join(x for x in ["기저효과→PEG(영익)1y 산출불가" if base else "", op_proxy] if x)}
    return d
