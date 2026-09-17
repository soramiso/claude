"""왜 그렇게 알아들었는지 보여 준다.

규칙 봇은 틀렸을 때 까닭을 알 수 있어야 고칠 수 있다. 어떤 말에 몇 점이
붙었고 어떤 규칙으로 뜻을 옮겼는지 적어 준다. 사전을 손볼 때 이것부터 본다.
"""

from __future__ import annotations

from typing import Iterable, Optional

from . import intents as I
from . import parse as P
from . import text as T


def explain(r: P.Reading) -> str:
    """읽어 낸 결과를 사람이 읽는 꼴로."""
    줄 = [f"질문      {r.raw}",
          f"뜻        {P.say_intent(r.intent)} ({r.intent}) · {r.score:.2f}점"
          f" · 여유 {r.margin:.2f} · {r.kind}"]
    if r.runners:
        경쟁 = ", ".join(f"{n} {s:.2f}" for n, s in r.runners)
        줄.append(f"경쟁       {경쟁}")
    줄.append(f"기간      {r.period.say()}  [{r.period.start} ~ {r.period.end}]"
              f"{'' if r.period.explicit else ' (말이 없어 오늘로 봄)'}")
    if r.baseline:
        줄.append(f"견줄 기준  {r.baseline.label} [{r.baseline.start} ~ {r.baseline.end}]")
    if r.stocks:
        줄.append(f"종목      {', '.join(s.label for s in r.stocks)}")
    슬롯 = [(이름, 값) for 이름, 값 in
           (("지표", r.metric), ("정렬", r.order), ("집계", r.agg),
            ("방향", r.side), ("고르기", r.want), ("몇 개", r.limit),
            ("몇 번째", r.ordinal), ("장부", r.mode)) if 값]
    if 슬롯:
        줄.append("슬롯      " + " · ".join(f"{k} {v}" for k, v in 슬롯))
    if r.constraints:
        줄.append("조건      " + " · ".join(c.say() for c in r.constraints))
    if r.keywords:
        줄.append(f"낱말      {', '.join(r.keywords)}")
    말투 = []
    if r.negated:
        말투.append("부정")
    if r.asked:
        말투.append("물음")
    말투.append(r.polite)
    줄.append("말투      " + " · ".join(말투))
    if r.inherited:
        줄.append(f"이어받음  {', '.join(r.inherited)}")
    if r.notes:
        줄.append("옮김      " + " · ".join(r.notes))
    if r.parts:
        줄.append(f"쪼갬      {' | '.join(r.parts)}")
    return "\n".join(줄)


def trace(question: str, catalog: Iterable = (), today=None) -> str:
    """점수가 어디서 왔는지까지. 사전을 고칠 때 본다."""
    r = P.understand(question, catalog, today=today)
    줄 = [explain(r), "", "점수 내역"]
    for s in I.score_detail(question, has_terms=bool(r.terms))[:6]:
        줄.append(f"  {s.name:15s} {s.score:5.2f}  {' '.join(s.why)}")
    줄.append("")
    줄.append(f"어간      {', '.join(sorted(T.stem_set(question))[:12])}")
    return "\n".join(줄)
