"""문장 하나를 끝까지 읽어 내는 층."""

import unittest
from datetime import date

import nlu

CAT = nlu.catalog_from([("삼성전자", "005930"), ("카카오", "035720"),
                        ("에코프로비엠", "247540")])
T = date(2026, 9, 17)


def 읽기(q, **kw):
    kw.setdefault("today", T)
    return nlu.understand(q, CAT, **kw)


class 슬롯모으기(unittest.TestCase):
    def test_한꺼번에_읽는다(self):
        r = 읽기("지난주 대비 이번주 삼전 수익률 어때?")
        self.assertEqual(r.period.label, "이번 주")
        self.assertEqual(r.baseline.label, "지난 주")
        self.assertEqual(r.stocks[0].name, "삼성전자")
        self.assertEqual(r.metric, "수익률")

    def test_조건과_정렬과_개수(self):
        r = 읽기("10만원 넘게 번 종목만 많은 순으로 3개")
        self.assertEqual(r.want, "win")
        self.assertEqual(r.order, "내림차순")
        self.assertEqual(r.limit, 3)
        self.assertEqual(r.constraints[0].value, 100_000)

    def test_말투도_읽는다(self):
        r = 읽기("체결 안 된 거 있나요?")
        self.assertTrue(r.negated)
        self.assertTrue(r.asked)
        self.assertEqual(r.polite, "존대")

    def test_기록_밖_물음은_갈라_둔다(self):
        self.assertEqual(읽기("내일 뭐 살까").kind, "바깥")
        self.assertEqual(읽기("오늘 손익").kind, "기록")
        self.assertEqual(읽기("안녕").kind, "대화")
        self.assertTrue(읽기("내일 뭐 살까").hint())


class 옮김(unittest.TestCase):
    def test_종목을_짚으면_그_종목_이야기(self):
        self.assertEqual(읽기("삼성전자 수익 얼마야").intent, "stock")

    def test_평균을_물으면_평균(self):
        self.assertEqual(읽기("하루 평균 얼마 벌어").intent, "average")

    def test_견줄_기준이_있으면_비교(self):
        self.assertEqual(읽기("지난주 대비 어때").intent, "compare")

    def test_정렬을_물으면_순위(self):
        self.assertEqual(읽기("수익률 높은 순으로").intent, "ranking")

    def test_종목만_말하면_그_종목(self):
        self.assertEqual(읽기("삼성전자").intent, "stock")

    def test_옮긴_까닭을_남긴다(self):
        self.assertTrue(읽기("삼성전자 수익 얼마야").notes)


class 이어묻기(unittest.TestCase):
    def test_기간만_바꿔_묻기(self):
        첫 = 읽기("오늘 손익")
        둘 = 읽기("그럼 어제는?", last=첫)
        self.assertEqual(둘.intent, "pnl")
        self.assertEqual(둘.period.start, date(2026, 9, 16))
        self.assertTrue(둘.followup)

    def test_기간과_상관없는_물음_뒤에는_손익으로(self):
        첫 = 읽기("보유종목")
        둘 = 읽기("그럼 어제는?", last=첫)
        self.assertEqual(둘.intent, "pnl")

    def test_앞_종목을_이어받는다(self):
        첫 = 읽기("삼성전자 어때")
        둘 = 읽기("그건 왜 샀어?", last=첫)
        self.assertEqual(둘.intent, "why")
        self.assertEqual(둘.stocks[0].name, "삼성전자")
        self.assertIn("종목", 둘.inherited)

    def test_잡담은_이어받지_않는다(self):
        첫 = 읽기("오늘 손익")
        self.assertEqual(읽기("고마워", last=첫).intent, "thanks")


class 쪼개기(unittest.TestCase):
    def test_두_가지를_한꺼번에(self):
        self.assertEqual(len(읽기("오늘 손익이랑 보유종목 알려줘").parts), 2)

    def test_종목_나열은_쪼개지_않는다(self):
        self.assertEqual(읽기("삼성전자랑 카카오 왜 샀어").parts, ())
        self.assertEqual(len(읽기("삼성전자랑 카카오 왜 샀어").stocks), 2)


class 되묻기(unittest.TestCase):
    def test_모르면_모른다고(self):
        for q in ("김치찌개 레시피", "", "ㅁㄴㅇㄹ"):
            self.assertEqual(읽기(q).intent, "unknown")

    def test_비슷한_예시를_내민다(self):
        보기 = nlu.closest_examples("오늘 얼마 벌었나")
        self.assertTrue(보기)
        self.assertTrue(all(isinstance(b, str) for b in 보기))

    def test_헷갈리면_후보를_준다(self):
        r = 읽기("오늘 손익")
        self.assertIsInstance(nlu.ambiguous(r), tuple)

    def test_뜻을_사람_말로(self):
        self.assertEqual(nlu.say_intent("pnl"), "손익")


class 대화(unittest.TestCase):
    def test_여러_턴을_기억한다(self):
        d = nlu.Dialogue(CAT, today=T)
        d.remember(d.read("삼성전자 어때"))
        r = d.read("그건 왜 샀어?")
        self.assertEqual(r.stocks[0].name, "삼성전자")
        d.forget()
        self.assertIsNone(d.last)

    def test_기억은_몇_턴만(self):
        d = nlu.Dialogue(CAT, today=T, keep=3)
        for _ in range(5):
            d.remember(d.read("오늘 손익"))
        self.assertEqual(len(d.history), 3)


class 설명(unittest.TestCase):
    def test_왜_그렇게_읽었는지_보여준다(self):
        말 = nlu.trace("삼성전자 왜 팔았어?", CAT, T)
        self.assertIn("삼성전자", 말)
        self.assertIn("점수 내역", 말)
        self.assertIn("why", 말)


if __name__ == "__main__":
    unittest.main(verbosity=2)
