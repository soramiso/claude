"""python -m nlu "질문" — 문장을 어떻게 알아들었는지 보여 준다.

사전을 고치다 뜻이 엉뚱하게 잡히면 이것부터 찍어 본다.
종목 이름을 함께 보려면 기록 폴더를 --base 로 일러 주면 된다.
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import entities as E
from .explain import trace


def _catalog(base: Path) -> tuple:
    """기록 폴더가 있으면 종목 이름을 읽어 온다. 없으면 빈 목록."""
    import csv
    import io
    쌍 = []
    for mode in ("실제매매", "가상매매"):
        for 이름 in (f"{mode}_보유종목.csv", f"{mode}_거래내역.csv"):
            길 = base / 이름
            try:
                글 = 길.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            for row in csv.DictReader(io.StringIO(글)):
                쌍.append(((row.get("종목명") or "").strip(),
                          (row.get("종목코드") or "").strip()))
    return E.catalog_from(쌍)


def main() -> None:
    args = list(sys.argv[1:])
    base = Path(".")
    if "--base" in args:
        i = args.index("--base")
        base = Path(args[i + 1])
        del args[i:i + 2]
    질문 = " ".join(args)
    if not 질문:
        print(__doc__.strip())
        return
    print(trace(질문, _catalog(base)))


if __name__ == "__main__":
    main()
