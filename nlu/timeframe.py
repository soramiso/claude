"""언제를 묻는지 읽는다.

날짜 말은 종류가 많다. "어제", "지지난 주", "9월 3일부터 10일까지", "열흘",
"3주 전", "2분기", "상반기", "지난 영업일", "장 마감 무렵", "지난주 대비".
이 모두를 (시작 날짜, 끝 날짜) 한 쌍과 시각 범위로 바꾸는 것이 여기 할 일이다.

찾는 차례가 곧 우선순위다. 또렷하게 적은 날짜를 먼저 보고, 그다음 상대적인
말, 마지막에 "요즘" 같은 막연한 말을 본다. 아무 말도 없으면 오늘로 본다.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import NamedTuple, Optional

from . import text as T
from .numbers import WORD_NUMBER, parse_ko_number


class Period(NamedTuple):
    """질문이 가리키는 때. start 가 None 이면 전체 기간."""
    start: Optional[date]
    end: Optional[date]
    label: str
    explicit: bool = True
    kind: str = "day"                  # day | range | all
    time_start: Optional[int] = None   # 분 단위. 540 = 09:00
    time_end: Optional[int] = None
    baseline: Optional["Period"] = None
    business_only: bool = False

    @property
    def days(self) -> int:
        if self.start is None or self.end is None:
            return 0
        return (self.end - self.start).days + 1

    def has_clock(self) -> bool:
        return self.time_start is not None or self.time_end is not None

    def say(self) -> str:
        """사람이 읽는 꼴. 답 머리에 그대로 쓸 수 있다."""
        말 = self.label
        if self.has_clock():
            말 += f" {_clock_label(self.time_start, self.time_end)}"
        if self.business_only:
            말 += " (장 열린 날만)"
        return 말


ALL = Period(None, None, "전체 기간", True, "all")

# ---------------------------------------------------------------- 낱말표
_NUM_RE = "|".join([r"\d+"] + sorted(
    [w for w in WORD_NUMBER if re.fullmatch(r"[가-힣]+", w)], key=len, reverse=True))

SPAN_WORD = {"하루": 1, "이틀": 2, "사흘": 3, "나흘": 4, "닷새": 5, "엿새": 6,
             "이레": 7, "여드레": 8, "아흐레": 9, "열흘": 10, "보름": 15,
             "일주일": 7, "이주일": 14, "삼주일": 21, "한주": 7, "두주": 14,
             "한달": 30, "두달": 60, "석달": 90, "세달": 90, "반년": 182,
             "일년": 365, "한해": 365}

WEEKDAY = {"월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3, "금요일": 4,
           "토요일": 5, "일요일": 6, "월욜": 0, "화욜": 1, "수욜": 2, "목욜": 3,
           "금욜": 4, "토욜": 5, "일욜": 6}

# 장 시간을 기준으로 삼는다. 분 단위로 적어 두면 비교가 쉽다.
CLOCK = {
    "장초반": (540, 600), "개장": (540, 600), "시초": (540, 570),
    "장시작": (540, 600), "오전": (540, 720), "아침": (540, 660),
    "점심": (690, 780), "오후": (720, 930), "장마감": (870, 930),
    "마감무렵": (870, 930), "막판": (870, 930), "종가": (900, 930),
    "장중": (540, 930), "동시호가": (480, 540),
}

_DATE_RE = (
    re.compile(r"(?<!\d)(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?!\d)"),
    re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)"),
    re.compile(r"(?<!\d)(\d{1,2})월\s*(\d{1,2})일"),
    re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)"),
)

_RANGE_MARK = re.compile(r"부터|까지|~|에서|사이|동안")
_COMPARE_MARK = ("대비", "보다", "비교", "견주", "에서얼마", "차이")


# ---------------------------------------------------------------- 잔손질
def _fmt(d: date) -> str:
    return f"{d.month}월 {d.day}일"


def _day_label(d: date, today: date) -> str:
    gap = (today - d).days
    이름 = {0: "오늘", 1: "어제", 2: "그저께", 3: "그끄저께", -1: "내일"}
    return 이름.get(gap) or _fmt(d)


def _clock_label(a: Optional[int], b: Optional[int]) -> str:
    def 시각(m):
        return f"{m // 60}:{m % 60:02d}"
    if a is not None and b is not None:
        return f"{시각(a)}~{시각(b)}"
    if a is not None:
        return f"{시각(a)} 이후"
    return f"{시각(b)} 이전" if b is not None else ""


def month_bounds(y: int, m: int) -> tuple:
    start = date(y, m, 1)
    end = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
    return start, end


def months_ago(d: date, n: int) -> date:
    y, m = d.year, d.month - n
    while m <= 0:
        m += 12
        y -= 1
    _, last = month_bounds(y, m)
    return date(y, m, min(d.day, last.day))


def quarter_bounds(y: int, q: int) -> tuple:
    first = 3 * (q - 1) + 1
    return date(y, first, 1), month_bounds(y, first + 2)[1]


def business_days(start: date, end: date) -> list:
    """주말을 뺀 날들. 공휴일까지는 모른다."""
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _num(word: str) -> int:
    if word.isdigit():
        return int(word)
    n = WORD_NUMBER.get(word)
    if n is None:
        n = parse_ko_number(word) or 0
    return int(n)


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


# ---------------------------------------------------------------- 시각
def parse_clock(question: str) -> tuple:
    """질문에서 시각 범위를 (시작분, 끝분) 으로. 없으면 (None, None)."""
    q = T.squash(question)
    m = re.search(r"(\d{1,2})시\s*(\d{1,2})?분?\s*(?:부터|~|-)\s*(\d{1,2})시\s*(\d{1,2})?분?", q)
    if m:
        a = int(m.group(1)) * 60 + int(m.group(2) or 0)
        b = int(m.group(3)) * 60 + int(m.group(4) or 0)
        return (a, b) if a <= b else (b, a)
    for w, (a, b) in CLOCK.items():
        if w in q:
            return a, b
    m = re.search(r"(\d{1,2})시\s*(\d{1,2})?분?\s*(이후|이전|전|후|쯤|경|께)?", q)
    if m:
        h, mm = int(m.group(1)), int(m.group(2) or 0)
        if h <= 8 and "오후" not in q:
            h += 12 if h <= 6 else 0
        base = h * 60 + mm
        tail = m.group(3) or ""
        if tail in ("이후", "후"):
            return base, None
        if tail in ("이전", "전"):
            return None, base
        return base, base + (0 if m.group(2) else 59)
    return None, None


# ---------------------------------------------------------------- 본체
def parse_period(question: str, today: Optional[date] = None) -> Period:
    """질문에서 기간을 읽는다. 아무 말도 없으면 오늘."""
    today = today or datetime.now().date()
    q = T.squash(question)

    m = re.search(r"대비|보다|비교해|비교하", q)
    if m:
        기준글, 본체글 = q[:m.start()], q[m.end():]
        기준 = _bare_period(기준글, today) if 기준글 else None
        본체 = _bare_period(본체글, today) if 본체글 else None
        if 기준 is not None:
            본체 = 본체 or following_span(기준, today)
            return 본체._replace(baseline=기준,
                                time_start=parse_clock(q)[0],
                                time_end=parse_clock(q)[1])

    clock = parse_clock(q)
    business = any(k in q for k in ("영업일", "거래일", "장열린", "장이열린"))

    def 마감(p: Period) -> Period:
        p = p._replace(time_start=clock[0], time_end=clock[1],
                       business_only=business or p.business_only)
        return p._replace(baseline=_baseline(q, p, today))

    for 찾기 in (_explicit_dates, _open_range, _month_only, _quarter, _relative_day,
                 _weeks, _months, _years, _whole, _weekday, _weekend,
                 _counted_span, _span_word, _point_in_past, _vague, _bare_day):
        p = 찾기(q, today)
        if p is not None:
            return 마감(p)

    if clock != (None, None):
        return 마감(Period(today, today, "오늘"))
    return 마감(Period(today, today, "오늘", False))


def _bare_period(chunk: str, today: date) -> Optional[Period]:
    """견줌말 앞뒤 조각에서 기간만 읽는다. 없으면 None."""
    for 찾기 in (_explicit_dates, _month_only, _quarter, _relative_day, _weeks,
                 _months, _years, _weekday, _counted_span, _span_word,
                 _point_in_past, _vague):
        p = 찾기(chunk, today)
        if p is not None:
            return p
    return None


def following_span(p: Period, today: date) -> Period:
    """기준 구간의 바로 다음 구간. '지난주보다' 의 상대가 되는 '이번 주'."""
    이름 = {"지난 주": "이번 주", "지난 달": "이번 달", "어제": "오늘",
            "작년": "올해", "지난 분기": "이번 분기", "그저께": "어제"}
    if p.start is None or p.end is None:
        return Period(today, today, "오늘")
    start = p.end + timedelta(days=1)
    end = min(start + timedelta(days=p.days - 1), today)
    if start > today:
        return Period(today, today, "오늘")
    붙인이름 = 이름.get(p.label) or (f"그 뒤 {p.days}일" if p.days > 1 else _day_label(start, today))
    return Period(start, max(end, start), 붙인이름, kind=p.kind)


# --- 찾기들. 하나라도 걸리면 거기서 끝난다 --------------------------------
def _explicit_dates(q: str, today: date) -> Optional[Period]:
    m = re.search(r"(?<!\d)(\d{1,2})월\s*(\d{1,2})일\s*(?:부터|~|-)\s*(\d{1,2})일", q)
    if m:                                  # "9월 3일부터 10일까지" — 뒤에 월이 없다
        try:
            a = date(today.year, int(m.group(1)), int(m.group(2)))
            b = date(today.year, int(m.group(1)), int(m.group(3)))
            if a > today:
                a, b = a.replace(year=a.year - 1), b.replace(year=b.year - 1)
            return Period(min(a, b), max(a, b), f"{_fmt(a)}~{_fmt(b)}", kind="range")
        except ValueError:
            pass
    found = _dates_in(q, today)
    if len(found) >= 2 and _RANGE_MARK.search(q):
        a, b = sorted((found[0][2], found[-1][2]))
        return Period(a, b, f"{_fmt(a)}~{_fmt(b)}", kind="range")
    if found:
        d = found[0][2]
        if "부터" in q[found[0][1]:found[0][1] + 4]:
            return Period(d, today, f"{_fmt(d)}부터", kind="range")
        if "까지" in q[found[0][1]:found[0][1] + 4]:
            return Period(None, d, f"{_fmt(d)}까지", kind="range")
        return Period(d, d, _day_label(d, today))
    return None


def _open_range(q: str, today: date) -> Optional[Period]:
    """'3일부터', '10일까지' 처럼 한쪽만 적은 것."""
    m = re.search(r"(?<!\d)(\d{1,2})일\s*부터", q)
    if m:
        d = _same_month_day(int(m.group(1)), today)
        if d:
            return Period(d, today, f"{_fmt(d)}부터", kind="range")
    m = re.search(r"(?<!\d)(\d{1,2})일\s*까지", q)
    if m:
        d = _same_month_day(int(m.group(1)), today)
        if d:
            return Period(None, d, f"{_fmt(d)}까지", kind="range")
    return None


def _same_month_day(day: int, today: date) -> Optional[date]:
    if not 1 <= day <= 31:
        return None
    y, mm = today.year, today.month
    if day > today.day:
        prev = months_ago(today.replace(day=1), 1)
        y, mm = prev.year, prev.month
    try:
        return date(y, mm, day)
    except ValueError:
        return None


def _month_only(q: str, today: date) -> Optional[Period]:
    m = re.search(r"(?<!\d)(\d{1,2})월(?!\d)", q)
    if not m or not 1 <= int(m.group(1)) <= 12:
        return None
    mm = int(m.group(1))
    y = today.year if mm <= today.month else today.year - 1
    s, e = month_bounds(y, mm)
    return Period(s, min(e, today), f"{mm}월", kind="range")


def _quarter(q: str, today: date) -> Optional[Period]:
    if "상반기" in q:
        y = today.year - (1 if "작년" in q or "지난" in q else 0)
        return Period(date(y, 1, 1), min(date(y, 6, 30), today),
                      f"{y}년 상반기" if y != today.year else "상반기", kind="range")
    if "하반기" in q:
        y = today.year - (1 if "작년" in q or "지난" in q else 0)
        return Period(date(y, 7, 1), min(date(y, 12, 31), today),
                      f"{y}년 하반기" if y != today.year else "하반기", kind="range")
    m = re.search(r"([1-4])\s*분기", q)
    now_q = (today.month - 1) // 3 + 1
    if m:
        qq = int(m.group(1))
        y = today.year - (1 if ("작년" in q or qq > now_q) else 0)
        s, e = quarter_bounds(y, qq)
        return Period(s, min(e, today), f"{qq}분기", kind="range")
    if "이번분기" in q or "금분기" in q:
        s, e = quarter_bounds(today.year, now_q)
        return Period(s, min(e, today), f"{now_q}분기", kind="range")
    if "지난분기" in q or "저번분기" in q or "전분기" in q:
        qq = now_q - 1 or 4
        y = today.year - (1 if now_q == 1 else 0)
        s, e = quarter_bounds(y, qq)
        return Period(s, e, f"지난 분기({qq}분기)", kind="range")
    return None


def _relative_day(q: str, today: date) -> Optional[Period]:
    if any(k in q for k in ("그끄저께", "그끄제")):
        d = today - timedelta(days=3)
        return Period(d, d, "그끄저께")
    if any(k in q for k in ("그저께", "그제", "엊그제")):
        d = today - timedelta(days=2)
        return Period(d, d, "그저께")
    if any(k in q for k in ("어제", "어저께", "전날", "지난밤")):
        d = today - timedelta(days=1)
        return Period(d, d, "어제")
    if any(k in q for k in ("오늘", "금일", "오늘자", "지금", "현재", "방금", "실시간")):
        return Period(today, today, "오늘")
    if "내일" in q or "모레" in q:
        d = today + timedelta(days=1 if "내일" in q else 2)
        return Period(d, d, "내일" if "내일" in q else "모레")
    return None


def _weeks(q: str, today: date) -> Optional[Period]:
    monday = today - timedelta(days=today.weekday())
    m = re.search(rf"({_NUM_RE})\s*주\s*전", q)
    if m:
        n = _num(m.group(1))
        s = monday - timedelta(days=7 * n)
        return Period(s, s + timedelta(days=6), f"{n}주 전", kind="range")
    if "지지난주" in q or "지지난 주" in q:
        s = monday - timedelta(days=14)
        return Period(s, s + timedelta(days=6), "지지난 주", kind="range")
    if any(k in q for k in ("지난주", "저번주", "전주", "지난한주", "먼젓주")):
        s = monday - timedelta(days=7)
        return Period(s, s + timedelta(days=6), "지난 주", kind="range")
    if any(k in q for k in ("이번주", "금주", "요번주", "이번한주", "이주")):
        return Period(monday, today, "이번 주", kind="range")
    return None


def _months(q: str, today: date) -> Optional[Period]:
    m = re.search(rf"({_NUM_RE})\s*(?:달|개월)\s*전", q)
    if m:
        n = _num(m.group(1))
        base = months_ago(today.replace(day=1), n)
        s, e = month_bounds(base.year, base.month)
        return Period(s, e, f"{n}달 전({s.month}월)", kind="range")
    if "지지난달" in q:
        base = months_ago(today.replace(day=1), 2)
        s, e = month_bounds(base.year, base.month)
        return Period(s, e, "지지난 달", kind="range")
    if any(k in q for k in ("지난달", "저번달", "전월", "지난한달")):
        base = months_ago(today.replace(day=1), 1)
        s, e = month_bounds(base.year, base.month)
        return Period(s, e, "지난 달", kind="range")
    if any(k in q for k in ("이번달", "이달", "금월", "요번달", "이번월", "당월")):
        s, _ = month_bounds(today.year, today.month)
        return Period(s, today, "이번 달", kind="range")
    if "월초" in q:
        s, _ = month_bounds(today.year, today.month)
        return Period(s, min(s + timedelta(days=9), today), "이번 달 초", kind="range")
    if "월말" in q:
        _, e = month_bounds(today.year, today.month)
        return Period(max(e - timedelta(days=9), today.replace(day=1)),
                      min(e, today), "이번 달 말", kind="range")
    return None


def _years(q: str, today: date) -> Optional[Period]:
    m = re.search(rf"({_NUM_RE})\s*년\s*전", q)
    if m:
        y = today.year - _num(m.group(1))
        return Period(date(y, 1, 1), date(y, 12, 31), f"{y}년", kind="range")
    if "재작년" in q:
        y = today.year - 2
        return Period(date(y, 1, 1), date(y, 12, 31), "재작년", kind="range")
    if any(k in q for k in ("작년", "지난해", "전년")):
        y = today.year - 1
        return Period(date(y, 1, 1), date(y, 12, 31), "작년", kind="range")
    if any(k in q for k in ("올해", "금년", "올한해", "연초부터", "올들어")):
        return Period(date(today.year, 1, 1), today, "올해", kind="range")
    if "연초" in q:
        return Period(date(today.year, 1, 1), min(date(today.year, 1, 31), today),
                      "연초", kind="range")
    if "연말" in q:
        y = today.year - (1 if today.month < 12 else 0)
        return Period(date(y, 12, 1), min(date(y, 12, 31), today), f"{y}년 연말",
                      kind="range")
    m = re.search(r"(20\d{2})년", q)
    if m:
        y = int(m.group(1))
        return Period(date(y, 1, 1), min(date(y, 12, 31), today), f"{y}년", kind="range")
    return None


_WHOLE_WORDS = ("전체", "누적", "지금까지", "여태", "통틀어", "처음부터",
                "이제껏", "역대", "전기간", "다합쳐", "총합")


def _whole(q: str, today: date) -> Optional[Period]:
    # 붙여 쓴 글자에 우연히 걸리지 않게 낱말 단위로 본다. '오전 체결' 의 '전체'.
    for tok in T.tokens(q):
        if any(tok.startswith(w) for w in _WHOLE_WORDS):
            return ALL
    return None


def _weekday(q: str, today: date) -> Optional[Period]:
    for w, idx in WEEKDAY.items():
        if w in q:
            back = (today.weekday() - idx) % 7
            if any(k in q for k in ("지난", "저번")):
                back += 7
            d = today - timedelta(days=back)
            return Period(d, d, f"{w[0]}요일 ({_fmt(d)})")
    return None


def _weekend(q: str, today: date) -> Optional[Period]:
    if "주말" in q:
        sat = today - timedelta(days=(today.weekday() - 5) % 7)
        return Period(sat, sat + timedelta(days=1), "주말", kind="range")
    if "평일" in q:
        monday = today - timedelta(days=today.weekday())
        return Period(monday, min(monday + timedelta(days=4), today), "평일",
                      kind="range", business_only=True)
    return None


def _counted_span(q: str, today: date) -> Optional[Period]:
    m = (re.search(rf"(?:최근|지난|요)\s*({_NUM_RE})\s*(영업일|거래일|주일|개월|달|주|일|년)", q)
         or re.search(rf"({_NUM_RE})\s*(영업일|거래일|주일|개월|달|주|일|년)\s*(?:간|동안|치|째)", q))
    if not m:
        return None
    n, unit = _num(m.group(1)), m.group(2)
    if n <= 0:
        return None
    if unit in ("개월", "달"):
        s = months_ago(today, n) + timedelta(days=1)
        return Period(s, today, f"최근 {n}개월", kind="range")
    if unit == "년":
        return Period(date(today.year - n, today.month, today.day), today,
                      f"최근 {n}년", kind="range")
    if unit in ("영업일", "거래일"):
        d, 남은 = today, n
        while 남은 > 1:
            d -= timedelta(days=1)
            if d.weekday() < 5:
                남은 -= 1
        return Period(d, today, f"최근 {n}영업일", kind="range", business_only=True)
    days = n * 7 if unit in ("주", "주일") else n
    이름 = f"최근 {n}{'주' if unit in ('주', '주일') else '일'}"
    return Period(today - timedelta(days=days - 1), today, 이름, kind="range")


def _span_word(q: str, today: date) -> Optional[Period]:
    for w, n in sorted(SPAN_WORD.items(), key=lambda kv: -len(kv[0])):
        i = q.find(w)
        if i >= 0 and q[i + len(w):].startswith(("평균", "에얼마", "치고")):
            continue                   # '하루 평균' 은 기간이 아니라 집계 단위다
        if w in q:
            return Period(today - timedelta(days=n - 1), today, f"최근 {n}일",
                          kind="range")
    return None


def _point_in_past(q: str, today: date) -> Optional[Period]:
    """'3일 전' 처럼 한 시점을 가리키는 말."""
    m = re.search(rf"({_NUM_RE})\s*일\s*전", q)
    if m:
        d = today - timedelta(days=_num(m.group(1)))
        return Period(d, d, _day_label(d, today))
    return None


def _vague(q: str, today: date) -> Optional[Period]:
    if any(k in q for k in ("요즘", "최근", "근래", "며칠", "요새", "요즈음", "얼마전")):
        return Period(today - timedelta(days=6), today, "최근 7일", kind="range")
    return None


def _bare_day(q: str, today: date) -> Optional[Period]:
    m = re.search(r"(?<!\d)(\d{1,2})\s*일(?!간|동안|치|째|전)", q)
    if not m:
        return None
    d = _same_month_day(int(m.group(1)), today)
    return Period(d, d, _day_label(d, today)) if d else None


# ---------------------------------------------------------------- 견주기
def previous_span(p: Period) -> Optional[Period]:
    """같은 길이의 바로 앞 구간. '지난주 대비' 의 기준으로 쓴다."""
    if p.start is None or p.end is None:
        return None
    n = p.days
    end = p.start - timedelta(days=1)
    start = end - timedelta(days=n - 1)
    이름 = {1: "그 전날"}.get(n, f"직전 {n}일")
    if p.label == "이번 주":
        이름 = "지난 주"
    elif p.label == "이번 달":
        이름 = "지난 달"
    elif p.label == "오늘":
        이름 = "어제"
    return Period(start, end, 이름, kind=p.kind)


def _baseline(q: str, p: Period, today: date) -> Optional[Period]:
    """'지난주 대비' 처럼 견줄 기준이 문장에 있으면 그것을."""
    if not any(k in q for k in _COMPARE_MARK):
        return None
    for 말, 만들기 in (("지난주", lambda: _weeks("지난주", today)),
                     ("저번주", lambda: _weeks("지난주", today)),
                     ("전주", lambda: _weeks("지난주", today)),
                     ("지난달", lambda: _months("지난달", today)),
                     ("전월", lambda: _months("지난달", today)),
                     ("어제", lambda: _relative_day("어제", today)),
                     ("그제", lambda: _relative_day("그제", today)),
                     ("작년", lambda: _years("작년", today))):
        if 말 in q:
            기준 = 만들기()
            if 기준 and (기준.start != p.start or 기준.end != p.end):
                return 기준
    return previous_span(p)


# ---------------------------------------------------------------- 걸러내기
_STAMP = re.compile(r"\s*(\d{4})[-./]?(\d{2})[-./]?(\d{2})(?:[ T]+(\d{1,2}):(\d{2}))?")


def when(text: str) -> Optional[tuple]:
    """'2026-09-17 09:31' 을 (date, 분) 으로. 못 읽으면 None."""
    m = _STAMP.match(text or "")
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    minute = None
    if m.group(4) is not None:
        minute = int(m.group(4)) * 60 + int(m.group(5))
    return d, minute


def in_period(text: str, period: Period) -> bool:
    """기록 한 줄의 날짜 칸이 이 기간에 드는지. 시각까지 본다."""
    if period is None:
        return True
    got = when(text)
    if got is None:
        return period.start is None and period.end is None
    d, minute = got
    if period.start is not None and d < period.start:
        return False
    if period.end is not None and d > period.end:
        return False
    if period.business_only and d.weekday() >= 5:
        return False
    if minute is not None:
        if period.time_start is not None and minute < period.time_start:
            return False
        if period.time_end is not None and minute > period.time_end:
            return False
    return True
