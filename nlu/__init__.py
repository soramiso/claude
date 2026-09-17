"""말을 알아듣는 층.

바깥에서는 이 한 이름만 쓰면 된다. 속은 여섯 조각으로 나뉘어 있다.

  text       글자·자모·조사·어미·오타 — 모든 것의 바닥
  numbers    한글 수사, 금액, 퍼센트, "10만원 넘게" 같은 조건
  timeframe  "지난주", "9월 3일부터", "최근 5영업일", "장 마감 무렵"
  lexicon    어떤 말이 어떤 뜻으로 가는지 적어 둔 표
  entities   종목·지표·정렬·집계를 문장에서 집어냄
  intents    점수를 매겨 뜻을 고르고, 슬롯을 보고 더 좁은 뜻으로 옮김
  parse      위를 모아 Reading 한 덩이로. 앞 질문을 이어받는 일도 여기서

사전을 늘리려면 lexicon.py 만 손대면 되는 때가 많다. 왜 그렇게 알아들었는지
궁금하면 explain.trace(질문) 를 찍어 보면 된다.
"""

from __future__ import annotations

# 판 번호. rules.py 가 이 숫자를 보고 옛 nlu.py 가 잡혔는지 가려낸다.
# 바깥에 내보이는 이름이나 Reading 의 칸을 바꿀 때 하나 올린다.
VERSION = 2

from . import entities, explain, intents, lexicon, numbers, parse, text, timeframe

# --- 글자 ---------------------------------------------------------------
from .text import (CHOSUNG, JUNGSUNG, JONGSUNG, chosung, compose, decompose,
                   deflate, depunct, from_qwerty, has_batchim, has_negation,
                   is_chosung_only, is_question, is_smalltalk, jamo, josa,
                   looks_like_qwerty, normalize, politeness, similar, squash,
                   stem_set, stems, strip_josa, tokens, unconjugate)
# --- 숫자 ---------------------------------------------------------------
from .numbers import (Constraint, parse_amount, parse_constraints, parse_ko_number,
                      parse_limit, parse_ordinal, parse_percent, parse_quantity)
# --- 기간 ---------------------------------------------------------------
from .timeframe import (ALL, Period, business_days, in_period, month_bounds,
                        months_ago, parse_clock, parse_period, previous_span,
                        quarter_bounds, when)
# --- 사전과 종목 ---------------------------------------------------------
from .lexicon import ANSWERABLE, INTENTS, Intent
from .entities import Stock, abbrevs, catalog_from, find_stocks, find_metric
# --- 뜻 고르기 -----------------------------------------------------------
from .intents import THRESHOLD, margin, route, score_detail, score_intents
from .parse import (ANAPHORA, Dialogue, Reading, ambiguous, closest_examples,
                    say_intent, understand)
from .explain import explain as describe, trace

# 예전 이름. 쓰던 코드가 그대로 돌게 남겨 둔다.
abbrev = abbrevs

__all__ = [n for n in dir() if not n.startswith("_")]
