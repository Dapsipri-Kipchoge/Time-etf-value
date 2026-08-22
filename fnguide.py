"""FnGuide CompanyGuide 파싱 + 밸류 지표 + 1차 정량필터(국내: 4조건)"""
import io, re
import requests, pandas as pd
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Referer": "https://comp.fnguide.com/"}
URL = ("https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp?pGB=1&gicode=A{code}"
       "&cID=&MenuYn=Y&ReportGB=&NewMenuID=101&stkGb=701")


def to_num(x):
    s = str(x).replace(",", "").replace("%", "").strip()
    if s in ("", "-", "nan", "None", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


_pw = _browser = None
def fetch(code):
    """headless 크롬으로 로드 (브라우저는 1회 생성 후 재사용)"""
    global _pw, _browser
    from playwright.sync_api import sync_playwright
    if _browser is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch()
    pg = _browser.new_page(user_agent=HEADERS["User-Agent"], locale="ko-KR")
    try:
        pg.goto(URL.format(code=code), wait_until="domcontentloaded", timeout=60000)
        try:
            pg.wait_for_selector("table", timeout=15000)
        except Exception:
            pass
        html = pg.content()
        title = pg.title()
    finally:
        pg.close()
    if "highlight" not in html:
        print(f"  [debug] {code} title={title!r} len={len(html)} has_매출액={'매출액' in html}")
    return html


def parse_header(soup):
    name = soup.select_one("#giName")
    name = name.get_text(strip=True) if name else "?"
    text = soup.get_text(" ")
    price = mcap = None
    m = re.search(r"종가/\s*전일대비[^\d]*([\d,]+)", text)
    if m: price = to_num(m.group(1))
    m = (re.search(r"시가총액\s*\(상장예정포함,\s*억원\)\s*([\d,]+)", text)
         or re.search(r"시가총액\s*\(억원\)\s*([\d,]+)", text))
    if m: mcap = to_num(m.group(1))
    return name, price, mcap


def parse_highlight(soup):
    """Financial Highlight 연결/연간 표. id 우선, 없으면 '매출액' 행과 '(E)' 열이 있는 첫 표"""
    cands = []
    node = soup.select_one("#highlight_D_A table")
    if node is not None:
        cands.append(node)
    cands += soup.select("table")
    for tbl in cands:
        txt = tbl.get_text(" ")
        if "매출액" not in txt or "(E)" not in txt:
            continue
        try:
            df = pd.read_html(io.StringIO(str(tbl)))[0]
        except Exception:
            continue
        df.columns = [c[-1] if isinstance(c, tuple) else c for c in df.columns]
        df = df.rename(columns={df.columns[0]: "항목"}).set_index("항목")
        df.index = [re.sub(r"\s+", "", str(i)) for i in df.index]
        df.columns = [re.sub(r"\s+", "", str(c)) for c in df.columns]
        if "매출액" in df.index and any("(E)" in c and "/12" in c for c in df.columns):
            return df
    raise RuntimeError("Financial Highlight 표 없음")


def cagr(cur, base, n):
    if cur is None or base is None or base <= 0 or cur <= 0:
        return None
    return ((cur / base) ** (1 / n) - 1) * 100


def peg(fper, g):
    return None if fper is None or g is None or g <= 0 else fper / g


def compute_stock(code: str) -> dict:
    soup = BeautifulSoup(fetch(code), "lxml")
    name, price, mcap = parse_header(soup)
    hl = parse_highlight(soup)
    years = sorted([c for c in hl.columns if re.fullmatch(r"\d{4}/12(\(E\))?", c)], key=lambda c: c[:4])
    est = [y for y in years if "(E)" in y]
    act = [y for y in years if "(E)" not in y]
    base = {"종목코드": code, "기업": name, "현재가": price, "시총(억)": mcap}
    if not est or len(act) < 1:
        return {**base, "비고": "컨센서스 없음 → 산출불가"}

    def g(row, col):
        return to_num(hl.loc[row, col]) if row in hl.index and col in hl.columns else None

    y0 = est[0]
    rev0, op0 = g("매출액", y0), g("영업이익", y0)
    ni0 = g("지배주주순이익", y0) or g("당기순이익", y0)
    hist = {n: (g("매출액", act[-n]), g("영업이익", act[-n])) for n in (1, 2, 3) if len(act) >= n}
    rev_1, op_1 = hist.get(1, (None, None))

    fpor = mcap / rev0 if mcap and rev0 else None
    fper = mcap / ni0 if mcap and ni0 and ni0 > 0 else None
    opm0 = op0 / rev0 * 100 if op0 is not None and rev0 else None
    opm_1 = op_1 / rev_1 * 100 if op_1 is not None and rev_1 else None
    base_effect = op_1 is None or op_1 <= 0 or (opm_1 is not None and opm_1 < 3)

    pegs = {}
    for n, (r, o) in hist.items():
        pegs[f"PEG(매출){n}y"] = peg(fper, cagr(rev0, r, n))
        pegs[f"PEG(영익){n}y"] = peg(fper, cagr(op0, o, n))
    if base_effect:
        pegs["PEG(영익)1y"] = None

    d = {**base, "fPOR": fpor, "fPER": fper, "fPER(사이트)": g("PER", y0),
         **pegs, "영업이익률(E)": opm0, "ROE(E)": g("ROE", y0),
         "매출증가율1y": cagr(rev0, rev_1, 1), "영익증가율1y": cagr(op0, op_1, 1),
         "배당수익률": g("배당수익률", act[-1]),
         "비고": "기저효과→PEG(영익)1y 산출불가" if base_effect else ""}
    d.update(first_filter(d))
    return d


def first_filter(d: dict) -> dict:
    """국내 1차 정량필터 4조건 (ROIC/WACC 제외). 2개 이상 → 탈락"""
    p1, p2, p3 = d.get("PEG(영익)1y"), d.get("PEG(영익)2y"), d.get("PEG(영익)3y")
    roe = d.get("ROE(E)")
    hits = []
    # ① 단기로 올수록 PEG 악화 (3y→2y→1y 상승)
    if p1 is not None and p2 is not None and p3 is not None and p1 > p2 > p3:
        hits.append("PEG악화추세")
    # ② PEG(영익)1y ≥ 1.0
    if p1 is not None and p1 >= 1.0:
        hits.append("PEG1y≥1.0")
    # ③ ROE < 15%
    if roe is not None and roe < 15:
        hits.append("ROE<15%")
    # ④ 기저효과로 PEG 왜곡, 장기치로도 보완 안 됨
    if "기저효과" in d.get("비고", "") and (p3 is None or p3 >= 1.0):
        hits.append("기저효과미보완")
    return {"탈락조건": ",".join(hits), "1차결과": "탈락" if len(hits) >= 2 else "통과"}
