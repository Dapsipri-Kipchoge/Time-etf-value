"""컨센서스 소스: 네이버증권(finance.naver.com) 기업실적분석 표
(FnGuide가 해외 IP를 차단해 교체. 파일명은 호환을 위해 유지)
밸류 지표 + 국내 1차 정량필터 4조건
"""
import io, re
import requests, pandas as pd
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Referer": "https://finance.naver.com/"}
URL = "https://finance.naver.com/item/main.naver?code={code}"


def to_num(x):
    s = str(x).replace(",", "").replace("%", "").strip()
    if s in ("", "-", "nan", "None", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch(code):
    r = requests.get(URL.format(code=code), headers=HEADERS, timeout=15)
    r.raise_for_status()
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            txt = r.content.decode(enc)
        except UnicodeDecodeError:
            continue
        if "매출액" in txt:
            return txt
    return r.text


def parse_header(soup):
    name = soup.select_one("div.wrap_company h2 a")
    name = name.get_text(strip=True) if name else "?"
    price = mcap = None
    el = soup.select_one("p.no_today span.blind")
    if el: price = to_num(el.get_text())
    text = soup.get_text(" ")
    # 1) id 셀렉터  2) 텍스트 정규식  3) 상장주식수 × 현재가
    el = soup.select_one("#_market_sum")
    if el: mcap = to_num(re.sub(r"\s", "", el.get_text()))
    if not mcap:
        m = re.search(r"시가총액\s*([\d,\s]+?)\s*억원", text)
        if m: mcap = to_num(re.sub(r"\s", "", m.group(1)))
    if not mcap and price:
        m = re.search(r"상장주식수\s*([\d,]+)", text)
        if m and to_num(m.group(1)):
            mcap = price * to_num(m.group(1)) / 1e8
    if not mcap:
        print(f"  [debug] 시총 파싱 실패: {name}")
    return name, price, mcap


def parse_finance(html):
    """기업실적분석 표를 직접 파싱 → DataFrame(index=항목, columns=연간 연도)"""
    soup = BeautifulSoup(html, "lxml")
    tbl = soup.select_one("table.tb_type1_ifrs") or soup.select_one("div.cop_analysis table")
    if tbl is None:
        print(f"  [debug] title={soup.title.get_text(strip=True) if soup.title else None!r} len={len(html)}")
        raise RuntimeError("기업실적분석 표 없음")
    rows = tbl.select("thead tr")
    if len(rows) < 2:
        raise RuntimeError("thead 구조 다름")
    # 1행: 주요재무정보 | 최근 연간 실적(colspan=N) | 최근 분기 실적(colspan=M)
    n_ann = None
    for th in rows[0].select("th"):
        if "연간" in th.get_text():
            n_ann = int(th.get("colspan", 1))
            break
    if n_ann is None:
        print(f"  [debug] thead0={[th.get_text(strip=True) for th in rows[0].select('th')]}")
        raise RuntimeError("연간 컬럼 없음")
    years = [re.sub(r"\s", "", th.get_text()) for th in rows[1].select("th")][:n_ann]
    data = {}
    for tr in tbl.select("tbody tr"):
        th = tr.select_one("th")
        if th is None:
            continue
        item = re.sub(r"\s|\(.*?\)", "", th.get_text())          # ROE(지배주주)→ROE
        vals = [td.get_text(strip=True) for td in tr.select("td")][:n_ann]
        data[item] = vals + [None] * (n_ann - len(vals))
    fin = pd.DataFrame.from_dict(data, orient="index", columns=years)
    return fin, soup


def cagr(cur, base, n):
    if cur is None or base is None or base <= 0 or cur <= 0:
        return None
    return ((cur / base) ** (1 / n) - 1) * 100


def peg(fper, g):
    return None if fper is None or g is None or g <= 0 else fper / g


def compute_stock(code: str) -> dict:
    html = fetch(code)
    fin, soup = parse_finance(html)
    name, price, mcap = parse_header(soup)
    base = {"종목코드": code, "기업": name, "현재가": price, "시총(억)": mcap}
    years = [c for c in fin.columns if re.fullmatch(r"\d{4}\.\d{2}(\(E\))?", c)]
    est = [y for y in years if "(E)" in y]
    act = [y for y in years if "(E)" not in y]
    if not est or not act:
        return {**base, "비고": "컨센서스 없음 → 산출불가"}

    def g(row, col):
        return to_num(fin.loc[row, col]) if row in fin.index and col in fin.columns else None

    y0 = est[0]
    rev0, op0, ni0 = g("매출액", y0), g("영업이익", y0), g("당기순이익", y0)
    hist = {n: (g("매출액", act[-n]), g("영업이익", act[-n])) for n in (1, 2, 3) if len(act) >= n}
    rev_1, op_1 = hist.get(1, (None, None))

    fper_site = g("PER", y0)
    if not mcap and fper_site and ni0 and ni0 > 0:          # 시총 못 읽으면 네이버 PER(E)로 역산
        mcap = fper_site * ni0
    fpor = mcap / rev0 if mcap and rev0 else None
    fper = mcap / ni0 if mcap and ni0 and ni0 > 0 else None
    opm0 = op0 / rev0 * 100 if op0 is not None and rev0 else None
    opm_1 = op_1 / rev_1 * 100 if op_1 is not None and rev_1 else None
    base_effect = op_1 is None or op_1 <= 0 or (opm_1 is not None and opm_1 < 3)

    pegs = {f"PEG({k}){n}y": None for n in (1, 2, 3) for k in ("매출", "영익")}
    for n, (r, o) in hist.items():
        pegs[f"PEG(매출){n}y"] = peg(fper, cagr(rev0, r, n))
        pegs[f"PEG(영익){n}y"] = peg(fper, cagr(op0, o, n))
    if base_effect:
        pegs["PEG(영익)1y"] = None

    d = {**base, "fPOR": fpor, "fPER": fper, "fPER(사이트)": fper_site,
         **pegs, "영업이익률(E)": opm0, "ROE(E)": g("ROE", y0),
         "매출증가율1y": cagr(rev0, rev_1, 1), "영익증가율1y": cagr(op0, op_1, 1),
         "배당수익률": g("시가배당률", act[-1]), "추정연도": y0,
         "비고": "기저효과→PEG(영익)1y 산출불가" if base_effect else ""}
    d.update(first_filter(d))
    return d


def first_filter(d: dict) -> dict:
    """국내 1차 정량필터 4조건 (ROIC/WACC 제외). 2개 이상 → 탈락"""
    p1, p2, p3 = d.get("PEG(영익)1y"), d.get("PEG(영익)2y"), d.get("PEG(영익)3y")
    roe = d.get("ROE(E)")
    hits = []
    if p1 is not None and p2 is not None and p3 is not None and p1 > p2 > p3:
        hits.append("PEG악화추세")
    if p1 is not None and p1 >= 1.0:
        hits.append("PEG1y≥1.0")
    if roe is not None and roe < 15:
        hits.append("ROE<15%")
    long_peg = p3 if p3 is not None else p2
    if "기저효과" in d.get("비고", "") and (long_peg is None or long_peg >= 1.0):
        hits.append("기저효과미보완")
    return {"탈락조건": ",".join(hits), "1차결과": "탈락" if len(hits) >= 2 else "통과"}
