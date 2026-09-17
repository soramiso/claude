"""말을 알아듣는 층이 제대로 도는지 본다. 기록 파일 없이 문장만 본다."""

import unittest
from datetime import date

import nlu

T = date(2026, 9, 17)          # 목요일


class 다듬기(unittest.TestCase):
    def test_띄어쓰기를_지운다(self):
        self.assertEqual(nlu.squash("이번 주 손익"), "이번주손익")

    def test_조사를_뗀다(self):
        self.assertEqual(nlu.strip_josa("삼성전자는"), "삼성전자")
        self.assertEqual(nlu.strip_josa("카카오를"), "카카오")
        self.assertEqual(nlu.strip_josa("손익"), "손익")      # 두 글자는 안 건드린다

    def test_초성(self):
        self.assertEqual(nlu.chosung("삼성전자"), "ㅅㅅㅈㅈ")
        self.assertEqual(nlu.chosung("ㅅㅅㅈㅈ"), "ㅅㅅㅈㅈ")

    def test_줄임말(self):
        self.assertIn("삼전", nlu.abbrev("삼성전자"))

    def test_오타를_자모로_견준다(self):
        self.assertGreater(nlu.similar("승률", "승율"), 0.8)

    def test_조사_붙이기(self):
        self.assertEqual(nlu.josa("삼성전자", "은는"), "삼성전자는")
        self.assertEqual(nlu.josa("카카오", "은는"), "카카오는")
        self.assertEqual(nlu.josa("한글", "이가"), "한글이")
        self.assertEqual(nlu.josa("오늘", "은는"), "오늘은")
        self.assertEqual(nlu.josa("이번 주", "은는"), "이번 주는")
        self.assertEqual(nlu.josa("3", "이가"), "3이")
        self.assertEqual(nlu.josa("2", "이가"), "2가")


class 기간(unittest.TestCase):
    def 본다(self, q):
        return nlu.parse_period(q, T)

    def test_기본은_오늘(self):
        p = self.본다("손익 알려줘")
        self.assertEqual((p.start, p.end, p.explicit), (T, T, False))

    def test_어제_그저께(self):
        self.assertEqual(self.본다("어제 손익").start, date(2026, 9, 16))
        self.assertEqual(self.본다("그저께 손익").start, date(2026, 9, 15))

    def test_주(self):
        self.assertEqual(self.본다("이번주 승률").start, date(2026, 9, 14))
        self.assertEqual(self.본다("이번 주 승률").start, date(2026, 9, 14))
        p = self.본다("지난주 성적")
        self.assertEqual((p.start, p.end), (date(2026, 9, 7), date(2026, 9, 13)))
        self.assertEqual(self.본다("지지난주").start, date(2026, 8, 31))

    def test_달과_해(self):
        self.assertEqual(self.본다("이번 달 손익").start, date(2026, 9, 1))
        p = self.본다("지난달 수익")
        self.assertEqual((p.start, p.end), (date(2026, 8, 1), date(2026, 8, 31)))
        self.assertEqual(self.본다("올해 수익").start, date(2026, 1, 1))
        self.assertEqual(self.본다("작년 수익").end, date(2025, 12, 31))

    def test_센_날수(self):
        self.assertEqual(self.본다("최근 5일 수익").start, date(2026, 9, 13))
        self.assertEqual(self.본다("5일간 손익").start, date(2026, 9, 13))
        self.assertEqual(self.본다("최근 2주 흐름").start, date(2026, 9, 4))
        self.assertEqual(self.본다("열흘 손익").start, date(2026, 9, 8))
        self.assertEqual(self.본다("일주일 수익").start, date(2026, 9, 11))
        self.assertEqual(self.본다("최근 3개월").start, date(2026, 6, 18))

    def test_또렷한_날짜(self):
        self.assertEqual(self.본다("9월 3일 손익").start, date(2026, 9, 3))
        self.assertEqual(self.본다("2026-09-15 체결").start, date(2026, 9, 15))
        self.assertEqual(self.본다("9/15 체결").start, date(2026, 9, 15))
        p = self.본다("9월 3일부터 9월 10일까지 매매")
        self.assertEqual((p.start, p.end), (date(2026, 9, 3), date(2026, 9, 10)))

    def test_숫자만_적은_날(self):
        self.assertEqual(self.본다("15일 손익").start, date(2026, 9, 15))
        self.assertEqual(self.본다("20일 체결").start, date(2026, 8, 20))   # 아직 안 온 날

    def test_요일(self):
        self.assertEqual(self.본다("월요일 손익").start, date(2026, 9, 14))

    def test_전체(self):
        self.assertIsNone(self.본다("전체 손익").start)
        self.assertIsNone(self.본다("누적 얼마야").start)

    def test_전체보다_구체적인_말이_이긴다(self):
        self.assertEqual(self.본다("올해 누적").start, date(2026, 1, 1))
        self.assertEqual(self.본다("오늘 누적손익").start, T)

    def test_기간_안에_드는지(self):
        p = self.본다("어제")
        self.assertTrue(nlu.in_period("2026-09-16 09:31:00", p))
        self.assertFalse(nlu.in_period("2026-09-17 09:31:00", p))
        self.assertFalse(nlu.in_period("", p))
        self.assertTrue(nlu.in_period("아무거나", self.본다("전체")))


class 의도(unittest.TestCase):
    CAT = (nlu.Stock("삼성전자", "005930"), nlu.Stock("카카오", "035720"))

    def 본다(self, q, terms=()):
        return nlu.understand(q, self.CAT, terms, today=T)

    def test_고른다(self):
        표 = {
            "오늘 손익은?": "pnl", "이번 주 얼마 벌었어?": "pnl",
            "보유종목 알려줘": "holdings", "지금 뭐 들고 있나": "holdings",
            "오늘 체결 내역": "trades", "어제 뭐 사고팔았어": "trades",
            "이번 주 승률": "winrate", "오늘 성적 어때": "winrate",
            "요약해줘": "summary", "별일 없지?": "summary",
            "제일 많이 번 종목": "ranking", "총자산 얼마야": "asset",
            "최근 흐름 보여줘": "trend", "도움말": "help",
            "삼성전자는 왜 팔았어?": "why", "오늘 왜 이렇게 깨졌지": "why",
            "삼성전자 어때?": "stock", "삼전 수익 얼마야": "stock",
        }
        for q, want in 표.items():
            with self.subTest(q=q):
                self.assertEqual(self.본다(q).intent, want)

    def test_모르면_모른다고_한다(self):
        self.assertEqual(self.본다("김치찌개 레시피 알려줘").intent, "unknown")
        self.assertEqual(self.본다("").intent, "unknown")

    def test_오타를_봐준다(self):
        self.assertEqual(self.본다("보유종묵 알려줘").intent, "holdings")
        self.assertEqual(self.본다("승율 어때").intent, "winrate")

    def test_종목을_집어낸다(self):
        self.assertEqual(self.본다("삼성전자 왜 샀어").stocks[0].name, "삼성전자")
        self.assertEqual(self.본다("005930 왜 샀어").stocks[0].name, "삼성전자")
        self.assertEqual(self.본다("삼전 어때").stocks[0].name, "삼성전자")
        self.assertEqual(self.본다("ㅅㅅㅈㅈ 어때").stocks[0].name, "삼성전자")
        self.assertEqual(self.본다("삼성 어때").stocks[0].name, "삼성전자")
        self.assertEqual(self.본다("카카오랑 삼성전자 왜 샀어").stocks[0].name, "카카오")

    def test_모르는_코드도_받는다(self):
        r = self.본다("000660 왜 샀어")
        self.assertEqual(r.stocks[0].code, "000660")

    def test_모의와_실제를_가른다(self):
        self.assertEqual(self.본다("모의 손익").mode, "가상매매")
        self.assertEqual(self.본다("오늘 손익").mode, "실제매매")

    def test_이익_손실_추리기(self):
        self.assertEqual(self.본다("손실 난 종목만 보여줘").want, "lose")
        self.assertEqual(self.본다("플러스인 종목").want, "win")

    def test_이익_손실만_말해도_보유로_본다(self):
        self.assertEqual(self.본다("물린 거 있어?").intent, "holdings")
        self.assertEqual(self.본다("플러스인 종목만").intent, "holdings")

    def test_앞_질문에_이어_묻기(self):
        첫 = self.본다("오늘 손익")
        이어 = nlu.understand("그럼 어제는?", self.CAT, last=첫, today=T)
        self.assertEqual(이어.intent, "pnl")
        self.assertEqual(이어.period.start, date(2026, 9, 16))
        self.assertTrue(이어.followup)

    def test_두_가지를_한꺼번에(self):
        r = self.본다("오늘 손익이랑 보유종목 알려줘")
        self.assertEqual(len(r.parts), 2)

    def test_한_가지면_쪼개지_않는다(self):
        self.assertEqual(self.본다("삼성전자랑 카카오 왜 샀어").parts, ())


if __name__ == "__main__":
    unittest.main(verbosity=2)
