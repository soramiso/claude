"""문장 하나를 끝까지 읽어 Reading 한 덩이로 만든다.

여기까지 오면 답을 만들 재료가 다 모인다. 무엇을(의도), 언제(기간),
어떤 종목을, 어떤 조건으로 물었는지가 한 자리에 담긴다. 앞 질문을 기억해
"그럼 어제는?" 처럼 생략한 말을 채우는 일도 여기서 한다.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Iterable, NamedTuple, Optional

from . import text as T
from . import lexicon as L
from . import numbers as N
from . import entities as E
from . import intents as I
from . import timeframe as TF
from .timeframe import Period
from .entities import Stock

THRESHOLD = I.THRESHOLD

# 앞말을 가리키는 말. 이것이 보이면 앞 질문에서 빠진 자리를 채운다.
ANAPHORA = ("그럼", "그러면", "그건", "그거", "그것", "거기", "아까", "방금",
            "그때", "그리고", "또", "이번엔", "이건", "걔", "얘", "쟤", "다시",
            "한번더", "마찬가지")
# 기간과 상관없는 물음들. "그럼 어제는?" 을 이어받을 때는 손익으로 돌린다.
TIMELESS = ("holdings", "stock", "ranking", "help", "exposure", "breakeven")

_SPLIT_RE = re.compile(r"그리고|,|、|\+|또한|이랑|하고|랑|그다음|및|또")


class Reading(NamedTuple):
    """질문 하나를 읽어 낸 결과. rules 는 이것만 보고 답을 만든다."""
    raw: str
    intent: str
    score: float
    period: Period
    stocks: tuple = ()
    terms: tuple = ()
    mode: str = "실제매매"
    want: str = ""
    limit: Optional[int] = None
    runners: tuple = ()
    parts: tuple = ()
    followup: bool = False
    # --- 넓히면서 붙인 것들 -------------------------------------------
    kind: str = "기록"
    margin: float = 0.0
    side: str = ""
    metric: str = ""
    order: str = ""
    agg: str = ""
    ordinal: Optional[int] = None
    constraints: tuple = ()
    keywords: tuple = ()
    negated: bool = False
    polite: str = "중립"
    asked: bool = True
    smalltalk: str = ""
    inherited: tuple = ()
    notes: tuple = ()

    @property
    def baseline(self) -> Optional[Period]:
        return self.period.baseline

    @property
    def label(self) -> str:
        return self.period.label

    def hint(self) -> str:
        """기록 밖 질문이면 대신 해 줄 말."""
        it = L.BY_NAME.get(self.intent)
        return it.hint if it else ""


def understand(question: str, catalog: Iterable = (), terms: Iterable = (),
               last: Optional[Reading] = None, today: Optional[date] = None,
               allow_split: bool = True, aliases: Optional[dict] = None) -> Reading:
    """질문 하나를 끝까지 읽어 낸다. 대답은 rules 가 만든다."""
    raw = T.normalize(question)
    q = T.squash(T.deflate(raw))
    catalog = list(catalog)

    stocks = E.find_stocks(raw, catalog, aliases) if raw else ()
    given = tuple(str(t) for t in terms if str(t).strip())
    flat = _flatten(stocks, given)

    period = TF.parse_period(raw, today)
    slots = {
        "stocks": stocks, "terms": flat, "baseline": period.baseline,
        "agg": E.find_agg(raw), "order": E.find_order(raw),
        "metric": E.find_metric(raw), "want": E.find_want(raw),
        "side": E.find_side(raw), "constraints": N.parse_constraints(raw),
        "clock": period.has_clock(),
        "target": any(w in q for w in ("종목", "거있", "것있", "거없", "것없",
                                       "거만", "것만", "거는", "게있", "애들",
                                       "놈", "주식은", "거뭐", "것뭐")),
    }

    ranked = I.score_detail(raw, has_terms=bool(flat))
    best = (ranked[0].name, ranked[0].score) if ranked else ("unknown", 0.0)
    잔말 = T.is_smalltalk(raw)
    inherited, notes = [], []

    # 앞 종목을 가리키는 말이면 뜻이 또렷해도 이어받는다
    if last is not None and not stocks and last.stocks and _points_back(q):
        stocks = last.stocks
        flat = _flatten(stocks, given)
        slots["stocks"], slots["terms"] = stocks, flat
        ranked = I.score_detail(raw, has_terms=True)
        best = (ranked[0].name, ranked[0].score) if ranked else ("unknown", 0.0)
        inherited.append("종목")

    followup = False
    if best[1] < THRESHOLD and last is not None and not 잔말:
        if _points_back(q) or period.explicit or flat or slots["want"]:
            의도 = last.intent
            if period.explicit and 의도 in TIMELESS:
                의도 = "pnl"
                notes.append("기간만 바꿔 물어 손익으로 봄")
            best = (의도, THRESHOLD)
            followup = True
            inherited.append("물음")
            if not period.explicit and last.period.explicit:
                period = last.period
                inherited.append("기간")

    name = best[0] if best[1] >= THRESHOLD else "unknown"
    if name == "unknown" and 잔말:
        name = {"인사": "greeting", "감사": "thanks", "작별": "bye",
                "웃음": "greeting"}.get(잔말, "unknown")
    name, 까닭 = I.route(name, slots)
    if 까닭:
        notes.append(까닭)

    parts = _split(raw, catalog, today, aliases) if (allow_split and not followup) else ()

    it = L.BY_NAME.get(name)
    return Reading(
        raw=raw, intent=name, score=best[1], period=period,
        stocks=tuple(stocks), terms=flat, mode=E.find_mode(raw),
        want=slots["want"], limit=N.parse_limit(raw),
        runners=tuple((s.name, s.score) for s in ranked[:4]),
        parts=parts, followup=followup,
        kind=it.kind if it else "기록",
        margin=I.margin(ranked), side=slots["side"], metric=slots["metric"],
        order=slots["order"], agg=slots["agg"], ordinal=N.parse_ordinal(raw),
        constraints=slots["constraints"],
        keywords=E.find_keywords(raw), negated=T.has_negation(raw),
        polite=T.politeness(raw), asked=T.is_question(raw), smalltalk=잔말,
        inherited=tuple(inherited), notes=tuple(notes))


def _flatten(stocks, given) -> tuple:
    return tuple(dict.fromkeys([t for s in stocks for t in s.terms] + list(given)))


def _points_back(q: str) -> bool:
    return any(k in q for k in ANAPHORA)


def _split(raw: str, catalog, today, aliases) -> tuple:
    """두 가지를 한 문장에 물었으면 조각으로 나눈다."""
    pieces = [p.strip() for p in _SPLIT_RE.split(raw) if p.strip()]
    if len(pieces) < 2:
        return ()
    reads = [understand(p, catalog, (), None, today, False, aliases) for p in pieces]
    good = [r for r in reads if r.intent != "unknown" and r.score >= THRESHOLD]
    if len(good) > 1 and len({r.intent for r in good}) > 1:
        return tuple(r.raw for r in good)
    return ()


# ---------------------------------------------------------------- 되묻기
def closest_examples(question: str, n: int = 3) -> list:
    """못 알아들었을 때 "혹시 이거?" 로 내밀 예시."""
    pool = [(ex, it.name) for it in L.INTENTS if it.kind == "기록"
            for ex in it.examples]
    q = T.squash(question)
    scored = sorted(pool, key=lambda p: -T.similar(q, T.squash(p[0])))
    return [ex for ex, _ in scored[:n]]


def ambiguous(r: Reading) -> tuple:
    """헷갈렸으면 후보 둘을 준다. 되물을 때 쓴다."""
    if r.intent == "unknown" or r.margin >= 0.35 or len(r.runners) < 2:
        return ()
    첫, 둘 = r.runners[0][0], r.runners[1][0]
    if 첫 == 둘 or 둘 not in L.BY_NAME:
        return ()
    return (첫, 둘)


SAY = {"pnl": "손익", "holdings": "보유 종목", "trades": "체결 내역",
       "winrate": "승률", "why": "매매 이유", "summary": "전체 요약",
       "ranking": "종목 순위", "asset": "자산", "trend": "손익 흐름",
       "stock": "그 종목 상태", "compare": "기간 비교", "average": "평균",
       "daypart": "시간대별 성적", "drawdown": "최대 낙폭", "streak": "연승·연패",
       "holding_period": "보유 기간", "cost": "수수료", "breakeven": "본전 가격",
       "exposure": "비중", "pending": "미체결 주문", "journal": "일지 검색",
       "count": "횟수", "biggest": "가장 큰 거래", "activity": "매매 활동량",
       "mistakes": "되풀이된 실수", "help": "도움말"}


def say_intent(name: str) -> str:
    return SAY.get(name, name)


# ---------------------------------------------------------------- 대화
class Dialogue:
    """여러 번 이어지는 물음을 기억한다. 몇 턴이면 충분하다."""

    def __init__(self, catalog: Iterable = (), today: Optional[date] = None,
                 aliases: Optional[dict] = None, keep: int = 8):
        self.catalog = list(catalog)
        self.today = today
        self.aliases = aliases or {}
        self.keep = keep
        self.history = []

    @property
    def last(self) -> Optional[Reading]:
        return self.history[-1] if self.history else None

    def read(self, question: str, terms: Iterable = ()) -> Reading:
        r = understand(question, self.catalog, terms, self.last, self.today,
                       True, self.aliases)
        return r

    def remember(self, r: Reading) -> None:
        self.history.append(r)
        del self.history[:-self.keep]

    def forget(self) -> None:
        self.history.clear()
