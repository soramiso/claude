"""문장에서 무엇을 가리키는지 집어낸다.

종목이 가장 중요하다. 사람은 "삼성전자" 라고 또박또박 쓰지 않는다. 코드로,
줄임말로, 초성으로, 오타로, 심지어 한영 전환을 잊고 "tkatjdwjswk" 라고
친다. 기록에 있는 이름을 밑천 삼아 그 모두를 같은 종목으로 본다.

지표(수익률·평단가), 정렬(많은 순), 집계(평균), 방향(매수/매도)도 여기서 꺼낸다.
"""

from __future__ import annotations

import re
from typing import Iterable, NamedTuple, Optional

from . import text as T
from . import lexicon as L


class Stock(NamedTuple):
    name: str
    code: str

    @property
    def label(self) -> str:
        if self.name and self.code:
            return f"{self.name}({self.code})"
        return self.name or self.code or "?"

    @property
    def terms(self) -> tuple:
        return tuple(t for t in (self.name, self.code) if t)

    def matches(self, *fields: str) -> bool:
        """기록 한 줄의 칸들이 이 종목을 가리키는지."""
        blob = "".join(f or "" for f in fields)
        return any(t and t in blob for t in self.terms)


# 종목 이름으로 오해하기 쉬운 흔한 말들. 사전에 나오는 말은 종목이 아니다.
_STOP = set()
for _i in L.INTENTS:
    for _k, _ in _i.keys:
        _STOP.add(_k)
for _group in (L.METRICS, L.ORDERS, L.AGGS):
    for _words in _group.values():
        _STOP.update(_words)
_STOP.update(L.WANT_WIN + L.WANT_LOSE + L.SIDE_BUY + L.SIDE_SELL)
_STOP.update(("오늘", "어제", "이번", "지난", "종목", "주식", "수익", "손실", "전체",
              "얼마", "요즘", "최근", "지금", "현재", "보유", "평가", "누적"))


def catalog_from(pairs: Iterable) -> tuple:
    """(종목명, 종목코드) 쌍들을 종목 목록으로. 이름이 같으면 코드 있는 쪽."""
    seen = {}
    for name, code in pairs:
        name, code = (name or "").strip(), (code or "").strip()
        key = name or code
        if not key:
            continue
        cur = seen.get(key)
        if cur is None or (not cur.code and code):
            seen[key] = Stock(name, code)
    return tuple(seen.values())


def abbrevs(name: str) -> set:
    """흔한 줄임말. 삼성전자→삼전, LG화학→화학, SK하이닉스→하이닉스."""
    s = T.squash(name)
    han = re.sub(r"[^가-힣]", "", s)
    out = set()
    if len(han) >= 3:
        out.add(han[0] + han[2])
    if len(han) >= 4:
        out.add(han[:2])
        out.add(han[0] + han[2] + han[3] if len(han) >= 4 else "")
    tail = re.sub(r"^[a-z0-9]+", "", s)
    if len(tail) >= 2 and tail != s:
        out.add(tail)
    head = re.match(r"^[a-z]{2,}", s)
    if head:
        out.add(head.group(0))
    out.discard("")
    return {a for a in out if len(a) >= 2}


def find_stocks(question: str, catalog: Iterable, aliases: Optional[dict] = None,
                fuzzy: bool = True) -> tuple:
    """질문에 나온 종목들. 나온 차례대로 준다."""
    catalog = list(catalog)
    raw = T.normalize(question)
    q = T.squash(raw)
    hits, seen = [], set()

    def add(stock: Stock, pos: int):
        key = stock.name or stock.code
        if key and key not in seen:
            seen.add(key)
            hits.append((pos, stock))

    # 1) 여섯 자리 코드는 가장 또렷하다
    by_code = {s.code: s for s in catalog if s.code}
    for m in re.finditer(r"(?<!\d)\d{6}(?!\d)", q):
        add(by_code.get(m.group(0), Stock("", m.group(0))), m.start())

    # 2) 사람이 붙여 둔 별명
    for 별명, 이름 in (aliases or {}).items():
        별 = T.squash(별명)
        if 별 and 별 in q:
            찾음 = next((s for s in catalog if s.name == 이름), Stock(이름, ""))
            add(찾음, q.find(별))

    # 3) 이름 그대로
    for s in catalog:
        name = T.squash(s.name)
        if len(name) >= 2 and name in q:
            add(s, q.find(name))

    # 4) 줄임말
    for s in catalog:
        for a in abbrevs(s.name):
            if a in q and a not in _STOP:
                add(s, q.find(a))

    # 5) 초성만 친 경우
    for j in re.findall(r"[ㄱ-ㅎ]{2,}", q):
        for s in catalog:
            if T.chosung(s.name) == j:
                add(s, q.find(j))

    # 6) 앞글자만 부른 경우 ("삼성" → 삼성전자)
    for tok in T.tokens(raw):
        if len(tok) < 2 or tok in _STOP or not re.fullmatch(r"[가-힣]+", tok):
            continue
        for s in catalog:
            name = T.squash(s.name)
            if name.startswith(tok) and name != tok:
                add(s, q.find(tok))

    # 7) 한영 전환을 잊고 친 경우
    for tok in re.findall(r"[a-zA-Z]{4,}", raw):
        if T.looks_like_qwerty(tok):
            되돌린 = T.squash(T.from_qwerty(tok))
            for s in catalog:
                if T.squash(s.name) == 되돌린:
                    add(s, raw.find(tok))

    # 8) 오타. 짧은 이름은 건드리지 않는다
    if fuzzy and not hits:
        for tok in T.tokens(raw):
            if len(tok) < 3 or tok in _STOP:
                continue
            for s in catalog:
                name = T.squash(s.name)
                if len(name) >= 3 and T.similar(tok, name) >= 0.8:
                    add(s, q.find(tok[:2]) if tok[:2] in q else 0)

    hits.sort(key=lambda kv: kv[0] if kv[0] >= 0 else 999)
    return tuple(s for _, s in hits)


# ---------------------------------------------------------------- 그 밖의 슬롯
def _first_hit(q: str, table: dict) -> str:
    """사전에서 문장에 나온 첫 항목. 긴 낱말을 먼저 본다."""
    best, where = "", len(q) + 1
    for 이름, 말들 in table.items():
        for w in sorted(말들, key=len, reverse=True):
            i = q.find(w)
            if i >= 0 and i < where:
                best, where = 이름, i
    return best


def find_metric(question: str) -> str:
    return _first_hit(T.squash(question), L.METRICS)


def find_order(question: str) -> str:
    return _first_hit(T.squash(question), L.ORDERS)


def find_agg(question: str) -> str:
    return _first_hit(T.squash(question), L.AGGS)


def find_want(question: str) -> str:
    """이익 난 것만 / 손실 난 것만."""
    q = T.squash(question)
    승 = min((q.find(w) for w in L.WANT_WIN if w in q), default=-1)
    패 = min((q.find(w) for w in L.WANT_LOSE if w in q), default=-1)
    if 승 < 0 and 패 < 0:
        return ""
    if 패 < 0 or (승 >= 0 and 승 < 패):
        return "win"
    return "lose"


# 양쪽을 한꺼번에 이르는 말. 한쪽으로 몰면 안 된다.
_BOTH_SIDES = ("사고팔", "사고판", "매매", "매수매도", "매도매수", "거래")


def find_side(question: str) -> str:
    """산 이야기인지 판 이야기인지. 없거나 양쪽이면 빈 문자열."""
    q = T.squash(question)
    if any(w in q for w in _BOTH_SIDES):
        return ""
    어간 = T.stem_set(question)
    산 = any(w in q for w in L.SIDE_BUY) or bool(어간 & {"사", "매수", "담"})
    판 = any(w in q for w in L.SIDE_SELL) or bool(어간 & {"팔", "매도", "털"})
    if 산 and not 판:
        return "매수"
    if 판 and not 산:
        return "매도"
    return ""


def find_mode(question: str) -> str:
    q = T.squash(question)
    if any(k in q for k in L.MODE_SIM):
        return "가상매매"
    return "실제매매"


# 어느 질문에나 나오는 말들. 찾을 낱말로는 쓸모가 없다.
_GENERIC = set(("오늘", "어제", "그제", "이번", "지난", "최근", "요즘", "지금",
                "전체", "누적", "알려줘", "보여줘", "말해줘", "찾아줘", "좀",
                "뭐야", "어때", "일지", "기록", "내역", "에서", "관련", "부분"))


def find_keywords(question: str, drop: Iterable = ()) -> tuple:
    """일지 검색처럼 '무엇을 찾는지' 가 필요할 때 쓸 낱말들.

    종목 이름을 가릴 때 쓰는 _STOP 은 여기서 쓰지 않는다. "손절", "고점대비"
    처럼 사전에 있는 말이 바로 찾을 말인 경우가 많기 때문이다.
    """
    빼기 = set(drop) | _GENERIC
    out = []
    for tok in T.tokens(question):
        if len(tok) < 2 or tok in 빼기 or tok.isdigit():
            continue
        out.append(tok)
    return tuple(dict.fromkeys(out))
