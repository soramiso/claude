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

try:                      # 패키지 안에서 불려도, 스크립트로 불려도 되게
    from . import nlu
except ImportError:       # pragma: no cover
    import nlu

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

    kept = rows
    note = ""
    if r.want == "win":
        kept = [h for h in rows if _num(h.get("평가손익")) > 0]
        note = " (이익 난 것만)"
    elif r.want == "lose":
        kept = [h for h in rows if _num(h.get("평가손익")) < 0]
        note = " (손실 난 것만)"
    if not kept:
        which = "이익 난" if r.want == "win" else "손실 난"
        return f"지금 {which} 종목은 없습니다. (보유 {len(rows)}종목)"

    kept = sorted(kept, key=lambda h: -_num(h.get("평가손익")))
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
    rows = _rows(base, f"{r.mode}_거래내역.csv", r.period, "일시")
    if r.terms:
        rows = [x for x in rows
                if any(t in (x.get("종목코드") or "") + (x.get("종목명") or "")
                       for t in r.terms)]
    label = r.period.label
    if not rows:
        who = f" {_label_of(list(r.terms))}" if r.terms else ""
        return f"{label}{who} 체결 기록이 없습니다."

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


# ---------------------------------------------------------------- 도움말
HELP = """물어볼 수 있는 것 (API 키 없이 기록에서 바로 계산합니다)

  요약    "오늘 요약해줘"  "지금 상황 어때"  "별일 없지?"
  손익    "오늘 손익은?"  "이번 주 얼마 벌었어"  "최근 5일 수익"
  이유    "삼성전자는 왜 매도했지?"  "005930 왜 샀어"  "오늘 왜 깨졌어"
  보유    "보유종목 알려줘"  "지금 뭐 들고 있나"  "손실 난 종목만"
  체결    "오늘 체결 내역"  "어제 뭐 사고팔았어"  "삼성전자 언제 샀어"
  승률    "이번 주 승률"  "오늘 몇 승 몇 패야"
  순위    "제일 많이 번 종목"  "가장 아픈 종목 3개"
  자산    "총자산 얼마야"  "현금 얼마 남았어"
  추세    "최근 흐름 보여줘"  "요즘 나아지고 있어?"
  종목    "삼성전자 어때?"  "삼전 지금 상태"  "ㅅㅅㅈㅈ 어때"

기간은 오늘·어제·그저께·이번 주·지난 주·이번 달·지난 달·올해·작년,
"최근 N일/주/개월", "열흘", "일주일", "9월 3일", "9월 3일부터 10일까지",
"월요일", "전체" 를 알아듣습니다.

띄어쓰기와 조사는 신경 쓰지 않아도 되고, 오타도 어느 정도 봐줍니다.
"그럼 어제는?" 처럼 앞 질문에 이어 물어도 됩니다.
모의주문 기록을 보려면 질문에 '모의' 를 넣으세요."""


def suggest(question: str) -> str:
    """못 알아들었을 때. 지어내는 대신 무엇을 물을 수 있는지 보여 준다."""
    guesses = nlu.closest_examples(question, 3)
    lines = ["무슨 뜻인지 자신이 없어 답을 지어내지 않겠습니다.",
             "혹시 이런 걸 물으셨나요?"]
    lines += [f"  · {g}" for g in guesses]
    lines += ["", HELP]
    return "\n".join(lines)


# ---------------------------------------------------------------- 진입점
_HANDLER = {"pnl": _pnl, "why": _why, "holdings": _holdings, "trades": _trades,
            "winrate": _winrate, "ranking": _ranking, "asset": _asset,
            "trend": _trend, "stock": _stock, "summary": _summary}


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


def respond(r: nlu.Reading, base: Path) -> str:
    """읽어 낸 뜻에 맞는 답. 모르면 빈 문자열."""
    if r.intent == "help":
        return HELP
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
            out, 끝 = respond(r, self.base), r
        if not out:
            return suggest(question)
        self.last = 끝
        return out


def _main() -> None:                  # pragma: no cover
    """python rules.py [폴더] ["질문"] — 질문이 없으면 이어서 물어볼 수 있다."""
    import sys
    args = [a for a in sys.argv[1:]]
    base = Path(args[0]) if args and not args[0].startswith("-") else Path(".")
    rest = " ".join(args[1:]) if len(args) > 1 else ""
    chat = Conversation(base)
    if rest:
        print(chat.ask(rest))
        return
    print("무엇이 궁금하신가요? (그냥 Enter 치면 끝냅니다)\n")
    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        print(chat.ask(q), "\n")


if __name__ == "__main__":            # pragma: no cover
    _main()
