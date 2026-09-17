"""질문을 뜯어 보는 층. 규칙이지만 사람 말에 가깝게 받아 준다.

하는 일은 넷이다.

  다듬기  띄어쓰기와 조사를 걷어내고, 오타는 비슷한 말로 되돌린다.
  기간    "지난주", "9월 3일", "최근 2주", "열흘" 을 날짜 범위로 바꾼다.
  의도    키워드마다 점수를 매겨 가장 높은 것을 고른다. 낮으면 모른다고 한다.
  종목    기록에 있는 이름·코드·줄임말·초성으로 종목을 집어낸다.

문장을 정말로 이해하지는 못한다. 다만 같은 뜻을 달리 쓰는 것, 조금 틀리게
쓰는 것, 앞 질문에 기대어 짧게 쓰는 것까지는 받아 준다. 그마저 안 되면
무엇을 물을 수 있는지 보여 주는 편이 지어내는 것보다 낫다.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Iterable, NamedTuple, Optional

# ---------------------------------------------------------------- 글자 다듬기

_WS = re.compile(r"\s+")
_WORD = re.compile(r"[가-힣ㄱ-ㅎa-z0-9]+")
CHOSUNG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"


_JAMO_BACK = {chr(0x1100 + i): CHOSUNG[i] for i in range(19)}
_JAMO_BACK.update({chr(0x1161 + i): chr(0x314F + i) for i in range(21)})


def normalize(text: str) -> str:
    """유니코드 꼴을 맞추고 공백을 한 칸으로 줄인다.

    NFKC 는 홀로 쓴 'ㅅ' 을 조합용 자모로 바꿔 버린다. 초성 질문("ㅅㅅㅈㅈ")
    을 받으려면 그것만 제자리로 돌려놓아야 한다.
    """
    t = unicodedata.normalize("NFKC", text or "")
    if any(ch in _JAMO_BACK for ch in t):
        t = "".join(_JAMO_BACK.get(ch, ch) for ch in t)
    return _WS.sub(" ", t).strip()


def squash(text: str) -> str:
    """띄어쓰기를 지운 꼴. '이번 주' 와 '이번주' 를 같은 말로 본다."""
    return _WS.sub("", normalize(text)).lower()


_JOSA = ("으로부터", "에서부터", "로부터", "에게서", "한테서", "이라는", "이라고",
         "이라도", "이라서", "까지는", "부터는", "에서는", "에게는", "보다는",
         "보다도", "라는", "라고", "라도", "라서", "처럼", "만큼", "밖에",
         "조차", "마저", "에서", "에게", "한테", "께서", "이랑", "하고",
         "으로", "에는", "까지", "부터", "보다", "이나",
         "은", "는", "이", "가", "을", "를", "의", "도", "만", "과", "와",
         "랑", "로", "에", "야", "아", "나")
JOSA = tuple(sorted(set(_JOSA), key=len, reverse=True))


def strip_josa(token: str) -> str:
    """토큰 끝의 조사를 뗀다. 남는 말이 두 글자는 되어야 뗀다."""
    if not re.fullmatch(r"[가-힣]+", token):
        return token
    for j in JOSA:
        if token.endswith(j) and len(token) - len(j) >= 2:
            return token[: -len(j)]
    return token


def tokens(text: str) -> list:
    """비교용 토큰. 조사를 떼고 소문자로."""
    return [strip_josa(t) for t in _WORD.findall(normalize(text).lower())]


def chosung(text: str) -> str:
    """초성만 남긴다. 'ㅅㅅㅈㅈ' 같은 질문을 받기 위한 것."""
    out = []
    for ch in text:
        if "가" <= ch <= "힣":
            out.append(CHOSUNG[(ord(ch) - 0xAC00) // 588])
        elif "ㄱ" <= ch <= "ㅎ":
            out.append(ch)
    return "".join(out)


def abbrev(name: str) -> set:
    """흔한 줄임말. 삼성전자→삼전, LG화학→화학 처럼 부르는 사람이 많다."""
    s = squash(name)
    han = re.sub(r"[^가-힣]", "", s)
    out = set()
    if len(han) >= 3:
        out.add(han[0] + han[2])
    if len(han) >= 4:
        out.add(han[:2])
    tail = re.sub(r"^[a-z0-9]+", "", s)
    if len(tail) >= 2 and tail != s:
        out.add(tail)
    out.discard("")
    return {a for a in out if len(a) >= 2}


_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"


def jamo(text: str) -> str:
    """글자를 자모로 푼다. '승률' 과 '승율' 은 글자로는 반만 같지만
    자모로는 여섯 중 다섯이 같다. 오타를 봐주려면 이쪽이 맞다."""
    out = []
    for ch in text:
        if "가" <= ch <= "힣":
            i = ord(ch) - 0xAC00
            out.append(CHOSUNG[i // 588])
            out.append(_JUNG[(i % 588) // 28])
            if i % 28:
                out.append(_JONG[i % 28])
        else:
            out.append(ch)
    return "".join(out)


def similar(a: str, b: str) -> float:
    """두 말이 얼마나 닮았는지. 오타를 봐주는 데만 쓴다."""
    return max(difflib.SequenceMatcher(None, a, b).ratio(),
               difflib.SequenceMatcher(None, jamo(a), jamo(b)).ratio())


# ---------------------------------------------------------------- 조사 붙이기

_PAIRS = {"은는": ("은", "는"), "이가": ("이", "가"), "을를": ("을", "를"),
          "와과": ("과", "와"), "과와": ("과", "와"), "로으로": ("으로", "로"),
          "으로로": ("으로", "로"), "이나": ("이나", "나"), "이란": ("이란", "란")}


def has_batchim(word: str) -> bool:
    """마지막 글자에 받침이 있나. 숫자와 영문은 읽는 소리로 친다."""
    w = re.sub(r"[^가-힣a-zA-Z0-9]+$", "", normalize(word))
    if not w:
        return False
    ch = w[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    if ch.isdigit():
        return ch in "013678"          # 영·일·삼·육·칠·팔 은 받침으로 끝난다
    return ch.lower() in "lmnr"        # 엘·엠·엔·알


def josa(word: str, pair: str = "은는") -> str:
    """받침에 맞는 조사를 붙인다. 문장이 사람 말처럼 보이는 가장 싼 방법."""
    key = pair.replace("/", "").replace(" ", "")
    withb, without = _PAIRS.get(key, (key[: len(key) // 2], key[len(key) // 2:]))
    w = normalize(word)
    if not w:
        return w
    if key in ("로으로", "으로로"):
        ch = w[-1]
        if "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 == 8:   # ㄹ 받침
            return w + "로"
    return w + (withb if has_batchim(w) else without)


# ---------------------------------------------------------------- 기간

class Period(NamedTuple):
    """질문이 가리키는 기간. start 가 None 이면 전체."""
    start: Optional[date]
    end: Optional[date]
    label: str
    explicit: bool = True


_NUM_WORD = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "석": 3, "셋": 3,
             "네": 4, "넉": 4, "넷": 4, "다섯": 5, "여섯": 6, "일곱": 7,
             "여덟": 8, "아홉": 9, "열": 10}
_NUM_RE = "|".join([r"\d+"] + sorted(_NUM_WORD, key=len, reverse=True))

_SPAN_WORD = {"하루": 1, "이틀": 2, "사흘": 3, "나흘": 4, "닷새": 5, "엿새": 6,
              "이레": 7, "여드레": 8, "아흐레": 9, "열흘": 10, "보름": 15,
              "일주일": 7, "이주일": 14, "삼주일": 21, "한주": 7, "두주": 14,
              "한달": 30, "두달": 60, "석달": 90, "일년": 365}

_WEEKDAY = {"월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3,
            "금요일": 4, "토요일": 5, "일요일": 6}

_DATE_RE = (
    re.compile(r"(?<!\d)(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?!\d)"),
    re.compile(r"(?<!\d)(\d{1,2})월(\d{1,2})일"),
    re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)"),
)


def _fmt(d: date) -> str:
    return f"{d.month}월 {d.day}일"


def _day_label(d: date, today: date) -> str:
    gap = (today - d).days
    return {0: "오늘", 1: "어제", 2: "그저께"}.get(gap) or _fmt(d)


def _month_bounds(y: int, m: int) -> tuple:
    start = date(y, m, 1)
    end = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
    return start, end


def _months_ago(d: date, n: int) -> date:
    y, m = d.year, d.month - n
    while m <= 0:
        m += 12
        y -= 1
    _, last = _month_bounds(y, m)
    return date(y, m, min(d.day, last.day))


def _dates_in(q: str, today: date) -> list:
    """문장에 박힌 날짜들. 겹치면 긴 쪽을 남긴다."""
    found = []
    for pat in _DATE_RE:
        for m in pat.finditer(q):
            g = m.groups()
            try:
                if len(g) == 3:
                    d = date(int(g[0]), int(g[1]), int(g[2]))
                else:
                    d = date(today.year, int(g[0]), int(g[1]))
                    if d > today + timedelta(days=1):
                        d = date(today.year - 1, int(g[0]), int(g[1]))
            except ValueError:
                continue
            found.append((m.start(), m.end(), d))
    found.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    picked = []
    for s, e, d in found:
        if picked and s < picked[-1][1]:
            continue
        picked.append((s, e, d))
    return picked


def parse_period(question: str, today: Optional[date] = None) -> Period:
    """질문에서 기간을 읽는다. 아무 말도 없으면 오늘."""
    today = today or datetime.now().date()
    q = squash(question)

    found = _dates_in(q, today)
    if len(found) >= 2 and re.search(r"부터|~|까지|에서", q):
        a, b = sorted((found[0][2], found[-1][2]))
        return Period(a, b, f"{_fmt(a)}~{_fmt(b)}")
    if found:
        d = found[0][2]
        return Period(d, d, _day_label(d, today))

    m = re.search(r"(?<!\d)(\d{1,2})월(?!\d)", q)
    if m and 1 <= int(m.group(1)) <= 12:
        mm = int(m.group(1))
        y = today.year if mm <= today.month else today.year - 1
        s, e = _month_bounds(y, mm)
        return Period(s, min(e, today), f"{mm}월")

    if any(k in q for k in ("그저께", "그제", "엊그제")):
        d = today - timedelta(days=2)
        return Period(d, d, "그저께")
    if any(k in q for k in ("어제", "어저께", "전날")):
        d = today - timedelta(days=1)
        return Period(d, d, "어제")
    if any(k in q for k in ("오늘", "금일", "오늘자", "지금", "현재")):
        return Period(today, today, "오늘")

    monday = today - timedelta(days=today.weekday())
    if "지지난주" in q:
        s = monday - timedelta(days=14)
        return Period(s, s + timedelta(days=6), "지지난 주")
    if any(k in q for k in ("지난주", "저번주", "전주", "지난한주")):
        s = monday - timedelta(days=7)
        return Period(s, s + timedelta(days=6), "지난 주")
    if any(k in q for k in ("이번주", "금주", "요번주", "이번한주")):
        return Period(monday, today, "이번 주")

    if "지지난달" in q:
        prev = _months_ago(today.replace(day=1), 2)
        s, e = _month_bounds(prev.year, prev.month)
        return Period(s, e, "지지난 달")
    if any(k in q for k in ("지난달", "저번달", "전월", "지난한달")):
        prev = _months_ago(today.replace(day=1), 1)
        s, e = _month_bounds(prev.year, prev.month)
        return Period(s, e, "지난 달")
    if any(k in q for k in ("이번달", "이달", "금월", "요번달", "이번월")):
        s, _ = _month_bounds(today.year, today.month)
        return Period(s, today, "이번 달")
    if any(k in q for k in ("올해", "금년", "올한해")):
        return Period(date(today.year, 1, 1), today, "올해")
    if any(k in q for k in ("작년", "지난해", "전년")):
        y = today.year - 1
        return Period(date(y, 1, 1), date(y, 12, 31), "작년")

    if any(k in q for k in ("전체", "누적", "지금까지", "여태", "통틀어", "처음부터")):
        return Period(None, None, "전체 기간")

    for w, idx in _WEEKDAY.items():
        if w in q:
            d = today - timedelta(days=(today.weekday() - idx) % 7)
            return Period(d, d, f"{w} ({_fmt(d)})")

    m = (re.search(rf"(?:최근|지난|요)\s*({_NUM_RE})\s*(주일|개월|달|주|일)", q)
         or re.search(rf"({_NUM_RE})\s*(주일|개월|달|주|일)\s*(?:간|동안|치|째)", q))
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else _NUM_WORD[m.group(1)]
        unit = m.group(2)
        if n > 0:
            if unit in ("개월", "달"):
                s = _months_ago(today, n) + timedelta(days=1)
                return Period(s, today, f"최근 {n}개월")
            days = n * 7 if unit in ("주", "주일") else n
            return Period(today - timedelta(days=days - 1), today,
                          f"최근 {n}{'주' if unit in ('주', '주일') else '일'}")

    for w, n in sorted(_SPAN_WORD.items(), key=lambda kv: -len(kv[0])):
        if w in q:
            return Period(today - timedelta(days=n - 1), today, f"최근 {n}일")

    if any(k in q for k in ("요즘", "최근", "근래", "며칠", "요새", "요즈음")):
        return Period(today - timedelta(days=6), today, "최근 7일")

    m = re.search(r"(?<!\d)(\d{1,2})\s*일(?!간|동안|치|째)", q)
    if m and 1 <= int(m.group(1)) <= 31:
        day = int(m.group(1))
        y, mm = today.year, today.month
        if day > today.day:                     # 아직 오지 않은 날이면 지난달
            first = _months_ago(today.replace(day=1), 1)
            y, mm = first.year, first.month
        try:
            d = date(y, mm, day)
            return Period(d, d, _day_label(d, today))
        except ValueError:
            pass

    return Period(today, today, "오늘", False)


def in_period(text: str, period: Period) -> bool:
    """'2026-09-17 09:31' 같은 칸이 기간 안에 드는지."""
    if period.start is None:
        return True
    m = re.match(r"\s*(\d{4})[-./]?(\d{2})[-./]?(\d{2})", text or "")
    if not m:
        return False
    try:
        d = date(*map(int, m.groups()))
    except ValueError:
        return False
    return period.start <= d <= period.end


# ---------------------------------------------------------------- 의도

class Intent(NamedTuple):
    name: str
    keys: tuple            # (구문, 가중치)
    examples: tuple = ()


INTENTS = (
    Intent("help", (("도움말", 1.5), ("뭘물", 1.5), ("뭐물", 1.5), ("무엇을물", 1.5),
                    ("help", 1.5), ("사용법", 1.5), ("어떻게쓰", 1.2),
                    ("뭘할수있", 1.2), ("뭐할수있", 1.2), ("명령어", 1.2),
                    ("뭐라고물", 1.2)),
           ("뭘 물어볼 수 있어?", "사용법 알려줘")),
    Intent("summary", (("요약", 1.5), ("브리핑", 1.5), ("정리해", 1.3), ("한눈에", 1.5),
                       ("현황", 1.0), ("상황", 1.0), ("리포트", 1.2), ("보고", 0.8),
                       ("전체적으로", 1.0), ("별일없", 1.2), ("어떻게되고있", 1.2),
                       ("오늘어때", 1.2), ("잘돌아가", 1.2)),
           ("오늘 요약해줘", "지금 상황 어때")),
    Intent("winrate", (("승률", 1.5), ("성적", 1.2), ("몇승", 1.2), ("승패", 1.2),
                       ("이겼", 1.0), ("적중률", 1.3), ("잘하고있", 1.0),
                       ("익절", 1.0), ("손절", 1.0), ("몇번먹", 1.0)),
           ("이번 주 승률", "오늘 몇 승 몇 패야")),
    Intent("why", (("왜", 1.3), ("이유", 1.3), ("어째서", 1.3), ("뭐때문", 1.3),
                   ("때문", 1.0), ("근거", 1.2), ("무슨일", 1.0), ("어쩌다", 1.1),
                   ("판단", 0.8), ("무슨생각", 1.2)),
           ("삼성전자는 왜 팔았어?", "005930 왜 샀어")),
    Intent("holdings", (("보유", 1.5), ("잔고", 1.3), ("들고", 1.3), ("갖고", 1.3),
                        ("가지고", 1.1), ("포지션", 1.3), ("몇종목", 1.2),
                        ("남은종목", 1.2), ("내종목", 1.2), ("종목목록", 1.2),
                        ("종목만", 1.3), ("난종목", 1.2), ("인종목", 1.2),
                        ("것만", 1.0), ("거만", 1.0)),
           ("보유종목 알려줘", "지금 뭐 들고 있어")),
    Intent("trades", (("체결", 1.5), ("거래내역", 1.5), ("매매내역", 1.5),
                      ("주문내역", 1.5), ("사고팔", 1.2), ("매매했", 1.1),
                      ("거래했", 1.1), ("언제샀", 1.2), ("언제팔", 1.2),
                      ("주문", 0.8), ("사고판", 1.2)),
           ("오늘 체결 내역", "어제 뭐 사고팔았어")),
    Intent("pnl", (("손익", 1.3), ("수익", 1.0), ("손실", 1.0), ("손해", 1.0),
                   ("이익", 1.0), ("얼마", 1.0), ("벌었", 1.2), ("잃었", 1.2),
                   ("깨졌", 1.2), ("먹었", 0.9), ("플러스", 0.9), ("마이너스", 0.9),
                   ("수익률", 1.0), ("물렸", 0.9)),
           ("오늘 손익은?", "이번 주 얼마 벌었어")),
    Intent("ranking", (("제일", 1.2), ("가장", 1.2), ("최고", 1.2), ("최악", 1.2),
                       ("베스트", 1.3), ("워스트", 1.3), ("순위", 1.4), ("랭킹", 1.4),
                       ("많이번", 1.3), ("많이잃", 1.3), ("효자", 1.2), ("애물단지", 1.2),
                       ("잘나가", 1.1), ("톱", 0.9)),
           ("제일 많이 번 종목", "가장 손실 큰 종목")),
    Intent("asset", (("총자산", 1.5), ("예수금", 1.5), ("자산", 1.1), ("현금", 1.2),
                     ("잔액", 1.2), ("원금", 1.2), ("시드", 1.1), ("투자금", 1.2),
                     ("남은돈", 1.3), ("얼마있", 1.2)),
           ("총자산 얼마야", "현금 얼마 남았어")),
    Intent("trend", (("추세", 1.4), ("흐름", 1.4), ("추이", 1.4), ("일별", 1.2),
                     ("그래프", 1.2), ("변화", 1.0), ("나아지", 1.2), ("나빠지", 1.2),
                     ("회복", 1.1), ("늘었", 0.9), ("줄었", 0.9), ("어떻게변", 1.2)),
           ("최근 흐름 보여줘", "요즘 나아지고 있어?")),
    Intent("stock", (("어때", 0.8), ("어떄", 0.8), ("상태", 0.7), ("괜찮", 0.8),
                     ("현황", 0.5), ("어떻게됐", 0.8), ("살아났", 0.8)),
           ("삼성전자 어때?", "카카오 지금 어떤 상태야")),
)

THRESHOLD = 0.9
_TERM_BONUS = {"why": 0.5, "stock": 0.9, "trades": 0.2}
_ANAPHORA = ("그럼", "그러면", "그건", "그거", "그것", "거기", "아까", "방금",
             "그때", "그리고", "또", "그럼요", "이번엔", "이건", "걔", "얘")
# 기간과 상관없는 물음들. "그럼 어제는?" 을 이어받을 때는 손익으로 돌린다.
_TIMELESS = ("holdings", "stock", "ranking", "help")


def score_intents(question: str, has_terms: bool = False) -> list:
    """의도마다 점수를 매겨 높은 순으로. 오타는 한 번만 봐준다."""
    q = squash(question)
    toks = [t for t in tokens(question) if len(t) >= 2]
    out = []
    for it in INTENTS:
        exact = sum(w for p, w in it.keys if p in q)
        fuzzy = 0.0
        if not exact:
            for p, w in it.keys:
                if len(p) < 2:
                    continue
                for t in toks:
                    r = similar(p, t)
                    if r >= 0.75:
                        fuzzy = max(fuzzy, w * r * 0.8)
        score = exact + fuzzy
        if has_terms:
            score += _TERM_BONUS.get(it.name, 0.0) if score else 0.0
            if it.name == "stock":
                score += 0.4
        if score:
            out.append((it.name, round(score, 3)))
    out.sort(key=lambda kv: -kv[1])
    return out


# ---------------------------------------------------------------- 종목 집어내기

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


def find_stocks(question: str, catalog: Iterable) -> tuple:
    """질문에 나온 종목. 이름·코드·줄임말·초성·앞글자 순으로 찾는다."""
    q = squash(question)
    catalog = list(catalog)
    hits, seen = [], set()

    def add(stock, pos):
        key = stock.name or stock.code
        if key and key not in seen:
            seen.add(key)
            hits.append((pos, stock))

    by_code = {s.code: s for s in catalog if s.code}
    for m in re.finditer(r"(?<!\d)\d{6}(?!\d)", q):
        add(by_code.get(m.group(0), Stock("", m.group(0))), m.start())

    for s in catalog:
        name = squash(s.name)
        if len(name) >= 2 and name in q:
            add(s, q.find(name))

    for s in catalog:
        for a in abbrev(s.name):
            if a in q:
                add(s, q.find(a))

    jamo = re.findall(r"[ㄱ-ㅎ]{2,}", q)
    for j in jamo:
        for s in catalog:
            if chosung(s.name) == j:
                add(s, q.find(j))

    for t in tokens(question):
        if len(t) < 2 or not re.fullmatch(r"[가-힣]+", t):
            continue
        for s in catalog:
            name = squash(s.name)
            if name.startswith(t) and name != t:
                add(s, q.find(t))

    hits.sort(key=lambda kv: kv[0])
    return tuple(s for _, s in hits)


# ---------------------------------------------------------------- 읽은 결과

class Reading(NamedTuple):
    raw: str
    intent: str
    score: float
    period: Period
    stocks: tuple
    terms: tuple
    mode: str
    want: str                 # "" | "win" | "lose"
    limit: Optional[int]
    runners: tuple
    parts: tuple
    followup: bool


_SPLIT_RE = re.compile(r"그리고|,|、|\+|또한|이랑|하고|랑|그다음|및")


def _mode_of(q: str) -> str:
    if any(k in q for k in ("모의", "가상", "연습", "페이퍼", "모의투자")):
        return "가상매매"
    return "실제매매"


def _want_of(q: str) -> str:
    if any(k in q for k in ("수익난", "이익난", "플러스", "오른", "벌고있", "먹은", "번종목")):
        return "win"
    if any(k in q for k in ("손실난", "마이너스", "빠진", "물린", "물려", "손해난",
                            "떨어진", "깨진", "잃은")):
        return "lose"
    return ""


def _limit_of(q: str) -> Optional[int]:
    m = re.search(r"(?:상위|하위|탑|top)?\s*(\d{1,2})\s*(?:개|종목|건|등)", q)
    return int(m.group(1)) if m else None


def understand(question: str, catalog: Iterable = (), terms: Iterable = (),
               last: Optional[Reading] = None, today: Optional[date] = None,
               allow_split: bool = True) -> Reading:
    """질문 하나를 끝까지 읽어 낸다. 대답은 rules 가 만든다."""
    raw = normalize(question)
    q = squash(raw)
    catalog = list(catalog)

    stocks = find_stocks(raw, catalog)
    given = tuple(str(t) for t in terms if str(t).strip())
    flat = tuple(dict.fromkeys([t for s in stocks for t in s.terms] + list(given)))

    period = parse_period(raw, today)
    mode, want = _mode_of(q), _want_of(q)
    ranked = score_intents(raw, has_terms=bool(flat))
    best = ranked[0] if ranked else ("unknown", 0.0)

    # "그건 왜 샀어?" 처럼 앞 종목을 가리키면 뜻이 또렷해도 이어받는다.
    if (last is not None and not stocks and last.stocks
            and any(k in q for k in _ANAPHORA)):
        stocks = last.stocks
        flat = tuple(dict.fromkeys([t for s in stocks for t in s.terms] + list(given)))
        ranked = score_intents(raw, has_terms=True)
        best = ranked[0] if ranked else ("unknown", 0.0)

    followup = False
    if best[1] < THRESHOLD and last is not None:
        if any(k in q for k in _ANAPHORA) or period.explicit or flat:
            intent = last.intent
            if period.explicit and intent in _TIMELESS:
                intent = "pnl"        # "그럼 어제는?" 은 어제 손익을 묻는 말이다
            best = (intent, THRESHOLD)
            followup = True

    name = best[0] if best[1] >= THRESHOLD else "unknown"

    # 종목을 짚어 물으면 '그 종목 이야기' 로 본다. "삼성전자 수익 얼마야?" 처럼.
    if flat and name in ("pnl", "trend", "summary", "asset"):
        name = "stock"
    if name == "stock" and not flat:
        name = "summary"
    if name == "unknown" and flat:
        name = "stock"
    if name == "unknown" and want:
        name = "holdings"        # "물린 거 있어?" 는 결국 보유 목록을 묻는 말이다

    parts = ()
    if allow_split and not followup:
        pieces = [p.strip() for p in _SPLIT_RE.split(raw) if p.strip()]
        if len(pieces) > 1:
            reads = [understand(p, catalog, (), None, today, False) for p in pieces]
            # 조각이 스스로 뜻을 갖춰야 쪼갠다. "삼성전자랑 카카오 왜 샀어" 의
            # 앞 조각처럼 종목 이름뿐인 것은 쪼갤 거리가 아니다.
            good = [r for r in reads
                    if r.intent != "unknown" and r.score >= THRESHOLD]
            if len(good) > 1 and len({r.intent for r in good}) > 1:
                parts = tuple(r.raw for r in good)

    return Reading(raw=raw, intent=name, score=best[1], period=period,
                   stocks=tuple(stocks), terms=flat, mode=mode,
                   want=want, limit=_limit_of(q),
                   runners=tuple(ranked[:3]), parts=parts, followup=followup)


def closest_examples(question: str, n: int = 3) -> list:
    """못 알아들었을 때 "혹시 이거?" 로 내밀 예시."""
    pool = [(ex, it.name) for it in INTENTS for ex in it.examples]
    scored = sorted(pool, key=lambda p: -similar(squash(question), squash(p[0])))
    return [ex for ex, _ in scored[:n]]
