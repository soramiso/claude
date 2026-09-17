"""답 만드는 층. 가짜 CSV 를 만들어 놓고 실제로 물어본다."""

import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import rules

오늘 = date.today()
어제 = 오늘 - timedelta(days=1)


def 날(d, hhmm="09:31"):
    return f"{d.isoformat()} {hhmm}:00"


class 기록:
    """시험용 폴더. 봇이 쓰는 파일 네 가지를 만들어 둔다."""

    def __init__(self):
        self.base = Path(tempfile.mkdtemp())
        일별 = ["날짜,평가손익,실현손익,누적손익,총자산"]
        걸음 = [0, 12000, -9000, 15000, -4000, 26000, 50000]   # 오르내림이 있어야
        누적 = 10000
        for i, 하루 in zip(range(6, -1, -1), 걸음):
            d = 오늘 - timedelta(days=i)
            누적 += 하루
            일별.append(f"{d.isoformat()},10000,{하루},{누적},{10000000 + 누적}")
        self.쓰기("실제매매_일별손익.csv", 일별)
        self.쓰기("실제매매_보유종목.csv", [
            "종목명,종목코드,수량,평균단가,현재가,평가금액,평가손익,수익률",
            "삼성전자,005930,10,70000,71200,712000,12000,1.71",
            "카카오,035720,5,50000,49000,245000,-5000,-2.00",
            "에코프로비엠,247540,3,100000,101000,303000,3000,1.00",
        ])
        그제 = 오늘 - timedelta(days=2)
        self.쓰기("실제매매_거래내역.csv", [
            "일시,구분,종목명,종목코드,수량,단가,거래금액,결과",
            f"{날(그제, '09:45')},매수,카카오,035720,5,50000,250000,접수",
            f"{날(어제, '10:05')},매수,에코프로비엠,247540,3,100000,300000,접수",
            f"{날(어제, '14:40')},매수,카카오,035720,3,49500,148500,잔고부족",
            f"{날(오늘, '09:31')},매수,삼성전자,005930,10,70000,700000,접수",
            f"{날(오늘, '14:02')},매도,카카오,035720,5,51000,255000,접수",
        ])
        self.쓰기("자동매매_일지.csv", [
            "일시,내용",
            f"{날(그제, '09:45')},카카오(035720) 조건 충족 매수 5주",
            f"{날(그제, '15:10')},카카오(035720) 손절 매도 검토 -1.2%",
            f"{날(어제, '10:05')},에코프로비엠(247540) 조건 충족 매수 3주",
            f"{날(오늘, '09:31')},삼성전자(005930) 조건 충족 매수 10주",
            f"{날(오늘, '11:00')},장중 점검 완료",
            f"{날(오늘, '14:02')},카카오(035720) 익절 매도 5주 +2.0%",
            f"{날(오늘, '15:10')},에코프로비엠(247540) 손절 매도 검토",
        ])
        self.쓰기("가상매매_일별손익.csv", [
            "날짜,평가손익,실현손익,누적손익,총자산",
            f"{오늘.isoformat()},2000,1000,3000,1003000",
        ])

    def 쓰기(self, 이름, 줄들):
        (self.base / 이름).write_text("\n".join(줄들) + "\n", encoding="utf-8")

    def 치우기(self):
        shutil.rmtree(self.base, ignore_errors=True)


class 답변(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.기록 = 기록()
        cls.base = cls.기록.base

    @classmethod
    def tearDownClass(cls):
        cls.기록.치우기()

    def 묻기(self, q, **kw):
        return rules.answer(q, self.base, **kw)

    # ------------------------------------------------------------ 손익
    def test_오늘_손익(self):
        답 = self.묻기("오늘 손익은?")
        self.assertIn("50,000원 벌었습니다", 답)
        self.assertIn("실현손익 +50,000원", 답)
        self.assertIn("총자산", 답)

    def test_기간을_바꾸면_다른_답(self):
        self.assertIn("어제", self.묻기("어제 손익"))
        self.assertIn("이번 주", self.묻기("이번주 얼마 벌었어"))
        self.assertIn("최근 5일", self.묻기("최근 5일 수익"))

    def test_기록이_없는_날은_그렇다고_말한다(self):
        답 = self.묻기("작년 손익")
        self.assertIn("기록이 없습니다", 답)

    # ------------------------------------------------------------ 보유
    def test_보유종목(self):
        답 = self.묻기("지금 뭐 들고 있어?")
        self.assertIn("3종목", 답)
        self.assertIn("삼성전자", 답)
        self.assertIn("+1.71%", 답)

    def test_손실_난_것만(self):
        답 = self.묻기("손실 난 종목만 보여줘")
        self.assertIn("카카오", 답)
        self.assertNotIn("삼성전자", 답)

    # ------------------------------------------------------------ 체결
    def test_체결_내역(self):
        답 = self.묻기("오늘 체결 내역")
        self.assertIn("2건 체결했습니다", 답)
        self.assertIn("09:31 매수 삼성전자", 답)

    def test_종목을_짚은_체결(self):
        답 = self.묻기("카카오 언제 팔았어?")
        self.assertIn("카카오", 답)
        self.assertNotIn("삼성전자", 답)

    # ------------------------------------------------------------ 승률
    def test_승률(self):
        답 = self.묻기("오늘 승률")
        self.assertIn("1승 1패", 답)
        self.assertIn("50.0%", 답)

    # ------------------------------------------------------------ 이유
    def test_종목을_왜_샀나(self):
        답 = self.묻기("삼성전자는 왜 샀어?")
        self.assertIn("삼성전자(005930)", 답)
        self.assertIn("조건 충족 매수", 답)

    def test_코드로_물어도_된다(self):
        self.assertIn("조건 충족 매수", self.묻기("005930 왜 샀지"))

    def test_종목_없이_왜(self):
        답 = self.묻기("오늘 왜 이렇게 깨졌어")
        self.assertIn("판단 기록", 답)
        self.assertIn("익절", 답)

    def test_기록에_없는_종목(self):
        self.assertIn("찾지 못했습니다", self.묻기("000660 왜 샀어"))

    # ------------------------------------------------------------ 넓힌 것들
    def test_요약(self):
        답 = self.묻기("오늘 요약해줘")
        for 칸 in ("손익", "자산", "보유", "체결", "승률"):
            self.assertIn(칸, 답)

    def test_순위(self):
        답 = self.묻기("제일 많이 번 종목")
        self.assertIn("삼성전자", 답)
        self.assertIn("카카오", 답)

    def test_자산(self):
        답 = self.묻기("총자산 얼마야")
        self.assertIn("총자산", 답)
        self.assertIn("현금(추정)", 답)

    def test_추세(self):
        답 = self.묻기("최근 흐름 보여줘")
        self.assertIn("일별 누적손익", 답)
        self.assertIn("오른 날", 답)

    def test_종목_하나_보기(self):
        답 = self.묻기("삼성전자 어때?")
        self.assertIn("보유", 답)
        self.assertIn("10주", 답)

    def test_줄임말과_초성(self):
        self.assertIn("삼성전자", self.묻기("삼전 어때"))
        self.assertIn("삼성전자", self.묻기("ㅅㅅㅈㅈ 어때"))

    # ------------------------------------------------------------ 넓힌 답들
    def test_견주기(self):
        답 = self.묻기("지난주 대비 이번주 어때")
        self.assertIn("지난 주 vs 이번 주", 답)
        self.assertIn("실현손익", 답)

    def test_견줄_말이_없으면_직전_구간과(self):
        답 = self.묻기("어제보다 나아졌어?")
        self.assertIn("vs", 답)

    def test_평균(self):
        답 = self.묻기("하루 평균 얼마 벌어?")
        self.assertIn("하루 평균", 답)
        self.assertNotIn("최근 1일", 답)          # '하루' 를 기간으로 읽으면 안 된다

    def test_시간대별(self):
        답 = self.묻기("몇 시에 제일 잘 돼?")
        self.assertIn("시간대별", 답)
        self.assertIn("09시", 답)

    def test_요일별(self):
        self.assertIn("요일별", self.묻기("요일별 성적 보여줘"))

    def test_낙폭(self):
        답 = self.묻기("최대 낙폭 얼마야")
        self.assertIn("최대 낙폭", 답)
        self.assertIn("-9,000원", 답)

    def test_연승연패(self):
        답 = self.묻기("연패 중이야?")
        self.assertIn("연패", 답)
        self.assertIn("최장", 답)

    def test_보유기간(self):
        답 = self.묻기("평균 보유 기간")
        self.assertIn("평균 보유 기간", 답)
        self.assertIn("에코프로비엠", 답)

    def test_수수료는_없으면_어림잡고_그렇다고_말한다(self):
        답 = self.묻기("수수료 얼마 나갔어")
        self.assertIn("어림", 답)
        self.assertIn("거래세", 답)

    def test_본전(self):
        답 = self.묻기("본전까지 얼마 남았어")
        self.assertIn("본전", 답)
        self.assertIn("카카오", 답)

    def test_비중(self):
        답 = self.묻기("주식 비중 어때")
        self.assertIn("비중", 답)
        self.assertIn("%", 답)

    def test_미체결(self):
        답 = self.묻기("최근 미체결 있어?")
        self.assertIn("잔고부족", 답)

    def test_미체결이_없으면_없다고_한다(self):
        self.assertIn("막힌 주문은 없습니다", self.묻기("오늘 미체결 있어?"))

    def test_일지_검색(self):
        답 = self.묻기("일지에서 손절 찾아줘")
        self.assertIn("손절", 답)
        self.assertNotIn("조건 충족 매수", 답)

    def test_횟수(self):
        답 = self.묻기("오늘 몇 번 거래했어")
        self.assertIn("2건", 답)
        self.assertIn("매수 1건", 답)

    def test_큰_거래(self):
        답 = self.묻기("제일 큰 거래가 뭐야")
        self.assertIn("삼성전자", 답)
        self.assertIn("700,000원", 답)

    def test_활동량(self):
        답 = self.묻기("최근 얼마나 매매했어")
        self.assertIn("하루 평균", 답)
        self.assertIn("가장 바빴던 날", 답)

    def test_되풀이되는_실수(self):
        답 = self.묻기("같은 실수 반복해?")
        self.assertTrue("되풀이" in 답 or "눈에 띄게" in 답)

    def test_잡담에는_짧게(self):
        self.assertIn("안녕하세요", self.묻기("안녕"))
        self.assertIn("다행", self.묻기("고마워"))

    def test_기록_밖_물음은_빈_문자열(self):
        for q in ("내일 뭐 살까?", "코스피 어때", "손절선 바꿔줘"):
            with self.subTest(q=q):
                self.assertEqual(self.묻기(q), "")

    def test_대화에서는_왜_답할_수_없는지_말한다(self):
        대화 = rules.Conversation(self.base)
        답 = 대화.ask("내일 뭐 살까?")
        self.assertIn("앞일은 기록에 없습니다", 답)

    # ------------------------------------------------------------ 말버릇
    def test_띄어쓰기와_조사를_안_가린다(self):
        a = self.묻기("이번주손익")
        b = self.묻기("이번 주 손익은?")
        self.assertEqual(a, b)

    def test_오타(self):
        self.assertIn("3종목", self.묻기("보유종묵 알려줘"))

    def test_모의는_다른_파일을_본다(self):
        답 = self.묻기("모의 오늘 손익")
        self.assertIn("1,003,000원", 답)

    def test_두_가지를_한꺼번에(self):
        답 = self.묻기("오늘 손익이랑 보유종목 알려줘")
        self.assertIn("실현손익", 답)
        self.assertIn("보유 3종목", 답)

    def test_모르면_빈_문자열(self):
        self.assertEqual(self.묻기("김치찌개 레시피 알려줘"), "")
        self.assertEqual(self.묻기(""), "")

    def test_도움말(self):
        self.assertIn("물어볼 수 있는 것", self.묻기("뭘 물어볼 수 있어?"))

    def test_모를_때_되묻기(self):
        말 = rules.suggest("김치찌개 레시피 알려줘")
        self.assertIn("혹시 이런 걸", 말)
        self.assertIn("물어볼 수 있는 것", 말)

    # ------------------------------------------------------------ 이어 묻기
    def test_앞_질문에_이어(self):
        대화 = rules.Conversation(self.base)
        첫 = 대화.ask("오늘 손익")
        self.assertIn("오늘", 첫)
        둘 = 대화.ask("그럼 어제는?")
        self.assertIn("어제", 둘)
        self.assertIn("손익", 둘)

    def test_이어_묻다_종목도_기억(self):
        대화 = rules.Conversation(self.base)
        대화.ask("삼성전자 왜 샀어?")
        답 = 대화.ask("그럼 그건 언제 샀어?")
        self.assertIn("삼성전자", 답)
        self.assertNotIn("카카오", 답)          # 앞 종목만 이어받아야 한다

    def test_기간만_바꿔_물으면_손익으로(self):
        대화 = rules.Conversation(self.base)
        대화.ask("보유종목 알려줘")             # 기간과 상관없는 물음 뒤에
        self.assertIn("어제 손익", 대화.ask("그럼 어제는?"))

    def test_대화에서는_모를_때_되묻는다(self):
        대화 = rules.Conversation(self.base)
        self.assertIn("혹시 이런 걸", 대화.ask("김치찌개 레시피"))

    # ------------------------------------------------------------ 옛 약속
    def test_예전_함수들이_그대로_돈다(self):
        self.assertIn("실현손익", rules.answer_pnl(self.base, "오늘 손익", "실제매매"))
        self.assertIn("삼성전자", rules.answer_holdings(self.base, "실제매매"))
        self.assertIn("체결", rules.answer_trades(self.base, "오늘 체결", "실제매매"))
        self.assertIn("승률", rules.answer_winrate(self.base, "오늘 승률"))
        self.assertIn("조건 충족",
                      rules.answer_why(self.base, "왜", "실제매매", ["삼성전자", "005930"]))

    def test_옛_nlu_와_섞이지_않게_판을_본다(self):
        import nlu
        self.assertGreaterEqual(nlu.VERSION, rules.NEEDS_NLU)

    def test_기록이_있는_폴더를_알아본다(self):
        self.assertTrue(rules.has_records(self.base))
        빈곳 = Path(tempfile.mkdtemp())
        try:
            self.assertFalse(rules.has_records(빈곳))
        finally:
            shutil.rmtree(빈곳, ignore_errors=True)

    def test_기록_폴더를_스스로_찾는다(self):
        둥지 = Path(tempfile.mkdtemp())
        try:
            (둥지 / "bot").mkdir()
            shutil.copy(self.base / "실제매매_일별손익.csv", 둥지)
            self.assertEqual(rules.find_base(둥지 / "bot", 위로=1).resolve(),
                             둥지.resolve())            # 한 단계 위에서 찾는다
        finally:
            shutil.rmtree(둥지, ignore_errors=True)

    def test_못_찾으면_준_자리를_그대로(self):
        빈곳 = Path(tempfile.mkdtemp())
        try:
            self.assertEqual(rules.find_base(빈곳, 위로=0).resolve(),
                             빈곳.resolve())
        finally:
            shutil.rmtree(빈곳, ignore_errors=True)

    def test_상태_점검이_어디서_불러왔는지_보여준다(self):
        말 = rules.doctor(self.base)
        self.assertIn("불러온 것", 말)
        self.assertIn("rules", 말)
        self.assertIn("실제매매_일별손익.csv", 말)
        self.assertIn("아는 종목", 말)

    def test_기록이_없는_폴더도_점검은_된다(self):
        빈곳 = Path(tempfile.mkdtemp())
        try:
            말 = rules.doctor(빈곳)
            self.assertIn("기록 파일이 하나도 없습니다", 말)
        finally:
            shutil.rmtree(빈곳, ignore_errors=True)

    def test_때만_물어도_답한다(self):
        답 = self.묻기("오늘은?")
        self.assertIn("한눈에", 답)

    def test_date_scope_는_그대로(self):
        s, e, 이름 = rules.date_scope("어제 손익")
        self.assertEqual((s, e, 이름), (어제, 어제, "어제"))
        s, e, 이름 = rules.date_scope("전체 손익")
        self.assertEqual((s, e, 이름), (None, None, "전체 기간"))

    def test_terms_를_넘겨_주는_옛_방식(self):
        답 = self.묻기("왜 샀어?", terms=["삼성전자", "005930"])
        self.assertIn("조건 충족 매수", 답)

    def test_어긋난_기록에도_안_죽는다(self):
        엉망 = Path(tempfile.mkdtemp())
        try:
            (엉망 / "실제매매_일별손익.csv").write_text(
                "날짜,평가손익\n엉망,,,\n\n,,\n", encoding="utf-8")
            (엉망 / "실제매매_보유종목.csv").write_text(
                '종목명,수량,평가손익\n"쉼표,이름",세개,abc\n', encoding="utf-8")
            for q in ("오늘 손익", "보유종목", "요약", "총자산", "흐름", "순위"):
                with self.subTest(q=q):
                    self.assertIsInstance(rules.answer(q, 엉망), str)
        finally:
            shutil.rmtree(엉망, ignore_errors=True)

    def test_넘겨받은_종목으로_상태_보기(self):
        답 = self.묻기("어때?", terms=["삼성전자", "005930"])
        self.assertIn("10주", 답)

    def test_빈_폴더에서도_안_죽는다(self):
        빈곳 = Path(tempfile.mkdtemp())
        try:
            for q in ("오늘 손익", "보유종목", "승률", "요약", "총자산", "흐름", "체결"):
                self.assertIsInstance(rules.answer(q, 빈곳), str)
        finally:
            shutil.rmtree(빈곳, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
