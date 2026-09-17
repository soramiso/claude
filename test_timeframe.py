"""기간 읽기. 오늘을 2026-09-17(목)로 고정해 놓고 본다."""

import unittest
from datetime import date

from nlu import timeframe as TF

T = date(2026, 9, 17)


class 기간(unittest.TestCase):
    def 본다(self, q):
        return TF.parse_period(q, T)

    def test_말이_없으면_오늘(self):
        p = self.본다("손익 알려줘")
        self.assertEqual((p.start, p.end, p.explicit), (T, T, False))

    def test_하루짜리(self):
        self.assertEqual(self.본다("어제").start, date(2026, 9, 16))
        self.assertEqual(self.본다("그저께").start, date(2026, 9, 15))
        self.assertEqual(self.본다("그끄저께").start, date(2026, 9, 14))
        self.assertEqual(self.본다("3일 전").start, date(2026, 9, 14))

    def test_주(self):
        self.assertEqual(self.본다("이번주").start, date(2026, 9, 14))
        self.assertEqual(self.본다("이번 주").start, date(2026, 9, 14))
        p = self.본다("지난주")
        self.assertEqual((p.start, p.end), (date(2026, 9, 7), date(2026, 9, 13)))
        self.assertEqual(self.본다("지지난주").start, date(2026, 8, 31))
        self.assertEqual(self.본다("3주 전").start, date(2026, 8, 24))

    def test_달(self):
        self.assertEqual(self.본다("이번 달").start, date(2026, 9, 1))
        p = self.본다("지난달")
        self.assertEqual((p.start, p.end), (date(2026, 8, 1), date(2026, 8, 31)))
        self.assertEqual(self.본다("지지난달").start, date(2026, 7, 1))
        self.assertEqual(self.본다("2달 전").start, date(2026, 7, 1))
        self.assertEqual(self.본다("월초").start, date(2026, 9, 1))

    def test_해와_분기(self):
        self.assertEqual(self.본다("올해").start, date(2026, 1, 1))
        self.assertEqual(self.본다("작년").end, date(2025, 12, 31))
        self.assertEqual(self.본다("재작년").start, date(2024, 1, 1))
        self.assertEqual(self.본다("2년 전").start, date(2024, 1, 1))
        self.assertEqual(self.본다("2024년").start, date(2024, 1, 1))
        self.assertEqual(self.본다("상반기").end, date(2026, 6, 30))
        self.assertEqual(self.본다("2분기").start, date(2026, 4, 1))
        self.assertEqual(self.본다("지난 분기").start, date(2026, 4, 1))

    def test_센_기간(self):
        self.assertEqual(self.본다("최근 5일").start, date(2026, 9, 13))
        self.assertEqual(self.본다("5일간").start, date(2026, 9, 13))
        self.assertEqual(self.본다("최근 2주").start, date(2026, 9, 4))
        self.assertEqual(self.본다("최근 3개월").start, date(2026, 6, 18))
        self.assertEqual(self.본다("열흘").start, date(2026, 9, 8))
        self.assertEqual(self.본다("보름").start, date(2026, 9, 3))
        self.assertEqual(self.본다("일주일").start, date(2026, 9, 11))

    def test_영업일은_주말을_뺀다(self):
        p = self.본다("최근 5영업일")
        self.assertTrue(p.business_only)
        self.assertEqual(p.start, date(2026, 9, 11))
        self.assertFalse(TF.in_period("2026-09-12 10:00", p))   # 토요일

    def test_또렷한_날짜(self):
        self.assertEqual(self.본다("9월 3일").start, date(2026, 9, 3))
        self.assertEqual(self.본다("2026-09-15").start, date(2026, 9, 15))
        self.assertEqual(self.본다("9/15").start, date(2026, 9, 15))
        self.assertEqual(self.본다("20260915").start, date(2026, 9, 15))
        p = self.본다("9월 3일부터 9월 10일까지")
        self.assertEqual((p.start, p.end), (date(2026, 9, 3), date(2026, 9, 10)))
        p = self.본다("9월 3일부터 10일까지")
        self.assertEqual((p.start, p.end), (date(2026, 9, 3), date(2026, 9, 10)))

    def test_한쪽만_적은_범위(self):
        p = self.본다("3일부터")
        self.assertEqual((p.start, p.end), (date(2026, 9, 3), T))
        p = self.본다("10일까지")
        self.assertEqual((p.start, p.end), (None, date(2026, 9, 10)))

    def test_숫자만_적은_날(self):
        self.assertEqual(self.본다("15일 손익").start, date(2026, 9, 15))
        self.assertEqual(self.본다("20일 체결").start, date(2026, 8, 20))

    def test_요일과_주말(self):
        self.assertEqual(self.본다("월요일").start, date(2026, 9, 14))
        self.assertEqual(self.본다("지난 월요일").start, date(2026, 9, 7))
        self.assertEqual(self.본다("주말").start, date(2026, 9, 12))

    def test_전체(self):
        self.assertIsNone(self.본다("전체 손익").start)
        self.assertIsNone(self.본다("누적 얼마야").start)

    def test_좁은_말이_전체보다_먼저다(self):
        self.assertEqual(self.본다("올해 누적").start, date(2026, 1, 1))
        self.assertEqual(self.본다("오늘 누적손익").start, T)
        self.assertEqual(self.본다("오전 체결").start, T)      # '오전체결' 의 '전체'

    def test_시각(self):
        p = self.본다("오전에 뭐 샀어")
        self.assertEqual((p.time_start, p.time_end), (540, 720))
        p = self.본다("장 마감 무렵")
        self.assertEqual((p.time_start, p.time_end), (870, 930))
        p = self.본다("9시부터 10시")
        self.assertEqual((p.time_start, p.time_end), (540, 600))

    def test_견줄_기준(self):
        p = self.본다("지난주 대비 이번주")
        self.assertEqual(p.start, date(2026, 9, 14))
        self.assertEqual(p.baseline.start, date(2026, 9, 7))
        p = self.본다("어제보다 오늘")
        self.assertEqual((p.start, p.baseline.start), (T, date(2026, 9, 16)))
        p = self.본다("지난주보다 나아졌어?")
        self.assertEqual(p.baseline.label, "지난 주")

    def test_직전_구간(self):
        앞 = TF.previous_span(self.본다("이번 주"))
        self.assertEqual(앞.label, "지난 주")
        self.assertEqual(TF.previous_span(self.본다("오늘")).label, "어제")


class 걸러내기(unittest.TestCase):
    def test_날짜_칸_읽기(self):
        self.assertEqual(TF.when("2026-09-17 09:31:00"), (date(2026, 9, 17), 571))
        self.assertEqual(TF.when("2026-09-17")[1], None)
        self.assertIsNone(TF.when("엉망"))

    def test_기간_안에_드는지(self):
        p = TF.parse_period("어제", T)
        self.assertTrue(TF.in_period("2026-09-16 09:31:00", p))
        self.assertFalse(TF.in_period("2026-09-17 09:31:00", p))
        self.assertFalse(TF.in_period("", p))
        self.assertTrue(TF.in_period("아무거나", TF.ALL))

    def test_시각까지_본다(self):
        p = TF.parse_period("오전 체결", T)
        self.assertTrue(TF.in_period("2026-09-17 09:31:00", p))
        self.assertFalse(TF.in_period("2026-09-17 14:02:00", p))

    def test_영업일만(self):
        self.assertEqual(len(TF.business_days(date(2026, 9, 14), date(2026, 9, 20))), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
