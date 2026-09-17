"""숫자와 조건을 읽는다.

"10만원 넘게 번 종목", "5% 이상 빠진 것", "3주 미만" 같은 말에서 숫자와
견줌말을 꺼낸다. 한글 수사("삼천오백만")와 아라비아 숫자, 둘을 섞어 쓴 것
("1억5천")까지 받는다. 뜻을 붙이는 일은 entities 가 한다.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional

from . import text as T

# ---------------------------------------------------------------- 수사
DIGIT = {"영": 0, "공": 0, "일": 1, "하나": 1, "한": 1, "이": 2, "둘": 2, "두": 2,
         "삼": 3, "셋": 3, "세": 3, "석": 3, "사": 4, "넷": 4, "네": 4, "넉": 4,
         "오": 5, "다섯": 5, "육": 6, "여섯": 6, "칠": 7, "일곱": 7,
         "팔": 8, "여덟": 8, "구": 9, "아홉": 9}
SMALL_UNIT = {"십": 10, "백": 100, "천": 1000}
BIG_UNIT = {"만": 10 ** 4, "억": 10 ** 8, "조": 10 ** 12}

NATIVE = {"하나": 1, "둘": 2, "셋": 3, "넷": 4, "다섯": 5, "여섯": 6, "일곱": 7,
          "여덟": 8, "아홉": 9, "열": 10, "스물": 20, "서른": 30, "마흔": 40,
          "쉰": 50, "예순": 60, "일흔": 70, "여든": 80, "아흔": 90}

_NUM_TOKEN = re.compile(
    r"(\d+(?:\.\d+)?)|(" + "|".join(
        sorted(list(DIGIT) + list(SMALL_UNIT) + list(BIG_UNIT) + list(NATIVE),
               key=len, reverse=True)) + r")")

# 낱말로 굳은 수. 바깥에서도 쓴다.
WORD_NUMBER = dict(NATIVE)
WORD_NUMBER.update({"한": 1, "두": 2, "세": 3, "네": 4, "석": 3, "넉": 4,
                    "다섯": 5, "보름": 15, "반": 0.5})


def parse_ko_number(chunk: str) -> Optional[float]:
    """'삼천오백만', '1억5천', '스물셋' 을 숫자로. 못 읽으면 None."""
    s = T.squash(chunk)
    if not s:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return float(s)

    total, section, num, seen = 0.0, 0.0, 0.0, False
    pos = 0
    while pos < len(s):
        m = _NUM_TOKEN.match(s, pos)
        if not m:
            break
        seen = True
        pos = m.end()
        if m.group(1):
            num = float(m.group(1))
            continue
        w = m.group(2)
        if w in BIG_UNIT:
            total += ((section + num) or 1) * BIG_UNIT[w]
            section = num = 0.0
        elif w in SMALL_UNIT:
            section += (num or 1) * SMALL_UNIT[w]
            num = 0.0
        elif w in NATIVE and w not in DIGIT:
            num = num + NATIVE[w] if num and num < 10 else NATIVE[w]
        else:
            d = DIGIT[w]
            if num >= 10 and num % 10 == 0 and d < 10:
                num += d                      # 스물 + 셋
            elif 0 < num < 10:
                num = num * 10 + d            # 자리를 이어 읽는 경우
            else:
                num = d
    if not seen:
        return None
    return total + section + num


# ---------------------------------------------------------------- 단위
_AMOUNT_RE = re.compile(
    r"(?P<num>(?:\d+(?:\.\d+)?|[영공일이삼사오육칠팔구십백천만억조한두세네다섯여섯일곱여덟아홉열스물서른마흔쉰예순일흔여든아흔]+))"
    r"\s*(?P<unit>조|억|만원|만|천원|천|원|월|주|퍼센트|퍼|프로|%|배|건|번|개|주식)?")

MONEY_UNIT = {"조": 10 ** 12, "억": 10 ** 8, "만원": 10 ** 4, "만": 10 ** 4,
              "천원": 1000, "천": 1000, "원": 1}


def parse_amount(chunk: str) -> Optional[float]:
    """'10만원', '1.5억', '삼천만' 을 원 단위 숫자로."""
    s = T.squash(chunk)
    m = re.search(r"([\d.,]+|[영공일이삼사오육칠팔구십백천만억조한두세네]+)\s*"
                  r"(조|억|만원|만|천원|천|원)", s)
    if not m:
        return None
    head, unit = m.group(1).replace(",", ""), m.group(2)
    if re.fullmatch(r"\d+(?:\.\d+)?", head):
        base = float(head)
    else:
        base = parse_ko_number(head + ("" if unit in ("원",) else ""))
        if base is None:
            return None
        if unit not in ("원",) and head and head[-1] in SMALL_UNIT:
            return base            # '삼천만' 처럼 이미 단위가 섞인 꼴
    mult = MONEY_UNIT.get(unit, 1)
    if unit in ("만원", "천원", "원"):
        return base * (MONEY_UNIT[unit] if unit != "원" else 1)
    return base * mult


def parse_percent(chunk: str) -> Optional[float]:
    """'5%', '5퍼', '오프로', '-3.2%' 를 숫자로."""
    s = T.squash(chunk)
    m = re.search(r"([+-]?\d+(?:\.\d+)?)\s*(?:%|퍼센트|퍼|프로)", s)
    if m:
        return float(m.group(1))
    m = re.search(r"([영공일이삼사오육칠팔구십백]+)\s*(?:%|퍼센트|퍼|프로)", s)
    if m:
        return parse_ko_number(m.group(1))
    return None


def parse_quantity(chunk: str) -> Optional[int]:
    """'10주', '세 주', '100개' 에서 개수를."""
    s = T.squash(chunk)
    m = re.search(r"([\d,]+|[한두세네다섯여섯일곱여덟아홉열스물서른일이삼사오육칠팔구십백천]+)"
                  r"\s*(?:주|개|종목|건|번)", s)
    if not m:
        return None
    head = m.group(1).replace(",", "")
    n = float(head) if head.isdigit() else parse_ko_number(head)
    return int(n) if n is not None else None


# ---------------------------------------------------------------- 견줌
GE = ("이상", "넘게", "넘는", "넘은", "넘어", "초과", "위로", "이상인", "보다많",
      "보다크", "부터", "以上")
LE = ("이하", "미만", "아래", "안되", "안 되", "못미치", "밑으로", "이내", "까지만",
      "보다적", "보다작")
EQ = ("정확히", "딱", "꼭", "만큼")
APPROX = ("쯤", "정도", "가량", "안팎", "내외", "즈음", "쯤은")

_STRICT_GE = ("넘게", "넘는", "넘은", "넘어", "초과")
_STRICT_LE = ("미만", "아래", "안되", "안 되", "못미치", "밑으로")


class Constraint(NamedTuple):
    """'10만원 이상' 하나를 담는다."""
    kind: str          # 금액 | 비율 | 수량 | 횟수 | 기간
    op: str            # >= > <= < == ~
    value: float
    unit: str
    raw: str

    def hit(self, v: float) -> bool:
        """값 하나가 이 조건에 드는지."""
        if self.op == ">=":
            return v >= self.value
        if self.op == ">":
            return v > self.value
        if self.op == "<=":
            return v <= self.value
        if self.op == "<":
            return v < self.value
        if self.op == "==":
            return abs(v - self.value) < 1e-9
        return abs(v - self.value) <= max(abs(self.value) * 0.1, 1)

    def say(self) -> str:
        """사람이 읽는 꼴로. 답에 '무엇으로 걸렀는지' 적을 때 쓴다."""
        숫자 = (f"{self.value:,.0f}" if self.kind != "비율"
                else f"{self.value:g}")
        단위 = {"금액": "원", "비율": "%", "수량": "주", "횟수": "번", "기간": "일"}
        말 = {">=": "이상", ">": "넘는", "<=": "이하", "<": "미만",
              "==": "인", "~": "쯤인"}
        return f"{숫자}{단위.get(self.kind, self.unit)} {말.get(self.op, '')}".strip()


_UNIT_KIND = {"원": "금액", "만원": "금액", "천원": "금액", "만": "금액",
              "억": "금액", "조": "금액", "천": "금액",
              "%": "비율", "퍼": "비율", "퍼센트": "비율", "프로": "비율",
              "주": "수량", "개": "수량", "종목": "수량",
              "건": "횟수", "번": "횟수", "회": "횟수",
              "일": "기간", "주일": "기간", "개월": "기간", "달": "기간"}

_CHUNK_RE = re.compile(
    r"(?P<num>[\d][\d,.]*|[영공일이삼사오육칠팔구십백천만억조한두세네다섯여섯일곱여덟아홉열]+)"
    r"\s*(?P<unit>만원|천원|퍼센트|주일|개월|원|만|억|조|천|%|퍼|프로|주|개|종목|건|번|회|일|달)"
    r"\s*(?P<tail>이상인|이하인|미만인|초과인|이상|이하|미만|초과|넘게|넘는|넘은|넘어|"
    r"아래|위로|이내|정도|가량|안팎|내외|쯤|딱|정확히)?")


def parse_constraints(sentence: str) -> tuple:
    """문장에 있는 조건을 모두 꺼낸다. 없으면 빈 묶음."""
    s = T.squash(sentence)
    out = []
    for m in _CHUNK_RE.finditer(s):
        unit, tail = m.group("unit"), m.group("tail") or ""
        kind = _UNIT_KIND.get(unit, "수량")
        head = m.group("num").replace(",", "")
        value = float(head) if re.fullmatch(r"\d+(?:\.\d+)?", head) else parse_ko_number(head)
        if value is None:
            continue
        if kind == "금액":
            value *= MONEY_UNIT.get(unit, 1)
        op = ""
        if any(k in tail for k in _STRICT_GE):
            op = ">"
        elif any(k in tail for k in _STRICT_LE):
            op = "<"
        elif "이상" in tail or "위로" in tail:
            op = ">="
        elif "이하" in tail or "이내" in tail:
            op = "<="
        elif any(k in tail for k in APPROX):
            op = "~"
        elif any(k in tail for k in EQ):
            op = "=="
        if not op:
            continue                      # 견줌말이 없으면 그냥 숫자다
        out.append(Constraint(kind, op, value, unit, m.group(0)))
    return tuple(out)


def parse_limit(sentence: str) -> Optional[int]:
    """'상위 3개', '탑5', '세 종목만' 에서 몇 개를 볼지."""
    s = T.squash(sentence)
    m = re.search(r"(?:상위|하위|탑|top|베스트|워스트)\s*(\d{1,2})", s)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{1,2}|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*(?:개|종목|건|줄)"
                  r"\s*(?:만|정도)?", s)
    if m:
        head = m.group(1)
        return int(head) if head.isdigit() else int(WORD_NUMBER.get(head, 0)) or None
    if any(k in s for k in ("제일", "가장", "최고", "최악", "첫", "톱")):
        return None
    return None


def parse_ordinal(sentence: str) -> Optional[int]:
    """'세 번째', '2번째' 처럼 몇 번째인지."""
    s = T.squash(sentence)
    m = re.search(r"(\d{1,2}|첫|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*(?:번째|째)", s)
    if not m:
        return None
    head = m.group(1)
    if head.isdigit():
        return int(head)
    return 1 if head == "첫" else int(WORD_NUMBER.get(head, 0)) or None
