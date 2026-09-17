"""종목과 슬롯 집어내기."""

import unittest

import nlu
from nlu import entities as E

CAT = E.catalog_from([("삼성전자", "005930"), ("카카오", "035720"),
                      ("에코프로비엠", "247540"), ("LG화학", "051910"),
                      ("현대차", "005380")])


class 종목(unittest.TestCase):
    def 찾기(self, q):
        return [s.name for s in E.find_stocks(q, CAT)]

    def test_이름과_코드(self):
        self.assertEqual(self.찾기("삼성전자 왜 샀어"), ["삼성전자"])
        self.assertEqual(self.찾기("005930 왜 샀어"), ["삼성전자"])

    def test_줄임말(self):
        self.assertEqual(self.찾기("삼전 어때"), ["삼성전자"])
        self.assertEqual(self.찾기("엘지화학 어때"), ["LG화학"])
        self.assertIn("에코프로비엠", self.찾기("에코프로 어때"))

    def test_초성(self):
        self.assertEqual(self.찾기("ㅅㅅㅈㅈ 어때"), ["삼성전자"])

    def test_앞글자(self):
        self.assertEqual(self.찾기("삼성 수익"), ["삼성전자"])

    def test_한영_전환_실수(self):
        self.assertEqual(self.찾기("tkatjdwjswk 어때"), ["삼성전자"])

    def test_오타(self):
        self.assertEqual(self.찾기("삼송전자 왜 샀어"), ["삼성전자"])

    def test_여럿을_차례대로(self):
        self.assertEqual(self.찾기("카카오랑 삼성전자 왜 샀어"), ["카카오", "삼성전자"])

    def test_기록에_없는_코드도_받는다(self):
        찾음 = E.find_stocks("000660 왜 샀어", CAT)
        self.assertEqual(찾음[0].code, "000660")
        self.assertEqual(찾음[0].name, "")

    def test_흔한_말은_종목으로_보지_않는다(self):
        self.assertEqual(self.찾기("오늘 손익 얼마야"), [])
        self.assertEqual(self.찾기("보유종목 알려줘"), [])

    def test_사람이_붙인_별명(self):
        찾음 = E.find_stocks("우리 효자 어때", CAT, aliases={"효자": "삼성전자"})
        self.assertEqual(찾음[0].name, "삼성전자")

    def test_기록_한_줄과_맞춰보기(self):
        s = E.Stock("삼성전자", "005930")
        self.assertTrue(s.matches("005930", "삼성전자"))
        self.assertTrue(s.matches("삼성전자(005930) 조건 충족 매수"))
        self.assertFalse(s.matches("카카오(035720) 익절"))


class 슬롯(unittest.TestCase):
    def test_지표(self):
        self.assertEqual(E.find_metric("수익률 높은 순"), "수익률")
        self.assertEqual(E.find_metric("평단 얼마야"), "평단가")
        self.assertEqual(E.find_metric("오늘 뭐 샀어"), "")

    def test_정렬과_집계(self):
        self.assertEqual(E.find_order("많은 순으로"), "내림차순")
        self.assertEqual(E.find_order("적은 순으로"), "오름차순")
        self.assertEqual(E.find_agg("하루 평균 얼마"), "평균")
        self.assertEqual(E.find_agg("몇 건이야"), "개수")

    def test_이익과_손실_고르기(self):
        self.assertEqual(E.find_want("손실 난 종목만"), "lose")
        self.assertEqual(E.find_want("수익 난 종목"), "win")
        self.assertEqual(E.find_want("물린 거"), "lose")
        self.assertEqual(E.find_want("보유종목"), "")

    def test_사고판_방향(self):
        self.assertEqual(E.find_side("오늘 뭐 팔았어"), "매도")
        self.assertEqual(E.find_side("어제 산 거"), "매수")
        self.assertEqual(E.find_side("오늘 사고팔았어"), "")

    def test_장부_고르기(self):
        self.assertEqual(E.find_mode("모의 손익"), "가상매매")
        self.assertEqual(E.find_mode("가상매매 보유종목"), "가상매매")
        self.assertEqual(E.find_mode("오늘 손익"), "실제매매")

    def test_찾을_낱말(self):
        낱말 = E.find_keywords("일지에서 고점대비 찾아줘")
        self.assertIn("고점대비", 낱말)
        self.assertNotIn("일지", 낱말)

    def test_목록_만들기는_코드_있는_쪽을_남긴다(self):
        cat = E.catalog_from([("삼성전자", ""), ("삼성전자", "005930")])
        self.assertEqual(cat[0].code, "005930")
        self.assertEqual(len(cat), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
