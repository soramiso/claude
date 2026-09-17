"""평가 표로 점수를 낸다. 기준을 밑돌면 실패한다."""

import unittest
from datetime import date

import eval_set
import nlu

CAT = nlu.catalog_from([("삼성전자", "005930"), ("카카오", "035720"),
                        ("에코프로비엠", "247540"), ("LG화학", "051910")])
T = date(2026, 9, 17)

# 기준선. 사전을 고쳐 올라가면 이 숫자도 함께 올린다.
MIN_INTENT = 0.93
MIN_ANSWERABLE = 0.95


def 읽기(q):
    return nlu.understand(q, CAT, today=T)


def 점수():
    맞음, 틀림 = 0, []
    for 질문, 기대 in eval_set.INTENT_CASES:
        got = 읽기(질문).intent
        if got == 기대:
            맞음 += 1
        else:
            틀림.append((질문, 기대, got))
    return 맞음 / len(eval_set.INTENT_CASES), 틀림


class 의도평가(unittest.TestCase):
    def test_전체_정확도(self):
        비율, 틀림 = 점수()
        보고 = "\n".join(f"    {q}  기대 {want}  나온 것 {got}" for q, want, got in 틀림)
        self.assertGreaterEqual(
            비율, MIN_INTENT,
            f"\n정확도 {비율:.1%} (기준 {MIN_INTENT:.0%})\n틀린 것 {len(틀림)}개:\n{보고}")

    def test_기록으로_답할_것을_바깥으로_보내지_않는다(self):
        샘 = []
        for 질문, 기대 in eval_set.INTENT_CASES:
            if 기대 not in nlu.ANSWERABLE:
                continue
            r = 읽기(질문)
            if r.kind != "기록":
                샘.append((질문, r.intent))
        self.assertFalse(샘, f"기록으로 답할 물음이 새 나갔습니다: {샘}")

    def test_기록_밖_물음은_기록으로_답하지_않는다(self):
        샘 = []
        for 질문, 기대 in eval_set.INTENT_CASES:
            if 기대 not in ("forecast", "howto", "market"):
                continue
            r = 읽기(질문)
            if r.kind != "바깥":
                샘.append((질문, r.intent))
        self.assertFalse(샘, f"앞일·설정 물음을 기록으로 답하려 합니다: {샘}")

    def test_말버릇이_달라도_같은_뜻(self):
        for 기대, 질문들 in eval_set.PARAPHRASE_GROUPS:
            for q in 질문들:
                with self.subTest(q=q):
                    self.assertEqual(읽기(q).intent, 기대)

    def test_기간_표현(self):
        for 질문, 라벨 in eval_set.PERIOD_CASES:
            with self.subTest(q=질문):
                self.assertEqual(nlu.parse_period(질문, T).label, 라벨)

    def test_모르는_말은_모른다고_한다(self):
        for q in ("김치찌개 레시피", "오늘 날씨 어때", "ㅁㄴㅇㄹ", "3 + 4는?"):
            with self.subTest(q=q):
                self.assertEqual(읽기(q).intent, "unknown")


if __name__ == "__main__":
    비율, 틀림 = 점수()
    print(f"의도 정확도 {비율:.1%}  ({len(eval_set.INTENT_CASES) - len(틀림)}"
          f"/{len(eval_set.INTENT_CASES)})")
    for q, want, got in 틀림:
        print(f"  틀림  {q:28s} 기대 {want:12s} 나온 것 {got}")
