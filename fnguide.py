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
M_BASIC = "https://m.stock.naver.com/api/stock/{code}/basic"
M_INTEG = "https://m.stock.naver.com/api/stock/{code}/integration"
M_ANNUAL = "https://m.stock.naver.com/api/stock/{code}/finance/annual"
M_REFERER = "https://m.stock.naver.com/domestic/stock/{code}/total"

ITEMS = {"매출액", "영업이익", "당기순이익", "ROE", "PER", "시가배당률", "부채비율"}
_PERIOD = re.compile(r"^20\d{2}[./-]?(0[1-9]|1[0-2])")


def _api_json(url, code):
    h = {**HEADERS, "Accept": "application/json", "Referer": M_REFERER.format(code=code)}
    r = requests.get(url.format(code=code), headers=h, timeout=15)
    r.raise_for_status()
    return r.json()


def _clean_title(t):
    return re.sub(r"\s|\(.*?\)", "", str(t))


def _walk(obj):
    yield obj
    if isinstance(obj, dict):
        for v in obj.values(): yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj: yield from _walk(v)


def _period_label(d):
    """dict에서 기간 라벨 추출: {'yymm':'2026.12','estimate':True} / {'key':'2026.12(E)'} 등"""
    for k in ("yymm", "period", "key", "date", "title", "columnName"):
        v = d.get(k)
        if isinstance(v, str) and _PERIOD.match(v.strip()):
            lab = v.strip()
            if "(E)" not in lab and (d.get("estimate") or d.get("isEstimate") or d.get("consensus")):
                lab += "(E)"
            return lab
    return None


def _row_pairs(row):
    """행 dict 안에서 (기간라벨, 값) 쌍 수집 — dict of dicts / list of dicts / 평면 dict 모두 대응"""
    pairs = {}
    for node in _walk(row):
        if not isinstance(node, dict):
            continue
        lab = _period_label(node)
        if lab:
            for vk in ("value", "val", "amount", "data"):
                if vk in node and not isinstance(node[vk], (dict, list)):
                    pairs[lab.replace("-", ".").replace("/", ".")] = node[vk]
                    break
        else:                                            # 평면형: {"2026.12(E)": "1,234", ...}
            for k, v in node.items():
                if isinstance(k, str) and _PERIOD.match(k.strip()) and not isinstance(v, (dict, list)):
                    pairs[k.strip().replace("-", ".").replace("/", ".")] = v
                elif isinstance(k, str) and _PERIOD.match(k.strip()) and isinstance(v, dict):
                    for vk in ("value", "val"):
                        if vk in v: pairs[k.strip()] = v[vk]; break
    return pairs


def fetch_api_finance(code):
    """모바일 API 연간 재무 → DataFrame(index=항목, columns=연도)  (단위: 억원)"""
    j = _api_json(M_ANNUAL, code)
    rows = {}
    for node in _walk(j):
        if isinstance(node, dict):
            t = node.get("title") or node.get("item") or node.get("name")
            if t and _clean_title(t) in ITEMS:
                p = _row_pairs(node)
                if p:
                    rows.setdefault(_clean_title(t), {}).update(p)
    if not rows:
        top = list(j)[:8] if isinstance(j, dict) else type(j).__name__
        raise RuntimeError(f"annual 구조 미인식 top={top}")
    fin = pd.DataFrame.from_dict(rows, orient="index")
    fin = fin[[c for c in sorted(fin.columns)]]
    return fin


def fetch_api_meta(code):
    name = price = mcap = sec = None
    try:
        b = _api_json(M_BASIC, code)
        for node in _walk(b):
            if isinstance(node, dict):
                name = name or node.get("stockName") or node.get("itemName")
                if price is None:
                    for k in ("closePrice", "currentPrice", "now", "nv"):
                        if node.get(k) is not None:
                            price = to_num(node[k]); break
    except Exception:
        pass
    try:
        it = _api_json(M_INTEG, code)
        kv = {}
        for node in _walk(it):
            if isinstance(node, dict):
                key, val = node.get("code") or node.get("key"), node.get("value")
                if key and val is not None and not isinstance(val, (dict, list)):
                    kv[str(key)] = str(val)
                name = name or node.get("stockName") or node.get("itemName")
                if sec is None:
                    for k in ("industryGroupKor", "industryName", "upjongName", "sectorName"):
                        if node.get(k): sec = str(node[k]); break
        raw = kv.get("marketValue") or kv.get("시총") or kv.get("시가총액") or ""
        m = re.search(r"(?:([\d,]+)\s*조)?\s*([\d,]+)?\s*억?", raw.replace(" ", ""))
        if m and (m.group(1) or m.group(2)):
            mcap = (to_num(m.group(1)) or 0) * 10000 + (to_num(m.group(2)) or 0)
        if price is None and kv.get("closePrice"): price = to_num(kv["closePrice"])
    except Exception:
        pass
    return name, price, mcap, sec


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
    fin = name = price = mcap = naver_sec = None
    err_api = err_html = ""
    try:                                                   # 1차: 모바일 JSON API
        fin = fetch_api_finance(code)
        name, price, mcap, naver_sec = fetch_api_meta(code)
    except Exception as e:
        err_api = f"API:{e}"
    if fin is None or not any("(E)" in c for c in fin.columns):
        try:                                               # 2차: 구 PC HTML
            html = fetch(code)
            fin2, soup = parse_finance(html)
            if fin is None or any("(E)" in c for c in fin2.columns):
                fin = fin2
            name2, price2, mcap2 = parse_header(soup)
            sec_el = soup.select_one("a[href*='sise_group_detail']")
            name, price, mcap = name or name2, price if price is not None else price2, mcap or mcap2
            naver_sec = naver_sec or (sec_el.get_text(strip=True) if sec_el else "")
        except Exception as e:
            err_html = f"HTML:{e}"
    if fin is None:
        raise RuntimeError(f"{err_api} {err_html}".strip())
    naver_sec = naver_sec or ""
    name = name or "?"
    base = {"종목코드": code, "기업": name, "현재가": price, "시총(억)": mcap, "네이버업종": naver_sec}
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
    mcap_note = ""
    if not mcap and fper_site and ni0 and ni0 > 0:          # 시총 못 읽으면 네이버 PER(E)로 역산(예외)
        mcap = fper_site * ni0
        mcap_note = "시총역산;"
    # 직접 산출: 시가총액 ÷ 당해(E) 영업이익 / 순이익  (네이버 기업실적분석, 단위 억원)
    fpor = mcap / op0 if mcap and op0 and op0 > 0 else None
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

    d = {**base, "순이익(E)": ni0, "영업이익(E)": op0, "fPOR": fpor, "fPER": fper, "fPER(사이트)": fper_site,
         **pegs, "영업이익률(E)": opm0, "ROE(E)": g("ROE", y0),
         "매출증가율1y": cagr(rev0, rev_1, 1), "영익증가율1y": cagr(op0, op_1, 1),
         "배당수익률": g("시가배당률", act[-1]), "추정연도": y0, "전년영업이익률": opm_1, "전년도": act[-1],
         "비고": mcap_note + ("기저효과→PEG(영익)1y 산출불가" if base_effect else "")}
    return d


# ───────────────────────── 스크리닝 (단일 기준, 전부 충족 = 통과)
CRITERIA = {"PEG(매출)1y": 1.0, "PEG(영익)": 1.0, "ROE(E)": 10.0, "영업이익률(E)": 10.0, "fPER": 30.0, "전년영업이익률": 5.0}
BASE_GROWTH_CAP = 150.0      # 영익증가율 150% 초과 시 기저효과로 간주


def _ok(x, lo=None, hi=None):
    if x is None or x != x:
        return False
    return (lo is None or x >= lo) and (hi is None or x <= hi)


def screen(d: dict, sector1: str) -> dict:
    g = d.get
    flags, fail = [], []
    peg1, peg2, pegs1 = g("PEG(영익)1y"), g("PEG(영익)2y"), g("PEG(매출)1y")
    base = "기저효과" in (g("비고") or "") or _ok(g("영익증가율1y"), lo=BASE_GROWTH_CAP)
    if base:
        flags.append("기저효과")
    eff = peg2 if base else peg1                 # 유효 PEG(영익): 기저효과면 2y CAGR 기준
    d["유효PEG"] = eff
    fper, fsite, roe, opm = g("fPER"), g("fPER(사이트)"), g("ROE(E)"), g("영업이익률(E)")
    if fper and fsite and fsite > 0 and abs(fper / fsite - 1) > 0.3:
        flags.append("비지배괴리")

    if sector1 == "금융":
        d.update(Type="금융", 탈락조건="영업이익·PEG 기준 부적합(별도 판단)", 플래그=",".join(flags)); return d
    if fper is None and g("순이익(E)") is None:
        d.update(Type="보류", 탈락조건="컨센서스 없음", 플래그=",".join(flags)); return d

    if not _ok(pegs1, hi=CRITERIA["PEG(매출)1y"]): fail.append("PEG매출>1")
    if not _ok(eff, hi=CRITERIA["PEG(영익)"]): fail.append("PEG영익>1")
    if not _ok(roe, lo=CRITERIA["ROE(E)"]): fail.append("ROE<10")
    if not _ok(opm, lo=CRITERIA["영업이익률(E)"]): fail.append("이익률<10")
    if not _ok(fper, lo=0, hi=CRITERIA["fPER"]): fail.append("fPER>30")
    if not _ok(g("전년영업이익률"), lo=CRITERIA["전년영업이익률"]): fail.append("전년이익률<5")
    d.update(Type="통과" if not fail else "탈락", 탈락조건=",".join(fail), 플래그=",".join(flags))
    return d
