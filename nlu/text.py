"""글자를 다루는 바닥. 위 모듈들이 모두 여기에 기댄다.

한국어는 같은 뜻을 쓰는 방법이 너무 많다. "팔았어", "파셨나요", "매도했지",
"털었니" 가 다 같은 말이다. 문장을 진짜로 분석하지는 못해도, 어미를 걷어내
어간만 남기면 사전 하나로 이 모두를 받을 수 있다. 여기서 하는 일이 그것이다.

  다듬기    유니코드·공백·문장부호를 고른 꼴로
  자모      풀고(분해) 다시 붙이고(조립), 초성만 뽑고
  조사      받침을 보고 은/는, 이/가, 으로/로 를 고른다
  어미      "했어요" 에서 "하" 를 꺼낸다. 어간 후보를 집합으로 준다
  오타      자모로 견주고, 영타로 잘못 친 것도 되돌린다
  말투      물음인지, 존대인지, 부정인지
"""

from __future__ import annotations

import difflib
import re
import unicodedata

# ---------------------------------------------------------------- 자모 표
CHOSUNG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNGSUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONGSUNG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"

HANGUL_START, HANGUL_END = 0xAC00, 0xD7A3


def is_hangul(ch: str) -> bool:
    return HANGUL_START <= ord(ch) <= HANGUL_END


def decompose(ch: str) -> tuple:
    """글자 하나를 (초성, 중성, 종성) 으로. 한글이 아니면 (글자, '', '')."""
    if not ch or not is_hangul(ch):
        return (ch, "", "")
    i = ord(ch) - HANGUL_START
    jong = JONGSUNG[i % 28]
    return (CHOSUNG[i // 588], JUNGSUNG[(i % 588) // 28], "" if jong == " " else jong)


def compose(cho: str, jung: str, jong: str = "") -> str:
    """(초성, 중성, 종성) 을 글자 하나로. 못 만들면 이어 붙인 그대로."""
    try:
        ci, ji = CHOSUNG.index(cho), JUNGSUNG.index(jung)
    except ValueError:
        return cho + jung + jong
    ki = JONGSUNG.index(jong) if jong and jong in JONGSUNG else 0
    return chr(HANGUL_START + (ci * 21 + ji) * 28 + ki)


def jamo(text: str) -> str:
    """글자를 자모로 푼다. 오타를 견줄 때 쓴다."""
    out = []
    for ch in text:
        if is_hangul(ch):
            cho, jung, jong = decompose(ch)
            out.append(cho + jung + jong)
        else:
            out.append(ch)
    return "".join(out)


def chosung(text: str) -> str:
    """초성만. 'ㅅㅅㅈㅈ' 같은 질문을 받기 위한 것."""
    out = []
    for ch in text:
        if is_hangul(ch):
            out.append(decompose(ch)[0])
        elif "ㄱ" <= ch <= "ㅎ":
            out.append(ch)
    return "".join(out)


def is_chosung_only(text: str) -> bool:
    t = re.sub(r"\s+", "", text)
    return bool(t) and all("ㄱ" <= ch <= "ㅎ" for ch in t)


# ---------------------------------------------------------------- 다듬기
_WS = re.compile(r"\s+")
_WORD = re.compile(r"[가-힣ㄱ-ㅎa-z0-9.]+")
_JAMO_BACK = {chr(0x1100 + i): CHOSUNG[i] for i in range(19)}
_JAMO_BACK.update({chr(0x1161 + i): JUNGSUNG[i] for i in range(21)})

# 자주 섞여 들어오는 군더더기. 뜻에 보탬이 없으니 비교 전에 덜어 낸다.
_FILLER = ("좀 ", "그냥 ", "혹시 ", "일단 ", "한번 ", "한 번 ", "대충 ", "빨리 ")


def normalize(text: str) -> str:
    """유니코드 꼴을 맞추고 공백을 한 칸으로 줄인다.

    NFKC 는 홀로 쓴 'ㅅ' 을 조합용 자모로 바꿔 버린다. 초성 질문("ㅅㅅㅈㅈ")
    을 받으려면 그것만 제자리로 돌려놓아야 한다.
    """
    t = unicodedata.normalize("NFKC", text or "")
    if any(ch in _JAMO_BACK for ch in t):
        t = "".join(_JAMO_BACK.get(ch, ch) for ch in t)
    return _WS.sub(" ", t).strip()


def squash(text: str) -> str:
    """띄어쓰기를 지운 꼴. '이번 주' 와 '이번주' 를 같은 말로 본다."""
    return _WS.sub("", normalize(text)).lower()


def depunct(text: str) -> str:
    """문장부호를 공백으로. 날짜에 쓰는 기호(-./:~)는 남긴다."""
    return _WS.sub(" ", re.sub(r"[?!,;'\"()\[\]{}<>·…]+", " ", normalize(text))).strip()


def deflate(text: str) -> str:
    """군더더기와 늘어진 자모를 걷어낸다. 'ㅋㅋㅋ', '좀' 같은 것."""
    t = normalize(text)
    for f in _FILLER:
        t = t.replace(f, " ")
    t = re.sub(r"([ㄱ-ㅎㅏ-ㅣ])\1{1,}", "", t)       # ㅋㅋㅋ, ㅠㅠ
    t = re.sub(r"(.)\1{3,}", r"\1\1", t)              # 아아아아 → 아아
    return _WS.sub(" ", t).strip()


# ---------------------------------------------------------------- 조사
_JOSA = ("으로부터", "에서부터", "로부터", "에게서", "한테서", "이라는", "이라고",
         "이라도", "이라서", "까지는", "부터는", "에서는", "에게는", "보다는",
         "보다도", "이라면", "라면", "라는", "라고", "라도", "라서", "처럼",
         "만큼", "밖에", "조차", "마저", "에서", "에게", "한테", "께서",
         "이랑", "하고", "으로", "에는", "까지", "부터", "보다", "이나",
         "은", "는", "이", "가", "을", "를", "의", "도", "만", "과", "와",
         "랑", "로", "에", "야", "아", "나", "께")
JOSA = tuple(sorted(set(_JOSA), key=len, reverse=True))

_PAIRS = {"은는": ("은", "는"), "이가": ("이", "가"), "을를": ("을", "를"),
          "와과": ("과", "와"), "과와": ("과", "와"), "로으로": ("으로", "로"),
          "으로로": ("으로", "로"), "이나": ("이나", "나"), "이란": ("이란", "란"),
          "아야": ("아", "야"), "이에요예요": ("이에요", "예요")}


def strip_josa(token: str) -> str:
    """토큰 끝의 조사를 뗀다. 남는 말이 두 글자는 되어야 뗀다."""
    if not re.fullmatch(r"[가-힣]+", token):
        return token
    for j in JOSA:
        if token.endswith(j) and len(token) - len(j) >= 2:
            return token[: -len(j)]
    return token


def has_batchim(word: str) -> bool:
    """마지막 글자에 받침이 있나. 숫자와 영문은 읽는 소리로 친다."""
    w = re.sub(r"[^가-힣a-zA-Z0-9]+$", "", normalize(word))
    if not w:
        return False
    ch = w[-1]
    if is_hangul(ch):
        return bool(decompose(ch)[2])
    if ch.isdigit():
        return ch in "013678"          # 영·일·삼·육·칠·팔 은 받침으로 끝난다
    return ch.lower() in "lmnr"        # 엘·엠·엔·알


def josa(word: str, pair: str = "은는") -> str:
    """받침에 맞는 조사를 붙인다. 문장이 사람 말처럼 보이는 가장 싼 방법."""
    key = pair.replace("/", "").replace(" ", "")
    withb, without = _PAIRS.get(key, (key[: len(key) // 2], key[len(key) // 2:]))
    w = normalize(word)
    if not w:
        return w
    if key in ("로으로", "으로로"):
        last = w[-1]
        if is_hangul(last) and decompose(last)[2] == "ㄹ":
            return w + "로"
    return w + (withb if has_batchim(w) else without)


# ---------------------------------------------------------------- 어미
# 뒤에서부터 떼어 낼 어미들. 긴 것을 먼저 본다.
_ENDINGS = (
    "습니까", "습니다", "ㅂ니까", "ㅂ니다", "었었어", "았었어", "했었어",
    "시겠어요", "으시나요", "셨나요", "시나요", "으셨어", "으세요", "으십니까",
    "나요", "까요", "가요", "되나", "는지", "은지", "을지", "ㄹ지", "던가",
    "더라", "드라", "구나", "군요", "네요", "네", "지요", "죠", "어요", "아요",
    "여요", "예요", "이에요", "에요", "잖아", "거든", "는데", "은데", "ㄴ데",
    "면서", "으면", "려고", "러고", "라고", "다고", "다는", "다가",
    "았어", "었어", "였어", "았니", "었니", "았나", "었나", "았지", "었지",
    "았고", "었고", "았는데", "었는데", "았다", "었다", "였다",
    "겠어", "겠지", "겠네", "을까", "ㄹ까", "니까", "으니", "아서", "어서",
    "고요", "해요", "한다", "した",
    "어", "아", "야", "여", "요", "지", "죠", "니", "나", "냐", "노", "남",
    "까", "게", "고", "며", "면", "다", "대", "래", "임", "음", "슴", "기",
    "은", "는", "을", "ㄹ", "ㄴ", "던", "한", "할", "함",
)
ENDINGS = tuple(sorted(set(_ENDINGS), key=len, reverse=True))

# 줄어든 꼴을 원래대로. "했"→"하", "봤"→"보" 처럼 소리가 합쳐진 것들.
_CONTRACTED = {"해": "하", "봐": "보", "와": "오", "줘": "주", "써": "쓰",
               "켜": "키", "펴": "피", "여": "이", "돼": "되", "래": "르",
               "쳐": "치", "져": "지", "뎌": "디", "셔": "시", "혀": "히"}

# 잘 쓰는 불규칙. 사전을 어간으로 맞추기보다 여기 적는 편이 읽기 쉽다.
_IRREGULAR = {
    "팔": "팔", "파": "팔", "판": "팔", "팔았": "팔", "팜": "팔",
    "삼": "사", "산": "사", "샀": "사", "살": "사",
    "들": "들", "듦": "들", "물렸": "물리", "물려": "물리", "물림": "물리",
    "깨졌": "깨지", "깨져": "깨지", "먹었": "먹", "벌었": "벌", "잃었": "잃",
    "됐": "되", "웠": "우", "났": "나", "냈": "내", "섰": "서", "탔": "타",
    "왔": "오", "갔": "가", "봤": "보", "췄": "추", "췄": "추",
}


def _drop_past(word: str) -> str:
    """끝 글자의 ㅆ 받침(과거)을 떼고, 줄어든 소리를 되돌린다."""
    if not word or not is_hangul(word[-1]):
        return word
    cho, jung, jong = decompose(word[-1])
    if jong not in ("ㅆ", "ㅄ"):
        return word
    bare = compose(cho, jung)
    return word[:-1] + _CONTRACTED.get(bare, bare)


def _drop_ending(word: str) -> str:
    """끝에 붙은 어미 하나를 뗀다. 남는 말이 한 글자는 되어야 한다."""
    for e in ENDINGS:
        if word.endswith(e) and len(word) - len(e) >= 1:
            return word[: -len(e)]
    # 받침으로만 붙은 어미: '판' → '파', '했음' 의 'ㅁ' 같은 것
    if is_hangul(word[-1]):
        cho, jung, jong = decompose(word[-1])
        if jong in ("ㄴ", "ㄹ", "ㅁ") and len(word) >= 2:
            return word[:-1] + compose(cho, jung)
    return word


def unconjugate(token: str) -> str:
    """활용을 벗겨 어간 하나를 고른다. 완벽할 필요는 없고 한결같으면 된다."""
    w = strip_josa(token)
    if not re.fullmatch(r"[가-힣]+", w):
        return w
    for _ in range(5):
        before = w
        w = _drop_ending(_drop_past(w))
        if w in _IRREGULAR:              # 적어 둔 불규칙에 닿으면 거기서 멈춘다
            return _IRREGULAR[w]
        if w == before or not w:
            break
    return w or before


def stems(token: str) -> frozenset:
    """어간 후보들. 하나로 못 줄이면 여러 개를 주고 교집합으로 맞춘다.

    사전 쪽 낱말도 같은 함수로 펼쳐 두면, 서로 다른 활용형이 만나게 된다.
    """
    token = normalize(token).lower()
    out = {token}
    bare = strip_josa(token)
    out.add(bare)
    if re.fullmatch(r"[가-힣]+", bare):
        w = bare
        for _ in range(5):
            w2 = _drop_ending(_drop_past(w))
            hit = _IRREGULAR.get(w2)
            out.add(hit or w2)
            if hit or w2 == w or not w2:
                break
            w = w2
        out.add(unconjugate(bare))
    # "매도하", "생각하" 는 "매도", "생각" 으로도 두어야 사전과 만난다.
    for w in list(out):
        if len(w) >= 2 and w.endswith(("하", "되", "시")):
            out.add(w[:-1])
    return frozenset(s for s in out if s)


def tokens(text: str) -> list:
    """비교용 토큰. 조사를 떼고 소문자로."""
    return [strip_josa(t) for t in _WORD.findall(deflate(text).lower())]


def stem_set(text: str) -> frozenset:
    """문장 전체의 어간 후보 모음."""
    out = set()
    for t in tokens(text):
        out |= stems(t)
    return frozenset(out)


# ---------------------------------------------------------------- 오타
def similar(a: str, b: str) -> float:
    """두 말이 얼마나 닮았는지. 글자와 자모 둘 다로 보고 높은 쪽을 쓴다."""
    if a == b:
        return 1.0
    return max(difflib.SequenceMatcher(None, a, b).ratio(),
               difflib.SequenceMatcher(None, jamo(a), jamo(b)).ratio())


# 두벌식 자판. 한글로 칠 것을 영문으로 친 경우를 되돌린다.
_KEY_CHO = {"r": "ㄱ", "R": "ㄲ", "s": "ㄴ", "e": "ㄷ", "E": "ㄸ", "f": "ㄹ",
            "a": "ㅁ", "q": "ㅂ", "Q": "ㅃ", "t": "ㅅ", "T": "ㅆ", "d": "ㅇ",
            "w": "ㅈ", "W": "ㅉ", "c": "ㅊ", "z": "ㅋ", "x": "ㅌ", "v": "ㅍ",
            "g": "ㅎ"}
_KEY_JUNG = {"k": "ㅏ", "o": "ㅐ", "i": "ㅑ", "O": "ㅒ", "j": "ㅓ", "p": "ㅔ",
             "u": "ㅕ", "P": "ㅖ", "h": "ㅗ", "y": "ㅛ", "n": "ㅜ", "b": "ㅠ",
             "m": "ㅡ", "l": "ㅣ"}
_COMBO_JUNG = {("ㅗ", "ㅏ"): "ㅘ", ("ㅗ", "ㅐ"): "ㅙ", ("ㅗ", "ㅣ"): "ㅚ",
               ("ㅜ", "ㅓ"): "ㅝ", ("ㅜ", "ㅔ"): "ㅞ", ("ㅜ", "ㅣ"): "ㅟ",
               ("ㅡ", "ㅣ"): "ㅢ"}
_COMBO_JONG = {("ㄱ", "ㅅ"): "ㄳ", ("ㄴ", "ㅈ"): "ㄵ", ("ㄴ", "ㅎ"): "ㄶ",
               ("ㄹ", "ㄱ"): "ㄺ", ("ㄹ", "ㅁ"): "ㄻ", ("ㄹ", "ㅂ"): "ㄼ",
               ("ㄹ", "ㅅ"): "ㄽ", ("ㄹ", "ㅌ"): "ㄾ", ("ㄹ", "ㅍ"): "ㄿ",
               ("ㄹ", "ㅎ"): "ㅀ", ("ㅂ", "ㅅ"): "ㅄ"}


def from_qwerty(text: str) -> str:
    """영문 자판으로 잘못 친 한글을 되돌린다. 'tkatjd' → '삼성'."""
    buf, out = [], []

    def flush():
        """모아 둔 자모를 글자로 묶는다."""
        i = 0
        while i < len(buf):
            cho = buf[i] if buf[i] in CHOSUNG else ""
            if not cho:
                out.append(buf[i]); i += 1; continue
            if i + 1 >= len(buf) or buf[i + 1] not in JUNGSUNG:
                out.append(cho); i += 1; continue
            jung, used = buf[i + 1], 2
            if i + 2 < len(buf) and (jung, buf[i + 2]) in _COMBO_JUNG:
                jung, used = _COMBO_JUNG[(jung, buf[i + 2])], 3
            jong = ""
            j = i + used
            if j < len(buf) and buf[j] in JONGSUNG and buf[j] != " ":
                nxt = buf[j + 1] if j + 1 < len(buf) else ""
                if not (nxt and nxt in JUNGSUNG):      # 다음 글자의 초성이면 넘긴다
                    jong, used = buf[j], used + 1
                    if (j + 1 < len(buf) and (jong, buf[j + 1]) in _COMBO_JONG
                            and not (j + 2 < len(buf) and buf[j + 2] in JUNGSUNG)):
                        jong, used = _COMBO_JONG[(jong, buf[j + 1])], used + 1
            out.append(compose(cho, jung, jong))
            i += used
        buf.clear()

    for ch in text:
        if ch in _KEY_CHO or ch in _KEY_JUNG:
            buf.append(_KEY_CHO.get(ch) or _KEY_JUNG[ch])
        else:
            flush()
            out.append(ch)
    flush()
    return "".join(out)


def looks_like_qwerty(text: str) -> bool:
    """영타로 친 한글처럼 보이나.

    자판에 있는 글자인지만 보면 'hello' 도 걸린다. 되돌려 본 뒤 온전한
    한글 음절로 맞아떨어지는지까지 봐야 영어 낱말과 갈린다.
    """
    t = re.sub(r"\s+", "", text)
    if len(t) < 4 or not re.fullmatch(r"[a-zA-Z]+", t):
        return False
    if any(ch not in _KEY_CHO and ch not in _KEY_JUNG for ch in t):
        return False
    back = from_qwerty(t)
    온전 = sum(1 for ch in back if is_hangul(ch))
    return 온전 >= 2 and 온전 / len(back) >= 0.8


def correct(token: str, vocab, cutoff: float = 0.78) -> str:
    """사전에 비슷한 말이 있으면 그것으로 고친다. 없으면 그대로."""
    if not token or token in vocab:
        return token
    best, score = token, cutoff
    for w in vocab:
        r = similar(token, w)
        if r > score:
            best, score = w, r
    return best


# ---------------------------------------------------------------- 말투
_QUESTION = ("뭐", "무엇", "무슨", "어디", "언제", "누구", "얼마", "몇", "왜",
             "어떻게", "어때", "어떤", "어느", "까", "나요", "니", "냐", "지",
             "는지", "은지", "을까", "ㄹ까", "알려", "보여", "말해", "궁금")
_POLITE = ("요", "습니다", "십니까", "세요", "시죠", "주세요", "주십시오", "해줘요")
_CASUAL = ("냐", "임", "삼", "ㅇㅇ", "ㄱㄱ", "해줘", "해봐", "알려줘")
_NEGATION = ("안 ", "안돼", "안되", "못 ", "못해", "않", "말고", "빼고", "아닌",
             "아니", "없", "말이야")


def is_question(text: str) -> bool:
    t = squash(text)
    return "?" in text or any(k in t for k in _QUESTION)


def politeness(text: str) -> str:
    """'존대' | '반말' | '중립'. 답의 말끝을 맞추는 데 쓸 수 있다."""
    t = squash(text)
    if any(t.endswith(k) or k in t for k in _POLITE):
        return "존대"
    if any(k in t for k in _CASUAL):
        return "반말"
    return "중립"


def has_negation(text: str) -> bool:
    """'안 팔았어?' 처럼 부정이 섞였나."""
    t = normalize(text)
    return any(k in t for k in _NEGATION)


def is_smalltalk(text: str) -> str:
    """인사·고맙다 같은 잡담. 뜻이 없으니 따로 받아 준다."""
    t = squash(text)
    if not t:
        return ""
    if any(k in t for k in ("안녕", "하이", "hi", "hello", "반가", "굿모닝", "좋은아침")):
        return "인사"
    if any(k in t for k in ("고마", "감사", "땡큐", "thanks", "수고")):
        return "감사"
    if any(k in t for k in ("잘자", "바이", "끝", "종료", "그만", "bye")):
        return "작별"
    if re.fullmatch(r"[ㅋㅎㅠㅜ.,!?~ ]+", t):
        return "웃음"
    return ""
