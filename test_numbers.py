"""숫자와 조건 읽기."""

import unittest

from nlu import numbers as N


class 수사(unittest.TestCase):
    def test_한글_수사(self):
        표 = {"삼천오백만": 35_000_000, "스물셋": 23, "십만": 100_000,
              "이만오천": 25_000, "천만": 10_000_000, "오백": 500,
              "서른다섯": 35, "1억": 100_000_000, "백만": 1_000_000}
        for 말, 값 in 표.items():
            with self.subTest(말=말):
                self.assertEqual(N.parse_ko_number(말), 값)

    def test_못_읽으면_None(self):
        self.assertIsNone(N.parse_ko_number("손익"))
        self.assertIsNone(N.parse_ko_number(""))


class 금액(unittest.TestCase):
    def test_단위를_붙인다(self):
        표 = {"10만원": 100_000, "1.5억": 150_000_000, "천만원": 10_000_000,
              "3천원": 3_000, "오백만원": 5_000_000, "5만원어치": 50_000}
        for 말, 값 in 표.items():
            with self.subTest(말=말):
                self.assertEqual(N.parse_amount(말), 값)

    def test_퍼센트(self):
        self.assertEqual(N.parse_percent("5% 이상"), 5.0)
        self.assertEqual(N.parse_percent("-3.2% 났어"), -3.2)
        self.assertEqual(N.parse_percent("오프로"), 5.0)
        self.assertIsNone(N.parse_percent("손익"))

    def test_수량(self):
        self.assertEqual(N.parse_quantity("10주 샀어"), 10)
        self.assertEqual(N.parse_quantity("세 종목"), 3)


class 조건(unittest.TestCase):
    def 하나(self, 말):
        것 = N.parse_constraints(말)
        self.assertTrue(것, f"조건을 못 읽음: {말}")
        return 것[0]

    def test_이상과_초과를_가른다(self):
        self.assertEqual(self.하나("10만원 이상 번 종목").op, ">=")
        self.assertEqual(self.하나("10만원 넘게 번 종목").op, ">")
        self.assertEqual(self.하나("3주 미만").op, "<")
        self.assertEqual(self.하나("5% 이하").op, "<=")
        self.assertEqual(self.하나("30만원쯤").op, "~")

    def test_종류와_값(self):
        c = self.하나("10만원 이상")
        self.assertEqual((c.kind, c.value), ("금액", 100_000))
        c = self.하나("5% 넘게 빠진 거")
        self.assertEqual((c.kind, c.value), ("비율", 5.0))

    def test_값이_드는지_본다(self):
        c = self.하나("10만원 이상")
        self.assertTrue(c.hit(150_000))
        self.assertFalse(c.hit(50_000))

    def test_사람이_읽는_꼴(self):
        self.assertEqual(self.하나("10만원 이상").say(), "100,000원 이상")

    def test_견줌말이_없으면_조건이_아니다(self):
        self.assertEqual(N.parse_constraints("10주 샀어"), ())


class 개수(unittest.TestCase):
    def test_몇_개를_볼지(self):
        self.assertEqual(N.parse_limit("상위 3개"), 3)
        self.assertEqual(N.parse_limit("세 종목만"), 3)
        self.assertEqual(N.parse_limit("탑5"), 5)
        self.assertIsNone(N.parse_limit("제일 많이 번 종목"))

    def test_몇_번째(self):
        self.assertEqual(N.parse_ordinal("두 번째"), 2)
        self.assertEqual(N.parse_ordinal("3번째"), 3)
        self.assertEqual(N.parse_ordinal("첫 번째"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
