"""API 없이 매매 기록에서 직접 답을 계산한다.

Claude API 키가 없어도 흔한 질문은 답할 수 있다. 오히려 숫자는 파일에서
그대로 더하므로 더 정확하다. 다루지 못하는 질문은 솔직히 그렇다고 말한다.

말을 알아듣는 일은 nlu.py 가 맡는다. 키워드 하나로 가르던 것을 점수로
바꾸고, 띄어쓰기·조사·오타·줄임말·초성을 견디게 했으며, 기간 표현도
"지난주"에서 "9월 3일부터 10일까지", "열흘", "최근 3개월"까지 넓혔다.
여기서는 그렇게 읽어 낸 뜻에 맞춰 답 문장을 만든다.

바깥과의 약속은 그대로다. answer() 는 규칙으로 답할 수 있으면 답을,
아니면 빈 문자열을 돌려준다. 빈 문자열이면 호출한 쪽에서 API 로 넘기면 된다.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta
from pathlib import Path

VERSION = 3               # rules 판
NEEDS_NLU = 2             # 이 rules.py 가 기대하는 nlu 판

def _옛_nlu_파일() -> str:
    """옆에 한 파일짜리 옛 nlu.py 가 남아 있나. 있으면 그 경로를.

    폴더와 파일이 둘 다 있으면 파이썬은 폴더를 먼저 집으므로 대개 탈은
    없다. 그래도 헷갈림의 씨앗이니 알려는 준다.
    """
    import os
    곁 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nlu.py")
    return 곁 if os.path.isfile(곁) else ""


_옛파일 = _옛_nlu_파일()   # 옆에 남아 있던 옛 nlu.py. 진단에서 알려 준다


def _곁에_있는_nlu():
    """이 파일 옆의 nlu/ 폴더를 경로로 짚어 직접 불러온다.

    같은 폴더에 옛 nlu.py 가 남아 있으면 파이썬은 폴더보다 그 파일을 먼저
    집는다. 지우라고 말해도 잊기 쉬우니, 폴더가 있으면 그쪽을 쓰게 한다.
    """
    import importlib.util
    import os
    import sys

    곁 = os.path.dirname(os.path.abspath(__file__))
    폴더 = os.path.join(곁, "nlu")
    첫장 = os.path.join(폴더, "__init__.py")
    if not os.path.isfile(첫장):
        return None
    자리 = importlib.util.spec_from_file_location(
        "nlu", 첫장, submodule_search_locations=[폴더])
    모듈 = importlib.util.module_from_spec(자리)
    sys.modules["nlu"] = 모듈          # 속의 'from . import text' 가 되게 먼저 등록
    자리.loader.exec_module(모듈)
    return 모듈


try:                      # 패키지 안에서 불려도, 스크립트로 불려도 되게
    from . import nlu
except ImportError:       # pragma: no cover
    import nlu

if getattr(nlu, "VERSION", 1) < NEEDS_NLU:      # pragma: no cover
    _옛파일 = getattr(nlu, "__file__", "") or _옛파일
    _새것 = _곁에_있는_nlu()
    if _새것 is None:
        raise ImportError(
            "말 알아듣는 층이 옛 판입니다.\n"
            f"  지금 잡힌 것: {_옛파일}\n"
            "  이 폴더의 nlu.py 를 지우고, nlu/ 폴더를 통째로 놓아 주세요.\n"
            "  (nlu/__init__.py, text.py, numbers.py, timeframe.py, lexicon.py,\n"
            "   entities.py, intents.py, parse.py, explain.py)")
    nlu = _새것

WON = "원"
MODES = ("실제매매", "가상매매")


def _cell(v) -> str:
    """칸 하나를 문자열로. 머리글보다 칸이 많은 줄은 값이 리스트로 온다."""
    if isinstance(v, (list, tuple)):
        return ",".join(str(x) for x in v if x)
    return "" if v is None else str(v)


def _read(path: Path) -> list:
    """CSV 를 dict 목록으로. 따옴표 안의 쉼표와 어긋난 줄까지 견딘다."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        row = {k: _cell(v) for k, v in r.items() if k is not None}
        if any(v.strip() for v in row.values()):
            rows.append(row)
    return rows


def _num(v) -> float:
    try:
        return float(re.sub(r"[,\s%원]", "", str(v)) or 0)
    except ValueError:
        return 0.0


def _won(v: float) -> str:
    return f"{v:+,.0f}{WON}" if v else f"0{WON}"


def _plain(v: float) -> str:
    return f"{v:,.0f}{WON}"


def _pct(v: float) -> str:
    return f"{v:+.2f}%"


def _spark(values: list) -> str:
    """숫자 몇 개를 한 줄 그림으로. 추세는 눈으로 보는 게 빠르다."""
    bars = "▁▂▃▄▅▆▇█"
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return bars[3] * len(values)
    return "".join(bars[int((v - lo) / (hi - lo) * (len(bars) - 1))] for v in values)


def _kdate(text: str) -> str:
    """'2026-09-11' 을 '9월 11일' 로. 표 밖의 문장에서는 이쪽이 읽기 좋다."""
    m = re.match(r"\s*(\d{4})[-./](\d{1,2})[-./](\d{1,2})", text or "")
    return f"{int(m.group(2))}월 {int(m.group(3))}일" if m else (text or "").strip()


def _name(row: dict) -> str:
    return (row.get("종목명") or row.get("종목코드") or "?").strip()


def _rate(row: dict) -> str:
    r = row.get("수익률") or row.get("평가손익률") or ""
    return f" ({_pct(_num(r))})" if str(r).strip() else ""


def _value(row: dict) -> float:
    """보유 평가금액. 없으면 수량×현재가로 메운다."""
    v = _num(row.get("평가금액"))
    if v:
        return v
    return _num(row.get("수량")) * _num(row.get("현재가") or row.get("평가단가"))


def _minute(stamp: str):
    """'2026-09-17 09:31:00' 에서 분 단위 시각. 없으면 None."""
    got = nlu.when(stamp or "")
    return got[1] if got else None


def _hhmm(stamp: str) -> str:
    return (stamp or "")[11:16]


def _daykey(stamp: str) -> str:
    return (stamp or "")[:10]


_WEEKNAME = "월화수목금토일"


def _weekday_of(stamp: str) -> str:
    got = nlu.when(stamp or "")
    return _WEEKNAME[got[0].weekday()] if got else ""


# ---------------------------------------------------------------- 기록 읽기
def catalog(base: Path) -> tuple:
    """기록에 나오는 종목 목록. 질문에서 종목을 알아보는 데 쓴다."""
    seen = {}
    for mode in MODES:
        for fn in (f"{mode}_보유종목.csv", f"{mode}_거래내역.csv"):
            for row in _read(base / fn):
                name = (row.get("종목명") or "").strip()
                code = (row.get("종목코드") or "").strip()
                key = name or code
                if not key:
                    continue
                cur = seen.get(key)
                if cur is None or (not cur.code and code):
                    seen[key] = nlu.Stock(name, code)
    return tuple(seen.values())


def _rows(base: Path, name: str, period=None, field: str = "") -> list:
    rows = _read(base / name)
    if period is None or not field:
        return rows
    return [r for r in rows if nlu.in_period(r.get(field), period)]


def _daily(base: Path, r: nlu.Reading, period=None) -> list:
    return _rows(base, f"{r.mode}_일별손익.csv", period or r.period, "날짜")


def _ledger(base: Path, r: nlu.Reading, period=None, stocks=True) -> list:
    rows = _rows(base, f"{r.mode}_거래내역.csv", period or r.period, "일시")
    if stocks and r.stocks:
        rows = [x for x in rows
                if any(st.matches(x.get("종목코드"), x.get("종목명")) for st in r.stocks)]
    elif stocks and r.terms:
        rows = [x for x in rows
                if any(t in (x.get("종목코드") or "") + (x.get("종목명") or "")
                       for t in r.terms)]
    if r.side:
        rows = [x for x in rows if r.side in (x.get("구분") or "")]
    return rows


def _journal(base: Path, r: nlu.Reading, period=None) -> list:
    rows = _rows(base, "자동매매_일지.csv", period or r.period, "일시")
    if r.stocks:
        rows = [x for x in rows
                if any(st.matches(x.get("내용")) for st in r.stocks)]
    return rows


def _holdings_rows(base: Path, r: nlu.Reading) -> list:
    rows = _read(base / f"{r.mode}_보유종목.csv")
    if r.stocks:
        rows = [h for h in rows
                if any(st.matches(h.get("종목코드"), h.get("종목명")) for st in r.stocks)]
    return rows


def _pick(rows: list, r: nlu.Reading, value=lambda h: 0.0) -> list:
    """이익·손실 고르기와 '얼마 이상' 조건을 함께 건다."""
    out = rows
    if r.want == "win":
        out = [h for h in out if value(h) > 0]
    elif r.want == "lose":
        out = [h for h in out if value(h) < 0]
    for c in r.constraints:
        if c.kind == "금액":
            out = [h for h in out if c.hit(abs(value(h)))]
        elif c.kind == "비율":
            out = [h for h in out if c.hit(abs(_num(h.get("수익률")
                                                   or h.get("평가손익률"))))]
        elif c.kind == "수량":
            out = [h for h in out if c.hit(_num(h.get("수량")))]
    return out


def _sorted(rows: list, r: nlu.Reading, value=lambda h: 0.0) -> list:
    """정렬 지시가 있으면 그대로, 없으면 큰것부터."""
    if r.order == "오름차순":
        return sorted(rows, key=value)
    if r.order == "최신순":
        return list(reversed(rows))
    if r.order == "오래된순":
        return list(rows)
    return sorted(rows, key=lambda h: -value(h))


def date_scope(question: str) -> tuple:
    """질문이 가리키는 기간. (시작 date, 끝 date, 표시용 이름)

    예전 호출부를 위해 남겨 둔 얼굴이다. 속은 nlu.parse_period 가 한다.
    """
    p = nlu.parse_period(question)
    return p.start, p.end, p.label


# ---------------------------------------------------------------- 손익
def _pnl(base: Path, r: nlu.Reading) -> str:
    """손익. 일별손익 + 보유종목별 평가손익 + 기간 내 매도."""
    label, mode = r.period.label, r.mode
    daily = _rows(base, f"{mode}_일별손익.csv", r.period, "날짜")
    if not daily:
        have = ", ".join(x.get("날짜", "") for x in _read(base / f"{mode}_일별손익.csv")[-3:])
        return (f"{label} 손익 기록이 없습니다.\n"
                f"{mode}_일별손익.csv 의 최근 날짜: {have or '(비어 있음)'}")

    last, first = daily[-1], daily[0]
    ev, rl, cum = (_num(last.get("평가손익")), _num(last.get("실현손익")),
                   _num(last.get("누적손익")))
    out = [_pnl_sentence(label, ev, rl, cum), ""]
    out.append(f"■ {label} 손익 ({last.get('날짜')})")
    out.append(f"  평가손익 {_won(ev)}  (아직 안 판 종목)")
    out.append(f"  실현손익 {_won(rl)}  (판 것으로 확정)")
    out.append(f"  누적손익 {_won(cum)}")
    out.append(f"  총자산 {_plain(_num(last.get('총자산')))}")
    if len(daily) > 1:
        diff = cum - _num(first.get("누적손익"))
        out.append(f"  {label} 동안 변화 {_won(diff)}"
                   f" ({first.get('날짜')} → {last.get('날짜')})")

    holdings = _read(base / f"{mode}_보유종목.csv")
    if holdings:
        out.append("\n■ 보유종목 평가손익")
        for h in sorted(holdings, key=lambda x: _num(x.get("평가손익"))):
            out.append(f"  {_name(h)} {_won(_num(h.get('평가손익')))}{_rate(h)}")

    sells = [x for x in _rows(base, f"{mode}_거래내역.csv", r.period, "일시")
             if "매도" in (x.get("구분") or "")]
    if sells:
        out.append(f"\n■ {label} 매도 {len(sells)}건")
        for x in sells:
            out.append(f"  {_name(x)} {_num(x.get('수량')):,.0f}주 "
                       f"@ {_plain(_num(x.get('단가')))} "
                       f"({(x.get('일시') or '')[11:16]})")
    return "\n".join(out)


def _pnl_sentence(label: str, ev: float, rl: float, cum: float) -> str:
    """머리에 붙는 한 문장. 숫자표를 읽기 전에 결론부터 말해 준다."""
    head = nlu.josa(label, "은는")
    if not rl and not ev:
        return f"{head} 아직 움직임이 없습니다. 누적으로는 {_won(cum)}입니다."
    if not rl:
        flow = "나 있습니다" if ev > 0 else "빠져 있습니다"
        return (f"{head} 확정한 손익 없이, 들고 있는 것에서 {_won(ev)} {flow}. "
                f"누적 {_won(cum)}.")
    verb = "벌었습니다" if rl > 0 else "잃었습니다"
    tail = f" 아직 안 판 것은 {_won(ev)}." if ev else ""
    return f"{head} {_plain(abs(rl))} {verb}.{tail} 누적 {_won(cum)}."


def answer_pnl(base: Path, question: str, mode: str = "실제매매") -> str:
    return _pnl(base, _reading(question, base, mode))


# ---------------------------------------------------------------- 왜
def _label_of(terms: list) -> str:
    """머리말에 쓸 이름. 코드보다 종목명이 읽기 좋다."""
    names = [t for t in terms if not re.fullmatch(r"\d{6}", t)]
    codes = [t for t in terms if re.fullmatch(r"\d{6}", t)]
    if names and codes:
        return f"{names[0]}({codes[0]})"
    return (names or codes or ["?"])[0]


_DECISIVE = ("손절", "익절", "고점대비", "청산", "조건 충족", "매도", "매수",
             "진입", "이탈", "돌파", "신호")


def _why_one(base: Path, r: nlu.Reading, terms: list, label: str) -> str:
    journal = _read(base / "자동매매_일지.csv")
    hits = [x for x in journal if any(t in (x.get("내용") or "") for t in terms)]
    if not hits:
        return (f"일지에서 {nlu.josa(label, '와과')} 관련된 기록을 찾지 못했습니다.\n"
                "손으로 매매했거나, 일지가 시작되기 전일 수 있습니다.")

    decisive = [x for x in hits
                if any(k in (x.get("내용") or "") for k in _DECISIVE)]
    out = [f"■ {label} 관련 기록 {len(hits)}건"]
    for x in (decisive or hits)[-8:]:
        out.append(f"  {x.get('일시')}  {x.get('내용')}")
    if decisive and len(hits) > len(decisive):
        out.append(f"  (판단과 무관한 줄 {len(hits) - len(decisive)}건은 생략)")

    trades = [x for x in _read(base / f"{r.mode}_거래내역.csv")
              if any(t in (x.get("종목코드") or "") + (x.get("종목명") or "")
                     for t in terms)]
    if trades:
        out.append(f"\n■ 체결 {len(trades)}건")
        for x in trades[-6:]:
            out.append(f"  {x.get('일시')}  {x.get('구분')} "
                       f"{_num(x.get('수량')):,.0f}주 @ {_plain(_num(x.get('단가')))}"
                       f" — {x.get('결과')}")
    return "\n".join(out)


def _why(base: Path, r: nlu.Reading) -> str:
    """특정 종목을 왜 사고팔았나. 일지에서 그 종목 줄을 뽑아 보여 준다.

    종목을 짚지 않으면 기간 안의 판단 기록을 모아 보여 준다.
    "오늘 왜 이렇게 깨졌어" 같은 질문이 여기로 온다.
    """
    journal = _read(base / "자동매매_일지.csv")
    if not journal:
        return ("자동매매_일지.csv 가 없습니다.\n"
                "알림이 들어간 stock_kor25.py 를 실행한 뒤부터 쌓입니다.")

    if r.stocks:
        blocks = [_why_one(base, r, list(s.terms), s.label) for s in r.stocks]
        return "\n\n".join(blocks)
    if r.terms:
        return _why_one(base, r, list(r.terms), _label_of(list(r.terms)))

    rows = [x for x in journal if nlu.in_period(x.get("일시"), r.period)]
    decisive = [x for x in rows
                if any(k in (x.get("내용") or "") for k in _DECISIVE)]
    if not decisive:
        return (f"{nlu.josa(r.period.label, '은는')} 판단으로 남은 기록이 없습니다.\n"
                "종목을 짚어 물으면 그 종목 기록만 모아 보여 드립니다. "
                "예: \"삼성전자는 왜 팔았어?\"")
    daily = _rows(base, f"{r.mode}_일별손익.csv", r.period, "날짜")
    머리 = f"{nlu.josa(r.period.label, '은는')} 이런 판단이 있었습니다."
    if daily:
        last = daily[-1]
        머리 = _pnl_sentence(r.period.label, _num(last.get("평가손익")),
                            _num(last.get("실현손익")),
                            _num(last.get("누적손익"))) + " 판단은 이랬습니다."
    out = [머리, "", f"■ {r.period.label} 판단 기록 {len(decisive)}건"]
    for x in decisive[-12:]:
        out.append(f"  {x.get('일시')}  {x.get('내용')}")
    return "\n".join(out)


def answer_why(base: Path, question: str, mode: str = "실제매매",
               terms=()) -> str:
    return _why(base, _reading(question, base, mode, terms))


# ---------------------------------------------------------------- 보유
def _holdings(base: Path, r: nlu.Reading) -> str:
    rows = _read(base / f"{r.mode}_보유종목.csv")
    if not rows:
        return f"{r.mode}_보유종목.csv 가 비어 있습니다. 보유 종목이 없습니다."

    kept = _pick(rows, r, _pl)
    고름 = []
    if r.want == "win":
        고름.append("이익 난 것만")
    elif r.want == "lose":
        고름.append("손실 난 것만")
    고름 += [c.say() for c in r.constraints]
    note = f" ({' · '.join(고름)})" if 고름 else ""
    if not kept:
        return (f"그 조건에 드는 종목이 없습니다. (보유 {len(rows)}종목"
                + (f" · 조건 {' · '.join(고름)}" if 고름 else "") + ")")

    kept = _sorted(kept, r, _pl)
    if r.limit:
        kept = kept[:r.limit]
    total = sum(_num(h.get("평가손익")) for h in kept)
    wins = sum(1 for h in kept if _num(h.get("평가손익")) > 0)
    losses = sum(1 for h in kept if _num(h.get("평가손익")) < 0)

    lead = f"지금 {len(kept)}종목 들고 있고, 평가손익은 합쳐서 {_won(total)}입니다."
    if wins and losses:
        lead += f" {wins}개는 이익, {losses}개는 손실입니다."
    out = [lead, "", f"■ 보유 {len(kept)}종목{note} · 평가손익 합계 {_won(total)}"]
    for h in kept:
        out.append(f"  {_name(h)} {_num(h.get('수량')):,.0f}주 · 평단 "
                   f"{_plain(_num(h.get('평균단가') or h.get('매입단가')))} · "
                   f"{_won(_num(h.get('평가손익')))}{_rate(h)}")
    return "\n".join(out)


def answer_holdings(base: Path, mode: str = "실제매매") -> str:
    return _holdings(base, _reading("보유종목", base, mode))


# ---------------------------------------------------------------- 체결
def _trades(base: Path, r: nlu.Reading) -> str:
    rows = _ledger(base, r)
    label = r.period.label
    if not rows:
        누구 = f" {_label_of(list(r.terms))}" if r.terms else ""
        무엇 = f" {r.side}한" if r.side else ""
        return f"{label}{누구}{무엇} 체결 기록이 없습니다."

    buys = [x for x in rows if "매수" in (x.get("구분") or "")]
    sells = [x for x in rows if "매도" in (x.get("구분") or "")]
    net = (sum(_num(x.get("거래금액")) for x in sells)
           - sum(_num(x.get("거래금액")) for x in buys))
    side = "순매도" if net >= 0 else "순매수"

    lead = (f"{nlu.josa(label, '은는')} {len(rows)}건 체결했습니다. "
            f"매수 {len(buys)}건, 매도 {len(sells)}건이고 {side} {_plain(abs(net))}입니다.")
    out = [lead, "",
           f"■ {label} 체결 {len(rows)}건 (매수 {len(buys)} · 매도 {len(sells)})"]
    for x in rows:
        mark = "매수" if "매수" in (x.get("구분") or "") else "매도"
        ok = "" if "접수" in (x.get("결과") or "") else f" ← {x.get('결과')}"
        out.append(f"  {(x.get('일시') or '')[11:16]} {mark} {_name(x)} "
                   f"{_num(x.get('수량')):,.0f}주 @ {_plain(_num(x.get('단가')))}{ok}")
    out.append(f"  {side} {_plain(abs(net))}")
    return "\n".join(out)


def answer_trades(base: Path, question: str, mode: str = "실제매매") -> str:
    return _trades(base, _reading(question, base, mode))


# ---------------------------------------------------------------- 승률
def _winrate(base: Path, r: nlu.Reading) -> str:
    """승률. 봇이 익절로 판단한 건과 손절로 판단한 건을 센다."""
    label = r.period.label
    journal = _rows(base, "자동매매_일지.csv", r.period, "일시")
    if not journal:
        return f"{label} 일지 기록이 없습니다."
    wins = [x for x in journal if "익절" in (x.get("내용") or "")]
    losses = [x for x in journal if "손절" in (x.get("내용") or "")]
    total = len(wins) + len(losses)
    if not total:
        return (f"{label} 에는 익절·손절로 정리된 매도가 없습니다.\n"
                "(승률은 일지의 '익절'·'손절' 판단을 세어 계산합니다)")

    rate = len(wins) / total * 100
    mood = ("다 이겼습니다." if not losses else
            "다 졌습니다." if not wins else
            "괜찮은 편입니다." if rate >= 60 else
            "반반입니다." if rate >= 40 else "좋지 않습니다.")
    out = [f"{nlu.josa(label, '은는')} {len(wins)}승 {len(losses)}패, "
           f"승률 {rate:.1f}%입니다. {mood}", "",
           f"■ {label} 승률 {rate:.1f}% (익절 {len(wins)} · 손절 {len(losses)})"]
    for x in sorted(wins + losses, key=lambda v: v.get("일시") or "")[-8:]:
        out.append(f"  {x.get('일시')}  {x.get('내용')}")
    return "\n".join(out)


def answer_winrate(base: Path, question: str) -> str:
    return _winrate(base, _reading(question, base))


# ---------------------------------------------------------------- 순위
def _ranking(base: Path, r: nlu.Reading) -> str:
    rows = _read(base / f"{r.mode}_보유종목.csv")
    if not rows:
        return (f"{r.mode}_보유종목.csv 가 비어 있어 순위를 낼 수 없습니다.\n"
                "이미 판 종목의 성적은 \"승률\" 이나 \"체결 내역\" 으로 보세요.")
    rows = sorted(rows, key=lambda h: -_num(h.get("평가손익")))
    good = [h for h in rows if _num(h.get("평가손익")) > 0]
    bad = [h for h in rows if _num(h.get("평가손익")) < 0]
    n = max(1, r.limit or 3)
    best, worst = rows[0], rows[-1]

    lead = (f"들고 있는 것 중에는 {nlu.josa(_name(best), '이가')} 제일 낫습니다"
            f" ({_won(_num(best.get('평가손익')))}).")
    if bad and worst is not best:
        lead += (f" 반대로 {nlu.josa(_name(worst), '이가')} 가장 아픕니다"
                 f" ({_won(_num(worst.get('평가손익')))}).")

    def 줄(목록):
        return [f"  {i}. {_name(h)} {_won(_num(h.get('평가손익')))}{_rate(h)}"
                for i, h in enumerate(목록, 1)]

    out = [lead, "", "■ 잘하고 있는 쪽"]
    out += 줄(good[:n]) or ["  이익 난 종목이 없습니다"]
    out.append("■ 발목 잡는 쪽")
    out += 줄(bad[::-1][:n]) or ["  손실 난 종목이 없습니다"]
    out.append("  (보유 종목의 평가손익 기준입니다. 이미 판 것은 승률·체결 내역에서 보세요)")
    return "\n".join(out)


def answer_ranking(base: Path, question: str, mode: str = "실제매매") -> str:
    return _ranking(base, _reading(question, base, mode))


# ---------------------------------------------------------------- 자산
def _asset(base: Path, r: nlu.Reading) -> str:
    daily = _read(base / f"{r.mode}_일별손익.csv")
    if not daily:
        return f"{r.mode}_일별손익.csv 가 비어 있어 자산을 알 수 없습니다."
    last = daily[-1]
    total = _num(last.get("총자산"))
    held = sum(_value(h) for h in _read(base / f"{r.mode}_보유종목.csv"))

    lead = f"지금 총자산은 {_plain(total)}입니다."
    scoped = [x for x in daily if nlu.in_period(x.get("날짜"), r.period)]
    if len(scoped) > 1:
        diff = _num(scoped[-1].get("총자산")) - _num(scoped[0].get("총자산"))
        verb = "늘었습니다" if diff >= 0 else "줄었습니다"
        lead += f" {r.period.label} 동안 {_plain(abs(diff))} {verb}."

    out = [lead, "", f"■ 자산 ({last.get('날짜')})",
           f"  총자산 {_plain(total)}",
           f"  누적손익 {_won(_num(last.get('누적손익')))}"]
    if held:
        out.append(f"  보유 평가금액 {_plain(held)}")
        if total:
            out.append(f"  현금(추정) {_plain(total - held)}"
                       f" · 주식 비중 {held / total * 100:.1f}%")
    return "\n".join(out)


def answer_asset(base: Path, question: str, mode: str = "실제매매") -> str:
    return _asset(base, _reading(question, base, mode))


# ---------------------------------------------------------------- 추세
def _trend(base: Path, r: nlu.Reading) -> str:
    rows = _rows(base, f"{r.mode}_일별손익.csv", r.period, "날짜")
    if len(rows) < 2:
        rows = _read(base / f"{r.mode}_일별손익.csv")[-7:]
    if len(rows) < 2:
        return "흐름을 그리려면 이틀치 이상이 필요한데, 기록이 모자랍니다."

    cums = [_num(x.get("누적손익")) for x in rows]
    diff = cums[-1] - cums[0]
    verb = "좋아지고 있습니다" if diff > 0 else "나빠지고 있습니다" if diff < 0 else "제자리입니다"
    lead = (f"{_kdate(rows[0].get('날짜'))}부터 {_kdate(rows[-1].get('날짜'))}까지 "
            f"누적손익이 {_won(cums[0])}에서 "
            f"{nlu.josa(_won(cums[-1]), '로으로')} {_won(diff)} 움직였습니다. {verb}.")

    out = [lead, "", f"■ 일별 누적손익  {_spark(cums)}"]
    prev = None
    for x in rows[-14:]:
        cum = _num(x.get("누적손익"))
        step = "" if prev is None else f"  ({_won(cum - prev):>12s})"
        out.append(f"  {(x.get('날짜') or '')[:10]}  {_won(cum):>14s}{step}")
        prev = cum
    ups = sum(1 for a, b in zip(cums, cums[1:]) if b > a)
    downs = sum(1 for a, b in zip(cums, cums[1:]) if b < a)
    out.append(f"  오른 날 {ups} · 내린 날 {downs}")
    return "\n".join(out)


def answer_trend(base: Path, question: str, mode: str = "실제매매") -> str:
    return _trend(base, _reading(question, base, mode))


# ---------------------------------------------------------------- 종목 하나
def _stock_one(base: Path, r: nlu.Reading, s: nlu.Stock) -> str:
    terms = [t for t in s.terms] or [s.label]
    out = [f"■ {s.label}"]

    held = [h for h in _read(base / f"{r.mode}_보유종목.csv")
            if any(t in (h.get("종목코드") or "") + (h.get("종목명") or "")
                   for t in terms)]
    if held:
        h = held[0]
        out.append(f"  보유    {_num(h.get('수량')):,.0f}주 · 평단 "
                   f"{_plain(_num(h.get('평균단가') or h.get('매입단가')))} · "
                   f"평가손익 {_won(_num(h.get('평가손익')))}{_rate(h)}")
    else:
        out.append("  보유    지금은 들고 있지 않습니다")

    trades = [x for x in _read(base / f"{r.mode}_거래내역.csv")
              if any(t in (x.get("종목코드") or "") + (x.get("종목명") or "")
                     for t in terms)]
    if trades:
        out.append(f"  체결    {len(trades)}건")
        for x in trades[-4:]:
            out.append(f"    {x.get('일시')}  {x.get('구분')} "
                       f"{_num(x.get('수량')):,.0f}주 @ {_plain(_num(x.get('단가')))}")

    journal = [x for x in _read(base / "자동매매_일지.csv")
               if any(t in (x.get("내용") or "") for t in terms)]
    if journal:
        out.append("  일지")
        for x in journal[-3:]:
            out.append(f"    {x.get('일시')}  {x.get('내용')}")
    if not held and not trades and not journal:
        out.append("  기록에서 이 종목을 찾지 못했습니다")
    return "\n".join(out)


def _stock(base: Path, r: nlu.Reading) -> str:
    stocks = r.stocks
    if not stocks and r.terms:        # 부르는 쪽에서 종목을 직접 넘겨 준 경우
        names = [t for t in r.terms if not re.fullmatch(r"\d{6}", t)]
        codes = [t for t in r.terms if re.fullmatch(r"\d{6}", t)]
        stocks = (nlu.Stock(names[0] if names else "", codes[0] if codes else ""),)
    if not stocks:
        return ""
    r = r._replace(stocks=stocks)
    blocks = [_stock_one(base, r, s) for s in stocks]
    if len(stocks) == 1:
        하나 = stocks[0]
        head = f"{nlu.josa(하나.name or 하나.code, '은는')} 이렇습니다."
    else:
        head = "물어보신 종목들입니다."
    tail = f'  (판단 이유가 궁금하면 "{stocks[0].name or stocks[0].code} 왜 샀어?")'
    return "\n\n".join([head] + blocks) + "\n" + tail


def answer_stock(base: Path, question: str, mode: str = "실제매매") -> str:
    return _stock(base, _reading(question, base, mode))


# ---------------------------------------------------------------- 한눈에
def _summary(base: Path, r: nlu.Reading) -> str:
    label, mode = r.period.label, r.mode
    daily = _rows(base, f"{mode}_일별손익.csv", r.period, "날짜")
    holdings = _read(base / f"{mode}_보유종목.csv")
    trades = _rows(base, f"{mode}_거래내역.csv", r.period, "일시")
    journal = _rows(base, "자동매매_일지.csv", r.period, "일시")

    if not (daily or holdings or trades or journal):
        return (f"{label} 기록이 하나도 없습니다.\n"
                f"{mode} 파일들이 있는 폴더가 맞는지 확인해 보세요.")

    out = []
    if daily:
        last = daily[-1]
        out += [_pnl_sentence(label, _num(last.get("평가손익")),
                              _num(last.get("실현손익")),
                              _num(last.get("누적손익"))), ""]
    out.append(f"■ {label} 한눈에")
    if daily:
        last = daily[-1]
        out.append(f"  손익    실현 {_won(_num(last.get('실현손익')))} · "
                   f"평가 {_won(_num(last.get('평가손익')))} · "
                   f"누적 {_won(_num(last.get('누적손익')))}")
        out.append(f"  자산    {_plain(_num(last.get('총자산')))}")
        if len(daily) > 1:
            diff = _num(last.get("누적손익")) - _num(daily[0].get("누적손익"))
            out.append(f"  변화    {label} 동안 {_won(diff)}  "
                       f"{_spark([_num(x.get('누적손익')) for x in daily])}")
    if holdings:
        tot = sum(_num(h.get("평가손익")) for h in holdings)
        rank = sorted(holdings, key=lambda h: -_num(h.get("평가손익")))
        tail = f" · 최고 {_name(rank[0])} · 최저 {_name(rank[-1])}" if len(rank) > 1 else ""
        out.append(f"  보유    {len(holdings)}종목 · 평가손익 {_won(tot)}{tail}")
    else:
        out.append("  보유    없음")
    buys = sum(1 for x in trades if "매수" in (x.get("구분") or ""))
    sells = sum(1 for x in trades if "매도" in (x.get("구분") or ""))
    out.append(f"  체결    {len(trades)}건 (매수 {buys} · 매도 {sells})")
    wins = sum(1 for x in journal if "익절" in (x.get("내용") or ""))
    losses = sum(1 for x in journal if "손절" in (x.get("내용") or ""))
    if wins or losses:
        out.append(f"  승률    {wins}승 {losses}패 "
                   f"({wins / (wins + losses) * 100:.1f}%)")

    out.append('\n  더 자세히 보려면 "보유종목", "체결 내역", "왜 팔았어?" 처럼 물어보세요.')
    return "\n".join(out)


def answer_summary(base: Path, question: str, mode: str = "실제매매") -> str:
    return _summary(base, _reading(question, base, mode))


def _widen(r: nlu.Reading, days: int = 7) -> nlu.Reading:
    """기간을 안 적은 물음은 오늘 하루만 봐서는 답이 안 된다. 넓혀서 본다."""
    if r.period.explicit:
        return r
    if days <= 0:
        return r._replace(period=nlu.ALL)
    끝 = r.period.end or datetime.now().date()
    시작 = 끝 - timedelta(days=days - 1)
    넓힌 = r.period._replace(start=시작, end=끝, label=f"최근 {days}일", kind="range",
                           explicit=False)
    return r._replace(period=넓힌)


# ---------------------------------------------------------------- 견주기
def _pl(h) -> float:
    return _num(h.get("평가손익"))


def _amt(x) -> float:
    return _num(x.get("거래금액")) or _num(x.get("수량")) * _num(x.get("단가"))


def _slice(base: Path, r: nlu.Reading, p) -> dict:
    """기간 한 토막의 숫자를 모은다. 견주기와 평균이 함께 쓴다."""
    daily = _daily(base, r, p)
    ledger = _rows(base, f"{r.mode}_거래내역.csv", p, "일시")
    journal = _rows(base, "자동매매_일지.csv", p, "일시")
    익절 = sum(1 for x in journal if "익절" in (x.get("내용") or ""))
    손절 = sum(1 for x in journal if "손절" in (x.get("내용") or ""))
    누적 = [_num(x.get("누적손익")) for x in daily]
    return {
        "일수": len(daily),
        "실현": sum(_num(x.get("실현손익")) for x in daily),
        "누적변화": (누적[-1] - 누적[0]) if len(누적) > 1 else (누적[0] if 누적 else 0.0),
        "끝누적": 누적[-1] if 누적 else 0.0,
        "총자산": _num(daily[-1].get("총자산")) if daily else 0.0,
        "체결": len(ledger),
        "매수": sum(1 for x in ledger if "매수" in (x.get("구분") or "")),
        "매도": sum(1 for x in ledger if "매도" in (x.get("구분") or "")),
        "익절": 익절, "손절": 손절,
        "승률": (익절 / (익절 + 손절) * 100) if (익절 + 손절) else None,
    }


def _compare(base: Path, r: nlu.Reading) -> str:
    기준 = r.baseline or nlu.previous_span(r.period)
    if 기준 is None:
        return "견줄 기간을 잡을 수 없습니다. \"지난주 대비 이번주\" 처럼 물어보세요."
    앞, 뒤 = _slice(base, r, 기준), _slice(base, r, r.period)
    if not (앞["일수"] or 뒤["일수"]):
        return f"{기준.label} 과 {r.period.label} 모두 기록이 없습니다."

    차 = 뒤["실현"] - 앞["실현"]
    낫다 = "나아졌습니다" if 차 > 0 else "나빠졌습니다" if 차 < 0 else "비슷합니다"
    머리 = (f"{nlu.josa(r.period.label, '은는')} {기준.label}보다 {낫다}. "
            f"실현손익 {_won(앞['실현'])} → {_won(뒤['실현'])} ({_won(차)}).")

    def 줄(이름, a, b, 꼴=_won, 단위="", 소수=0):
        if a is None and b is None:
            return None
        a = a or 0; b = b or 0
        폭 = _won(b - a) if 꼴 is _won else f"{b - a:+,.{소수}f}{단위}"
        return f"  {이름:8s} {꼴(a):>14s} → {꼴(b):>14s}   ({폭})"

    out = [머리, "", f"■ {기준.label} vs {r.period.label}"]
    for 줄값 in (줄("실현손익", 앞["실현"], 뒤["실현"]),
               줄("누적변화", 앞["누적변화"], 뒤["누적변화"]),
               줄("총자산", 앞["총자산"], 뒤["총자산"], _plain),
               줄("체결", 앞["체결"], 뒤["체결"], lambda v: f"{v:,.0f}건", "건"),
               줄("승률", 앞["승률"], 뒤["승률"], lambda v: f"{v:.1f}%", "%p", 1)):
        if 줄값:
            out.append(줄값)
    out.append(f"  ({기준.start}~{기준.end} 과 {r.period.start}~{r.period.end} 를 견줬습니다)")
    return "\n".join(out)


# ---------------------------------------------------------------- 평균
def _average(base: Path, r: nlu.Reading) -> str:
    r = _widen(r, 7)
    토막 = _slice(base, r, r.period)
    일수 = 토막["일수"] or max(r.period.days, 1)
    if not 토막["일수"] and not 토막["체결"]:
        return f"{r.period.label} 기록이 없어 평균을 낼 수 없습니다."

    하루 = 토막["실현"] / 일수
    머리 = (f"{nlu.josa(r.period.label, '은는')} 하루 평균 {_won(하루)} 입니다. "
            f"({일수}일 동안 합계 {_won(토막['실현'])})")
    out = [머리, "", f"■ {r.period.label} 평균",
           f"  하루 평균 손익   {_won(하루)}",
           f"  하루 평균 체결   {토막['체결'] / 일수:.1f}건"]

    ledger = _ledger(base, r, stocks=False)
    매수 = [x for x in ledger if "매수" in (x.get("구분") or "")]
    매도 = [x for x in ledger if "매도" in (x.get("구분") or "")]
    if 매수:
        out.append(f"  매수 건당 금액   {_plain(sum(_amt(x) for x in 매수) / len(매수))}")
    if 매도:
        out.append(f"  매도 건당 금액   {_plain(sum(_amt(x) for x in 매도) / len(매도))}")
    holdings = _read(base / f"{r.mode}_보유종목.csv")
    비율 = [_num(h.get("수익률") or h.get("평가손익률")) for h in holdings
           if str(h.get("수익률") or h.get("평가손익률") or "").strip()]
    if 비율:
        out.append(f"  보유 평균 수익률 {sum(비율) / len(비율):+.2f}%")
    if 토막["승률"] is not None:
        out.append(f"  승률             {토막['승률']:.1f}%")
    return "\n".join(out)


# ---------------------------------------------------------------- 시간대·요일
def _daypart(base: Path, r: nlu.Reading) -> str:
    r = _widen(r, 30)
    ledger = _ledger(base, r, stocks=False)
    journal = _rows(base, "자동매매_일지.csv", r.period, "일시")
    if not ledger and not journal:
        return f"{r.period.label} 체결·일지 기록이 없어 시간대를 볼 수 없습니다."

    요일로 = any(k in nlu.squash(r.raw) for k in ("요일", "무슨날"))
    def 칸(stamp):
        if 요일로:
            return _weekday_of(stamp) + "요일"
        m = _minute(stamp)
        return f"{m // 60:02d}시" if m is not None else "시각 없음"

    통 = {}
    for x in ledger:
        key = 칸(x.get("일시"))
        칸값 = 통.setdefault(key, {"체결": 0, "익절": 0, "손절": 0})
        칸값["체결"] += 1
    for x in journal:
        key = 칸(x.get("일시"))
        칸값 = 통.setdefault(key, {"체결": 0, "익절": 0, "손절": 0})
        if "익절" in (x.get("내용") or ""):
            칸값["익절"] += 1
        if "손절" in (x.get("내용") or ""):
            칸값["손절"] += 1
    if not 통:
        return f"{r.period.label} 에는 시각이 적힌 기록이 없습니다."

    def 점수(v):
        총 = v["익절"] + v["손절"]
        return (v["익절"] / 총) if 총 else -1

    좋은 = max(통.items(), key=lambda kv: (점수(kv[1]), kv[1]["체결"]))
    이름 = "요일" if 요일로 else "시간대"
    머리 = (f"{nlu.josa(r.period.label, '은는')} {좋은[0]} 성적이 가장 좋습니다."
            if 점수(좋은[1]) >= 0 else
            f"{nlu.josa(r.period.label, '은는')} {이름}별로 이렇게 움직였습니다.")
    out = [머리, "", f"■ {이름}별 ({r.period.label})"]
    for key in sorted(통):
        v = 통[key]
        총 = v["익절"] + v["손절"]
        성적 = f" · {v['익절']}승 {v['손절']}패" if 총 else ""
        out.append(f"  {key}  체결 {v['체결']}건{성적}")
    return "\n".join(out)


# ---------------------------------------------------------------- 낙폭
def _drawdown(base: Path, r: nlu.Reading) -> str:
    r = _widen(r, 0)
    daily = _daily(base, r)
    if len(daily) < 2:
        daily = _read(base / f"{r.mode}_일별손익.csv")
    if len(daily) < 2:
        return "낙폭을 보려면 이틀치 이상이 필요한데, 기록이 모자랍니다."

    고점, 최대낙폭, 고점날, 바닥날 = None, 0.0, "", ""
    for x in daily:
        cum = _num(x.get("누적손익"))
        if 고점 is None or cum > 고점:
            고점, 이번고점날 = cum, x.get("날짜")
        낙폭 = cum - 고점
        if 낙폭 < 최대낙폭:
            최대낙폭, 고점날, 바닥날 = 낙폭, 이번고점날, x.get("날짜")

    나쁜날 = min(daily, key=lambda x: _num(x.get("실현손익")))
    if 최대낙폭 == 0:
        머리 = "고점에서 밀린 적이 없습니다. 누적손익이 줄곧 위를 봤습니다."
    else:
        머리 = (f"최대 낙폭은 {_won(최대낙폭)} 입니다. "
                f"{_kdate(고점날)} 고점에서 {_kdate(바닥날)} 까지 밀렸습니다.")
    out = [머리, "", "■ 낙폭",
           f"  최대 낙폭   {_won(최대낙폭)}",
           f"  가장 나쁜 날 {_kdate(나쁜날.get('날짜'))} "
           f"실현 {_won(_num(나쁜날.get('실현손익')))}",
           f"  누적손익 흐름 {_spark([_num(x.get('누적손익')) for x in daily])}"]
    return "\n".join(out)


# ---------------------------------------------------------------- 연속
def _streak(base: Path, r: nlu.Reading) -> str:
    r = _widen(r, 0)
    journal = _rows(base, "자동매매_일지.csv", r.period, "일시")
    판정 = []
    for x in sorted(journal, key=lambda v: v.get("일시") or ""):
        내용 = x.get("내용") or ""
        if "익절" in 내용:
            판정.append((True, x))
        elif "손절" in 내용:
            판정.append((False, x))
    if not 판정:
        return (f"{r.period.label} 에는 익절·손절로 정리된 매도가 없어 "
                "연승·연패를 셀 수 없습니다.")

    현재, 최장승, 최장패, 이어짐 = 0, 0, 0, None
    for 이김, _ in 판정:
        if 이어짐 is None or 이김 == 이어짐:
            현재 += 1
        else:
            현재 = 1
        이어짐 = 이김
        if 이김:
            최장승 = max(최장승, 현재)
        else:
            최장패 = max(최장패, 현재)
    말 = "연승" if 이어짐 else "연패"
    out = [f"지금 {현재}{말} 중입니다. "
           f"({r.period.label} 기준 최장 {최장승}연승 · {최장패}연패)", "",
           f"■ 최근 판정 {min(len(판정), 10)}건"]
    for 이김, x in 판정[-10:]:
        out.append(f"  {'O' if 이김 else 'X'}  {x.get('일시')}  {x.get('내용')}")
    return "\n".join(out)


# ---------------------------------------------------------------- 보유 기간
def _holding_period(base: Path, r: nlu.Reading) -> str:
    ledger = _rows(base, f"{r.mode}_거래내역.csv", nlu.ALL, "일시")
    if not ledger:
        return "거래내역이 없어 보유 기간을 셀 수 없습니다."
    묶음 = {}
    for x in ledger:
        이름 = _name(x)
        칸 = 묶음.setdefault(이름, {"매수": [], "매도": []})
        쪽 = "매수" if "매수" in (x.get("구분") or "") else "매도"
        got = nlu.when(x.get("일시") or "")
        if got:
            칸[쪽].append(got[0])
    보유중 = {_name(h) for h in _read(base / f"{r.mode}_보유종목.csv")}
    오늘 = datetime.now().date()

    줄들, 날수들 = [], []
    for 이름, 칸 in 묶음.items():
        if r.stocks and not any(st.matches(이름) for st in r.stocks):
            continue
        if not 칸["매수"]:
            continue
        첫 = min(칸["매수"])
        끝 = max(칸["매도"]) if 칸["매도"] else 오늘
        날 = (끝 - 첫).days
        날수들.append(날)
        꼬리 = " (아직 보유 중)" if 이름 in 보유중 or not 칸["매도"] else ""
        줄들.append(f"  {이름}  {날}일  ({첫} → {끝}){꼬리}")
    if not 줄들:
        return "보유 기간을 셀 만한 매수 기록이 없습니다."

    평균 = sum(날수들) / len(날수들)
    out = [f"평균 보유 기간은 {평균:.1f}일입니다. "
           f"(가장 길게는 {max(날수들)}일, 짧게는 {min(날수들)}일)", "",
           "■ 종목별 보유 기간"] + sorted(줄들)
    return "\n".join(out)


# ---------------------------------------------------------------- 비용
_FEE_RATE, _TAX_RATE = 0.00015, 0.0018


def _cost(base: Path, r: nlu.Reading) -> str:
    ledger = _ledger(base, r, stocks=False)
    if not ledger:
        return f"{r.period.label} 체결 기록이 없습니다."
    적힌 = sum(_num(x.get("수수료")) + _num(x.get("세금")) for x in ledger)
    매수액 = sum(_amt(x) for x in ledger if "매수" in (x.get("구분") or ""))
    매도액 = sum(_amt(x) for x in ledger if "매도" in (x.get("구분") or ""))
    어림 = (매수액 + 매도액) * _FEE_RATE + 매도액 * _TAX_RATE

    if 적힌:
        머리 = f"{nlu.josa(r.period.label, '은는')} 수수료·세금으로 {_plain(적힌)} 나갔습니다."
    else:
        머리 = (f"기록에 수수료 칸이 없어 요율로 어림잡았습니다. "
                f"{nlu.josa(r.period.label, '은는')} 약 {_plain(어림)} 입니다.")
    out = [머리, "", f"■ {r.period.label} 비용",
           f"  매수 대금   {_plain(매수액)}",
           f"  매도 대금   {_plain(매도액)}"]
    if 적힌:
        out.append(f"  기록된 비용 {_plain(적힌)}")
    out.append(f"  어림 수수료 {_plain((매수액 + 매도액) * _FEE_RATE)}"
               f"  (양쪽 {_FEE_RATE * 100:.3f}%)")
    out.append(f"  어림 거래세 {_plain(매도액 * _TAX_RATE)}"
               f"  (매도분 {_TAX_RATE * 100:.2f}%)")
    return "\n".join(out)


# ---------------------------------------------------------------- 본전
def _breakeven(base: Path, r: nlu.Reading) -> str:
    rows = _holdings_rows(base, r)
    if not rows:
        return ("지금 들고 있는 종목이 없어 본전을 따질 것이 없습니다."
                if not r.stocks else
                f"{_label_of(list(r.terms))} 은 지금 보유하고 있지 않습니다.")
    out = []
    아픈것 = []
    for h in rows:
        평단 = _num(h.get("평균단가") or h.get("매입단가"))
        현재 = _num(h.get("현재가")) or (
            평단 + (_pl(h) / _num(h.get("수량")) if _num(h.get("수량")) else 0))
        필요 = ((평단 - 현재) / 현재 * 100) if 현재 else 0.0
        상태 = ("이미 본전을 넘었습니다" if 필요 <= 0
                else f"{필요:+.2f}% 더 올라야 본전입니다")
        out.append(f"  {_name(h)}  평단 {_plain(평단)} · 지금 {_plain(현재)} · {상태}")
        if 필요 > 0:
            아픈것.append((필요, _name(h)))
    머리 = ("들고 있는 것 모두 본전을 넘었습니다." if not 아픈것 else
            f"{nlu.josa(max(아픈것)[1], '이가')} 본전까지 가장 멉니다 "
            f"({max(아픈것)[0]:+.2f}%).")
    return "\n".join([머리, "", "■ 본전까지"] + out +
                     ["  (수수료·세금은 넣지 않은 값입니다)"])


# ---------------------------------------------------------------- 비중
def _exposure(base: Path, r: nlu.Reading) -> str:
    rows = _read(base / f"{r.mode}_보유종목.csv")
    daily = _read(base / f"{r.mode}_일별손익.csv")
    if not rows:
        return "보유 종목이 없어 비중을 낼 수 없습니다."
    총자산 = _num(daily[-1].get("총자산")) if daily else 0.0
    평가합 = sum(_value(h) for h in rows)
    바탕 = 총자산 or 평가합
    if not 바탕:
        return "평가금액이나 총자산이 적혀 있지 않아 비중을 낼 수 없습니다."

    큰것 = max(rows, key=_value)
    머리 = (f"주식에 {평가합 / 바탕 * 100:.1f}% 들어가 있고, "
            f"그중 {nlu.josa(_name(큰것), '이가')} {_value(큰것) / 바탕 * 100:.1f}% 로 가장 큽니다.")
    현금 = max(총자산 - 평가합, 0) if 총자산 else 0
    칸들 = [(_name(h), _value(h)) for h in sorted(rows, key=lambda x: -_value(x))]
    if 총자산:
        칸들.append(("현금(추정)", 현금))
    가장큰 = max(v for _, v in 칸들) or 1

    out = [머리, "", f"■ 비중 (바탕 {_plain(바탕)})"]
    for 이름, 값 in 칸들:
        몫 = 값 / 바탕 * 100
        칸 = "█" * max(1, round(값 / 가장큰 * 20))
        out.append(f"  {이름:12s} {몫:5.1f}%  {칸} {_plain(값)}")
    return "\n".join(out)


# ---------------------------------------------------------------- 미체결
def _pending(base: Path, r: nlu.Reading) -> str:
    r = _widen(r, 7)
    rows = _ledger(base, r, stocks=False)
    막힌 = [x for x in rows
            if not any(k in (x.get("결과") or "") for k in ("접수", "체결", "성공"))]
    if not rows:
        return f"{r.period.label} 주문 기록이 없습니다."
    if not 막힌:
        return (f"{nlu.josa(r.period.label, '은는')} 낸 주문 {len(rows)}건이 모두 "
                "접수됐습니다. 막힌 주문은 없습니다.")
    out = [f"{nlu.josa(r.period.label, '은는')} {len(막힌)}건이 접수되지 못했습니다.",
           "", f"■ 막힌 주문 {len(막힌)}건"]
    for x in 막힌:
        out.append(f"  {x.get('일시')}  {x.get('구분')} {_name(x)} "
                   f"{_num(x.get('수량')):,.0f}주 — {x.get('결과')}")
    return "\n".join(out)


# ---------------------------------------------------------------- 일지 찾기
def _journal_search(base: Path, r: nlu.Reading) -> str:
    rows = _rows(base, "자동매매_일지.csv", r.period, "일시")
    if not rows:
        return f"{r.period.label} 일지 기록이 없습니다."
    낱말 = [w for w in r.keywords if len(w) >= 2]
    찾음 = rows
    if r.stocks:
        찾음 = [x for x in 찾음 if any(st.matches(x.get("내용")) for st in r.stocks)]
    if 낱말:
        추린 = [x for x in 찾음 if any(w in (x.get("내용") or "") for w in 낱말)]
        찾음 = 추린 or 찾음
    머리 = f"{r.period.label} 일지에서 {len(찾음)}줄을 찾았습니다."
    if 낱말 and len(찾음) < len(rows):
        머리 += f" (찾은 낱말: {', '.join(낱말)})"
    out = [머리, "", f"■ 일지 {len(찾음)}건"]
    for x in 찾음[-20:]:
        out.append(f"  {x.get('일시')}  {x.get('내용')}")
    if len(찾음) > 20:
        out.append(f"  (앞의 {len(찾음) - 20}줄은 줄였습니다)")
    return "\n".join(out)


# ---------------------------------------------------------------- 횟수
def _count(base: Path, r: nlu.Reading) -> str:
    rows = _ledger(base, r)
    매수 = [x for x in rows if "매수" in (x.get("구분") or "")]
    매도 = [x for x in rows if "매도" in (x.get("구분") or "")]
    종목수 = len({_name(x) for x in rows})
    누구 = f" {_label_of(list(r.terms))}" if r.terms else ""
    if not rows:
        return f"{r.period.label}{누구} 체결이 없습니다. 0건입니다."
    머리 = (f"{nlu.josa(r.period.label, '은는')}{누구} 모두 {len(rows)}건 체결했습니다. "
            f"매수 {len(매수)}건, 매도 {len(매도)}건, 종목 {종목수}개입니다.")
    일자 = {_daykey(x.get("일시")) for x in rows}
    out = [머리, "", f"■ {r.period.label} 횟수",
           f"  체결   {len(rows)}건",
           f"  매수   {len(매수)}건",
           f"  매도   {len(매도)}건",
           f"  종목   {종목수}개",
           f"  매매한 날 {len(일자)}일"]
    return "\n".join(out)


# ---------------------------------------------------------------- 큰 거래
def _biggest(base: Path, r: nlu.Reading) -> str:
    rows = _ledger(base, r)
    if not rows:
        return f"{r.period.label} 체결 기록이 없습니다."
    큰것 = sorted(rows, key=lambda x: -_amt(x))
    n = max(1, min(r.limit or 5, len(큰것)))
    으뜸 = 큰것[0]
    머리 = (f"가장 큰 거래는 {_kdate(으뜸.get('일시'))} {_name(으뜸)} "
            f"{으뜸.get('구분')} {_plain(_amt(으뜸))} 입니다.")
    out = [머리, "", f"■ {r.period.label} 큰 거래 {n}건"]
    for i, x in enumerate(큰것[:n], 1):
        out.append(f"  {i}. {x.get('일시')}  {x.get('구분')} {_name(x)} "
                   f"{_num(x.get('수량')):,.0f}주 @ {_plain(_num(x.get('단가')))} "
                   f"= {_plain(_amt(x))}")
    return "\n".join(out)


# ---------------------------------------------------------------- 활동량
def _activity(base: Path, r: nlu.Reading) -> str:
    r = _widen(r, 7)
    rows = _ledger(base, r, stocks=False)
    if not rows:
        return f"{r.period.label} 체결 기록이 없습니다."
    날별 = {}
    for x in rows:
        날별.setdefault(_daykey(x.get("일시")), []).append(x)
    바쁜날 = max(날별.items(), key=lambda kv: len(kv[1]))
    평균 = len(rows) / max(len(날별), 1)
    머리 = (f"{nlu.josa(r.period.label, '은는')} {len(날별)}일 동안 {len(rows)}건, "
            f"하루 평균 {평균:.1f}건 매매했습니다. "
            f"가장 바빴던 날은 {_kdate(바쁜날[0])} ({len(바쁜날[1])}건) 입니다.")
    out = [머리, "", f"■ 날짜별 매매 건수"]
    for 날 in sorted(날별):
        칸 = "▪" * min(len(날별[날]), 30)
        out.append(f"  {날}  {len(날별[날]):3d}건  {칸}")
    return "\n".join(out)


# ---------------------------------------------------------------- 되풀이된 실수
def _mistakes(base: Path, r: nlu.Reading) -> str:
    r = _widen(r, 30)
    journal = _rows(base, "자동매매_일지.csv", r.period, "일시")
    ledger = _rows(base, f"{r.mode}_거래내역.csv", r.period, "일시")
    if not journal and not ledger:
        return f"{r.period.label} 기록이 없어 무엇이 되풀이되는지 볼 수 없습니다."

    손절종목 = {}
    for x in journal:
        내용 = x.get("내용") or ""
        if "손절" not in 내용:
            continue
        for h in _read(base / f"{r.mode}_보유종목.csv") + ledger:
            이름 = _name(h)
            if 이름 != "?" and 이름 in 내용:
                손절종목[이름] = 손절종목.get(이름, 0) + 1
                break
    되풀이 = {k: v for k, v in 손절종목.items() if v >= 2}

    산뒤판 = {}
    for x in sorted(ledger, key=lambda v: v.get("일시") or ""):
        이름 = _name(x)
        쪽 = "매수" if "매수" in (x.get("구분") or "") else "매도"
        산뒤판.setdefault(이름, []).append(쪽)
    잦은회전 = {k: v.count("매수") for k, v in 산뒤판.items() if v.count("매수") >= 3}

    조각 = []
    if 되풀이:
        조각.append("같은 종목에서 손절이 거듭됩니다: "
                    + ", ".join(f"{k} {v}번" for k, v in sorted(되풀이.items(),
                                                             key=lambda kv: -kv[1])))
    if 잦은회전:
        조각.append("한 종목을 자주 다시 삽니다: "
                    + ", ".join(f"{k} {v}번" for k, v in sorted(잦은회전.items(),
                                                             key=lambda kv: -kv[1])))
    손절수 = sum(1 for x in journal if "손절" in (x.get("내용") or ""))
    익절수 = sum(1 for x in journal if "익절" in (x.get("내용") or ""))
    if 손절수 and 익절수 and 손절수 >= 익절수 * 2:
        조각.append(f"손절({손절수})이 익절({익절수})보다 훨씬 많습니다. "
                    "조건이 너무 자주 걸리는지 살펴볼 만합니다.")
    if not 조각:
        return (f"{nlu.josa(r.period.label, '은는')} 눈에 띄게 되풀이되는 것이 없습니다. "
                f"(손절 {손절수} · 익절 {익절수})")
    out = [f"{r.period.label} 기록에서 걸리는 것이 {len(조각)}가지 보입니다.", "",
           "■ 되풀이되는 것"]
    out += [f"  · {말}" for 말 in 조각]
    out.append("  (기록에서 센 것일 뿐, 전략이 틀렸다는 뜻은 아닙니다)")
    return "\n".join(out)


# ---------------------------------------------------------------- 잡담
def _greeting(base: Path, r: nlu.Reading) -> str:
    return ("안녕하세요. 매매 기록으로 답해 드립니다.\n"
            '"오늘 요약해줘" 나 "이번 주 승률" 처럼 물어보세요.')


def _thanks(base: Path, r: nlu.Reading) -> str:
    return "도움이 됐다니 다행입니다. 더 궁금한 것이 있으면 물어보세요."


def _bye(base: Path, r: nlu.Reading) -> str:
    return "네, 필요할 때 다시 부르세요."


# ---------------------------------------------------------------- 도움말
HELP = """물어볼 수 있는 것 (API 키 없이 기록에서 바로 계산합니다)

  한눈에   "오늘 요약해줘"  "지금 상황 어때"  "별일 없지?"
  손익     "오늘 손익은?"  "이번 주 얼마 벌었어"  "최근 5일 수익"
  견주기   "지난주 대비 이번주 어때"  "어제보다 나아졌어?"
  평균     "하루 평균 얼마 벌어?"  "평균 수익률"
  보유     "지금 뭐 들고 있어"  "손실 난 종목만"  "10만원 넘게 번 종목"
  체결     "오늘 체결 내역"  "어제 뭐 사고팔았어"  "삼성전자 언제 샀어"
  이유     "삼성전자는 왜 팔았어?"  "005930 왜 샀어"  "오늘 왜 깨졌어"
  승률     "이번 주 승률"  "몇 승 몇 패야"  "연패 중이야?"
  순위     "제일 많이 번 종목"  "가장 아픈 종목 3개"
  자산     "총자산 얼마야"  "현금 얼마 남았어"  "주식 비중"
  추세     "최근 흐름 보여줘"  "최대 낙폭 얼마야"
  종목     "삼성전자 어때?"  "삼전 지금 상태"  "ㅅㅅㅈㅈ 어때"
  때       "몇 시에 제일 잘 돼?"  "요일별 성적"  "오전에 뭐 샀어"
  살림     "수수료 얼마 나갔어"  "본전까지 얼마"  "평균 보유 기간"
  살펴보기 "미체결 있어?"  "일지에서 고점대비 찾아줘"  "같은 실수 반복해?"

기간은 오늘·어제·그저께·이번/지난 주·이번/지난 달·올해·작년·분기·상반기,
"최근 N일/주/개월", "N일 전", "열흘", "일주일", "9월 3일", "9월 3일부터 10일까지",
"월요일", "최근 5영업일", "장 마감 무렵", "전체" 를 알아듣습니다.

띄어쓰기와 조사는 신경 쓰지 않아도 되고, 말끝이 달라도("팔았어/파셨나요/
매도했지") 같은 말로 봅니다. 오타와 한영 전환 실수도 어느 정도 봐줍니다.
"그럼 어제는?", "그건 왜 샀어?" 처럼 앞 질문에 이어 물어도 됩니다.
모의주문 기록을 보려면 질문에 '모의' 를 넣으세요."""


def suggest(question: str) -> str:
    """못 알아들었을 때. 지어내는 대신 무엇을 물을 수 있는지 보여 준다."""
    guesses = nlu.closest_examples(question, 3)
    lines = ["무슨 뜻인지 자신이 없어 답을 지어내지 않겠습니다.",
             "혹시 이런 걸 물으셨나요?"]
    lines += [f"  · {g}" for g in guesses]
    lines += ["", HELP]
    return "\n".join(lines)


def doctor(base: Path = None) -> str:
    """무엇이 어디서 불려 왔는지, 기록 폴더는 멀쩡한지 한눈에.

    돌다 이상하면 이것부터 찍어 본다. 파일이 섞였는지 바로 드러난다.
    """
    import os
    import platform
    import sys

    base = Path(base or ".")
    줄 = ["■ 불러온 것",
          f"  rules   {os.path.abspath(__file__)}  ({VERSION}판)",
          f"  nlu     {getattr(nlu, '__file__', '(모름)')}"
          f"  ({getattr(nlu, 'VERSION', 1)}판)",
          f"  파이썬   {platform.python_version()}  {platform.system()}"]
    if _옛파일:
        줄.append(f"  ! 옛 nlu.py 가 옆에 있습니다: {_옛파일}")
        쓰는중 = str(getattr(nlu, "__file__", "")).endswith("nlu.py")
        줄.append("    " + ("지금 그 파일을 쓰고 있습니다. nlu/ 폴더를 놓아 주세요."
                           if 쓰는중 else
                           "지금은 nlu/ 폴더 쪽을 쓰니, 그 파일은 지워도 됩니다."))
    곁 = Path(os.path.dirname(os.path.abspath(__file__))) / "nlu"
    빠진 = [이름 for 이름 in ("__init__.py", "text.py", "numbers.py", "timeframe.py",
                          "lexicon.py", "entities.py", "intents.py", "parse.py",
                          "explain.py") if not (곁 / 이름).is_file()]
    if 빠진:
        줄.append(f"  ! nlu/ 에 없는 파일: {', '.join(빠진)}")

    줄 += ["", f"■ 기록 폴더  {base.resolve()}"]
    본것 = False
    for mode in MODES:
        for 이름 in (f"{mode}_일별손익.csv", f"{mode}_보유종목.csv",
                    f"{mode}_거래내역.csv"):
            길 = base / 이름
            if 길.is_file():
                본것 = True
                줄.append(f"  {이름:24s} {len(_read(길)):4d}줄")
    길 = base / "자동매매_일지.csv"
    if 길.is_file():
        본것 = True
        줄.append(f"  {'자동매매_일지.csv':24s} {len(_read(길)):4d}줄")
    if not 본것:
        줄.append("  (기록 파일이 하나도 없습니다. 폴더를 일러 주세요:"
                  " python rules.py 기록폴더)")
    else:
        말 = catalog(base)
        줄.append(f"  아는 종목 {len(말)}개"
                  + (f": {', '.join(s.label for s in 말[:6])}" if 말 else ""))
    return "\n".join(줄)


def ask_back(후보: tuple) -> str:
    """두 뜻 사이에서 헷갈렸을 때 되묻는 말."""
    첫, 둘 = (nlu.say_intent(후보[0]), nlu.say_intent(후보[1]))
    return (f"{첫} 을(를) 물으신 건가요, 아니면 {둘} 인가요?\n"
            f"  · \"{첫}\" 이라고 다시 말해 주셔도 됩니다.")


# ---------------------------------------------------------------- 진입점
_HANDLER = {
    "pnl": _pnl, "why": _why, "holdings": _holdings, "trades": _trades,
    "winrate": _winrate, "ranking": _ranking, "asset": _asset,
    "trend": _trend, "stock": _stock, "summary": _summary,
    "compare": _compare, "average": _average, "daypart": _daypart,
    "drawdown": _drawdown, "streak": _streak, "holding_period": _holding_period,
    "cost": _cost, "breakeven": _breakeven, "exposure": _exposure,
    "pending": _pending, "journal": _journal_search, "count": _count,
    "biggest": _biggest, "activity": _activity, "mistakes": _mistakes,
    "greeting": _greeting, "thanks": _thanks, "bye": _bye,
}


def _reading(question: str, base: Path, mode: str = "", terms=(),
             last=None, today: date = None) -> nlu.Reading:
    r = nlu.understand(question, catalog(Path(base)), terms, last, today)
    if mode and mode != r.mode and not any(k in nlu.squash(question)
                                           for k in ("모의", "가상", "실제", "실전")):
        r = r._replace(mode=mode)
    return r


def read(question: str, base: Path, terms=(), last=None,
         today: date = None) -> nlu.Reading:
    """질문을 읽기만 한다. 무엇으로 알아들었는지 확인할 때 쓴다."""
    return _reading(question, Path(base), "", terms, last, today)


def respond(r: nlu.Reading, base: Path, outside: bool = False) -> str:
    """읽어 낸 뜻에 맞는 답. 모르면 빈 문자열.

    outside 를 켜면 기록 밖 질문(전망·설정·시황)에도 왜 답할 수 없는지
    한마디 한다. 끄면 빈 문자열이라, 부르는 쪽에서 API 로 넘길 수 있다.
    """
    if r.intent == "help":
        return HELP
    if r.kind == "바깥":
        return r.hint() if outside else ""
    fn = _HANDLER.get(r.intent)
    return fn(Path(base), r) if fn else ""


def answer(question: str, base: Path, terms=(), last=None,
           today: date = None) -> str:
    """규칙으로 답할 수 있으면 답을, 아니면 빈 문자열.

    빈 문자열이면 호출한 쪽에서 API 로 넘기면 된다. 예전과 같은 약속이다.
    """
    base = Path(base)
    r = _reading(question, base, "", terms, last, today)

    if r.parts:                       # "오늘 손익이랑 보유종목" 처럼 두 가지를 물은 것
        blocks = []
        for part in r.parts:
            piece = respond(_reading(part, base, r.mode, terms, None, today), base)
            if piece:
                blocks.append(piece)
        if len(blocks) > 1:
            return "\n\n".join(blocks)

    return respond(r, base)


class Conversation:
    """이어지는 대화. 앞 질문을 기억해 "그럼 어제는?" 을 받아 준다."""

    def __init__(self, base: Path, today: date = None):
        self.base = Path(base)
        self.today = today
        self.last = None

    def ask(self, question: str, terms=()) -> str:
        r = _reading(question, self.base, "", terms, self.last, self.today)
        out, 끝 = "", r
        if r.parts:
            blocks = []
            for part in r.parts:
                조각 = _reading(part, self.base, r.mode, terms, None, self.today)
                말 = respond(조각, self.base)
                if 말:
                    blocks.append(말)
                    끝 = 조각
            out = "\n\n".join(blocks) if len(blocks) > 1 else ""
        if not out:
            out, 끝 = respond(r, self.base, outside=True), r
        if not out:
            헷갈림 = nlu.ambiguous(r)
            if 헷갈림:
                self.last = 끝
                return ask_back(헷갈림)
            return suggest(question)
        self.last = 끝
        return out


def _main() -> None:                  # pragma: no cover
    """python rules.py [폴더] ["질문"] — 질문이 없으면 이어서 물어볼 수 있다.

    --why 를 붙이면 답 대신 '어떻게 알아들었는지' 를 보여 준다.
    대화 중에도 앞에 ? 를 붙이면 같은 것을 볼 수 있다.
    """
    import sys
    args = [a for a in sys.argv[1:]]
    설명 = "--why" in args
    점검 = "--doctor" in args
    args = [a for a in args if a not in ("--why", "--doctor")]
    base = Path(args[0]) if args and not args[0].startswith("-") else Path(".")
    if 점검:
        print(doctor(base))
        return
    rest = " ".join(args[1:]) if len(args) > 1 else ""
    chat = Conversation(base)

    def 한번(q: str) -> str:
        if q.startswith("??") or q.strip() in ("--doctor", "상태", "점검"):
            return doctor(base)
        if 설명 or q.startswith("?"):
            return nlu.trace(q.lstrip("? "), catalog(base))
        return chat.ask(q)

    if rest:
        print(한번(rest))
        return
    print(f"매매 기록 봇 (rules {VERSION}판 · nlu {getattr(nlu, 'VERSION', 1)}판"
          f" · 기록 {base.resolve()})")
    if _옛파일:
        print("  ! 옆에 옛 nlu.py 가 남아 있습니다. 지금은 nlu/ 폴더 쪽을 쓰니"
              " 지워도 됩니다.")
    print("무엇이 궁금하신가요?"
          " (앞에 ? 를 붙이면 어떻게 알아들었는지, ?? 를 붙이면 상태를 봅니다)\n")
    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        print(한번(q), "\n")


if __name__ == "__main__":            # pragma: no cover
    _main()
