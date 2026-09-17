"""글자 다루는 바닥이 제대로 도는지."""

import unittest

from nlu import text as T


class 다듬기(unittest.TestCase):
    def test_띄어쓰기를_지운다(self):
        self.assertEqual(T.squash("이번 주 손익"), "이번주손익")

    def test_군더더기를_덜어낸다(self):
        self.assertEqual(T.deflate("아ㅋㅋㅋ 좀 오늘 손익"), "아 오늘 손익")
        self.assertEqual(T.deflate("오늘ㅠㅠ 손익"), "오늘 손익")

    def test_문장부호는_공백으로(self):
        self.assertEqual(T.depunct("오늘, 손익은?"), "오늘 손익은")

    def test_홀로_쓴_자모가_살아남는다(self):
        self.assertEqual(T.squash("ㅅㅅㅈㅈ"), "ㅅㅅㅈㅈ")


class 자모(unittest.TestCase):
    def test_풀고_붙이기(self):
        self.assertEqual(T.decompose("삵"), ("ㅅ", "ㅏ", "ㄺ"))
        self.assertEqual(T.compose("ㅅ", "ㅏ"), "사")
        self.assertEqual(T.compose("ㅅ", "ㅏ", "ㄺ"), "삵")
        self.assertEqual(T.jamo("승률"), "ㅅㅡㅇㄹㅠㄹ")

    def test_초성(self):
        self.assertEqual(T.chosung("삼성전자"), "ㅅㅅㅈㅈ")
        self.assertEqual(T.chosung("ㅅㅅㅈㅈ"), "ㅅㅅㅈㅈ")
        self.assertTrue(T.is_chosung_only("ㅅㅅㅈㅈ"))
        self.assertFalse(T.is_chosung_only("삼성"))


class 조사(unittest.TestCase):
    def test_뗀다(self):
        self.assertEqual(T.strip_josa("삼성전자는"), "삼성전자")
        self.assertEqual(T.strip_josa("카카오를"), "카카오")
        self.assertEqual(T.strip_josa("손익"), "손익")

    def test_받침을_보고_붙인다(self):
        self.assertEqual(T.josa("삼성전자", "은는"), "삼성전자는")
        self.assertEqual(T.josa("카카오", "은는"), "카카오는")
        self.assertEqual(T.josa("한글", "이가"), "한글이")
        self.assertEqual(T.josa("이번 주", "은는"), "이번 주는")
        self.assertEqual(T.josa("3", "이가"), "3이")
        self.assertEqual(T.josa("2", "이가"), "2가")
        self.assertEqual(T.josa("+100,000원", "로으로"), "+100,000원으로")
        self.assertEqual(T.josa("서울", "로으로"), "서울로")     # ㄹ 받침


class 어미(unittest.TestCase):
    def test_활용을_벗긴다(self):
        표 = {"팔았어": "팔", "파셨나요": "팔", "털었니": "털", "샀어": "사",
              "했음": "하", "판": "팔", "살까": "사", "벌었나": "벌",
              "물렸어": "물리", "깨졌다": "깨지", "매도한": "매도"}
        for 말, 어간 in 표.items():
            with self.subTest(말=말):
                self.assertEqual(T.unconjugate(말), 어간)

    def test_어간_후보에_사전꼴이_들어온다(self):
        self.assertIn("매도", T.stems("매도했지"))
        self.assertIn("매수", T.stems("매수했어요"))
        self.assertIn("팔", T.stems("팔았습니다"))

    def test_문장_어간_모음(self):
        어간 = T.stem_set("삼성전자 언제 팔았어?")
        self.assertIn("팔", 어간)


class 오타(unittest.TestCase):
    def test_자모로_견준다(self):
        self.assertGreater(T.similar("승률", "승율"), 0.8)
        self.assertGreater(T.similar("보유종목", "보유종묵"), 0.8)
        self.assertLess(T.similar("손익", "체결"), 0.5)

    def test_영타를_되돌린다(self):
        self.assertEqual(T.from_qwerty("tkatjdwjswk"), "삼성전자")
        self.assertTrue(T.looks_like_qwerty("tkatjdwjswk"))
        self.assertFalse(T.looks_like_qwerty("hello"))

    def test_사전에서_고른다(self):
        self.assertEqual(T.correct("보유종묵", ("보유종목", "체결내역")), "보유종목")
        self.assertEqual(T.correct("전혀다른말", ("보유종목",)), "전혀다른말")


class 말투(unittest.TestCase):
    def test_물음인지(self):
        self.assertTrue(T.is_question("오늘 손익은?"))
        self.assertTrue(T.is_question("얼마 벌었어"))
        self.assertFalse(T.is_question("오늘 손익"))

    def test_존대와_반말(self):
        self.assertEqual(T.politeness("알려주세요"), "존대")
        self.assertEqual(T.politeness("알려줘"), "반말")

    def test_부정(self):
        self.assertTrue(T.has_negation("안 팔았어?"))
        self.assertTrue(T.has_negation("체결 안 된 거"))
        self.assertFalse(T.has_negation("팔았어?"))

    def test_잡담(self):
        self.assertEqual(T.is_smalltalk("안녕"), "인사")
        self.assertEqual(T.is_smalltalk("고마워"), "감사")
        self.assertEqual(T.is_smalltalk("ㅋㅋㅋ"), "웃음")
        self.assertEqual(T.is_smalltalk("오늘 손익"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
