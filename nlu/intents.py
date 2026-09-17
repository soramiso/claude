"""어느 뜻으로 물었는지 고른다.

두 단계다. 먼저 사전에 적힌 말들로 점수를 매겨 가장 높은 뜻을 고른다.
그다음 문장에서 꺼낸 슬롯(기간·종목·집계·견줌 기준)을 보고 더 좁은 뜻으로
옮긴다. "오늘 평균 얼마 벌어?" 는 손익처럼 보이지만 평균을 물은 것이고,
"삼성전자 수익 얼마야" 는 그 종목 이야기다. 사전을 늘리는 대신 이 옮김
규칙으로 다루면 사전이 단순해진다.
"""

from __future__ import annotations

from typing import NamedTuple

from . import text as T
from . import lexicon as L

THRESHOLD = 0.9
FUZZY_CUT = 0.75


class Scored(NamedTuple):
    name: str
    score: float
    why: tuple          # 무엇에 걸렸는지. 설명할 때 쓴다


def score_intents(question: str, has_terms: bool = False) -> list:
    """의도마다 점수를. 높은 순으로 (이름, 점수) 목록."""
    return [(s.name, s.score) for s in score_detail(question, has_terms)]


def score_detail(question: str, has_terms: bool = False) -> list:
    """점수와 함께 근거까지. 설명·시험에 쓴다."""
    q = T.squash(question)
    toks = [t for t in T.tokens(question) if len(t) >= 2]
    어간 = T.stem_set(question)
    out = []
    for it in L.INTENTS:
        점수, 근거 = 0.0, []
        for phrase, w in it.keys:
            if phrase in q:
                점수 += w
                근거.append(f"'{phrase}'")
        for st, w in it.stems:
            if st in 어간:
                점수 += w
                근거.append(f"어간 '{st}'")
        if not 점수:                      # 오타는 정확히 걸린 게 없을 때만 봐준다
            fuzzy, 짝 = 0.0, ""
            for phrase, w in it.keys:
                if len(phrase) < 3:          # 두 글자는 닮은 말이 너무 많다
                    continue
                for t in toks:
                    r = T.similar(phrase, t)
                    if r >= FUZZY_CUT and w * r * 0.8 > fuzzy:
                        fuzzy, 짝 = w * r * 0.8, f"'{t}'≈'{phrase}'"
            if fuzzy:
                점수, 근거 = fuzzy, [짝]
        if has_terms and 점수:
            보탬 = {"why": 0.5, "stock": 0.9, "trades": 0.2, "breakeven": 0.3,
                   "holding_period": 0.3}.get(it.name, 0.0)
            if 보탬:
                점수 += 보탬
                근거.append("종목을 짚음")
        if has_terms and it.name == "stock":
            점수 += 0.4
        if 점수:
            out.append(Scored(it.name, round(점수, 3), tuple(근거)))
    out.sort(key=lambda s: -s.score)
    return out


def margin(ranked: list) -> float:
    """1등과 2등의 점수 차. 작을수록 헷갈린 것이다."""
    if len(ranked) < 2:
        return 9.9 if ranked else 0.0
    첫, 둘 = ranked[0], ranked[1]
    a = 첫.score if isinstance(첫, Scored) else 첫[1]
    b = 둘.score if isinstance(둘, Scored) else 둘[1]
    return round(a - b, 3)


# ---------------------------------------------------------------- 옮김 규칙
def route(name: str, slots: dict) -> tuple:
    """슬롯을 보고 더 좁은 뜻으로 옮긴다. (새 이름, 옮긴 까닭)."""
    종목 = slots.get("stocks") or slots.get("terms")
    기준 = slots.get("baseline")
    집계 = slots.get("agg")
    순서 = slots.get("order")
    조건 = slots.get("constraints")
    바람 = slots.get("want")
    방향 = slots.get("side")
    지표 = slots.get("metric")
    때 = slots.get("clock")
    대상 = slots.get("target")      # "손실 난 거", "물린 종목" 처럼 가리키는 말

    if name in ("pnl", "summary", "trend", "asset") and 기준:
        return "compare", "견줄 기준이 있어 비교로 봄"
    if name in ("pnl", "trades", "winrate") and 집계 == "평균":
        return "average", "평균을 물어 평균으로 봄"
    if name in ("pnl", "trades") and 집계 == "개수":
        return "count", "개수를 물어 횟수로 봄"
    if name in ("pnl", "trend", "summary", "asset", "breakeven") and 종목:
        if name == "breakeven":
            return name, ""
        return "stock", "종목을 짚어 그 종목 이야기로 봄"
    if name == "pnl" and 바람 and 대상:
        return "holdings", "이익·손실로 종목을 골라 달라는 말로 봄"
    if name in ("pnl", "holdings") and (순서 in ("내림차순", "오름차순")) and not 조건:
        return "ranking", "정렬을 물어 순위로 봄"
    if name == "trades" and 때:
        return "trades", ""
    if name == "stock" and not 종목:
        return "summary", "종목을 짚지 않아 전체 요약으로 봄"
    if name == "unknown":
        if 종목:
            return "stock", "종목만 말해 그 종목 이야기로 봄"
        if 바람 or 조건:
            return "holdings", "이익·손실로 골라 달라는 말로 봄"
        if 방향:
            return "trades", "사고판 이야기로 봄"
        if 지표:
            return "pnl", "지표를 물어 손익으로 봄"
        if slots.get("period_explicit"):
            # "오늘은?" 처럼 때만 말한 물음. 그날을 한눈에 보여 주는 편이 낫다
            return "summary", "때만 말해 그날 요약으로 봄"
    return name, ""
