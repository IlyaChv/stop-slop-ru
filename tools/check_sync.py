#!/usr/bin/env python3
"""Проверяет, что два скилла не разошлись.

Скрипт check.py и часть каталога продублированы намеренно: каждая папка
должна работать сама по себе. Эта проверка следит, чтобы дубли совпадали.

Ошибка (код выхода 1):
- копии scripts/check.py в двух папках отличаются;
- фраза есть в обоих каталогах, но с разным весом.

Предупреждение: фразы только в каталоге писателя. Это допустимо, но главный
по весам каталог ревьюера (markers.md), и его стоит свериться.

Использование:
    python tools/check_sync.py
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEWER = ROOT / "stop-slop-ru"
WRITER = ROOT / "write-ru"


def load_check(path):
    spec = importlib.util.spec_from_file_location("check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    errors = []
    a = REVIEWER / "scripts" / "check.py"
    b = WRITER / "scripts" / "check.py"
    if a.read_bytes() != b.read_bytes():
        errors.append(f"{a.relative_to(ROOT)} и {b.relative_to(ROOT)} отличаются")

    check = load_check(a)
    rev = {check.norm(p): (p, w) for p, _, w, _ in check.parse_catalog(REVIEWER / "references" / "markers.md")}
    wri = {check.norm(p): (p, w) for p, _, w, _ in check.parse_catalog(WRITER / "references" / "stop-words.md")}

    for key in sorted(rev.keys() & wri.keys()):
        if rev[key][1] != wri[key][1]:
            errors.append(f"вес «{rev[key][0]}»: ревьюер {rev[key][1]}, писатель {wri[key][1]}")

    only_writer = sorted(wri.keys() - rev.keys())
    high_only = [wri[k][0] for k in only_writer if wri[k][1] == "Высокий"]

    print(f"Каталог ревьюера: {len(rev)} фраз, писателя: {len(wri)}, общих: {len(rev.keys() & wri.keys())}")
    print(f"Только у писателя: {len(only_writer)}, из них высокого веса: {len(high_only)}")
    if high_only:
        print("  Предупреждение, высокий вес без пары у ревьюера: " + ", ".join(f"«{p}»" for p in high_only))
    if errors:
        print("Ошибки:")
        for e in errors:
            print("  " + e)
        sys.exit(1)
    print("Синхронно.")


if __name__ == "__main__":
    main()
