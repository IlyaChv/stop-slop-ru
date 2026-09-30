#!/usr/bin/env python3
"""Прогоняет check.py ревьюера по корпусу реальных текстов.

Тексты лежат в corpus/texts/{human,machine}/ и в git не идут. Каждый файл
начинается с комментария <!-- source: ... | domain: ... | label: ... -->,
из него берутся профиль домена и метка.

Использование:
    python tools/run_corpus.py              текущая версия
    python tools/run_corpus.py --old 799de77   сравнить с версией из коммита
"""

import argparse
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXTS = ROOT / "corpus" / "texts"
SHORT = {"похоже на машину": "машина", "спорно": "спорно", "похоже на человека": "человек"}


def load(script, catalog, name):
    spec = importlib.util.spec_from_file_location(name, script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, mod.parse_catalog(catalog)


def load_ref(ref, tmp):
    out = {}
    for rel in ("stop-slop-ru/scripts/check.py", "stop-slop-ru/references/markers.md"):
        blob = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=ROOT, capture_output=True, check=True).stdout
        p = Path(tmp) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
        out[rel] = p
    return load(out["stop-slop-ru/scripts/check.py"], out["stop-slop-ru/references/markers.md"], "old")


def read_corpus():
    for f in sorted(TEXTS.glob("*/*.md")):
        raw = f.read_text(encoding="utf-8-sig")
        hdr = re.match(r"<!--(.*?)-->", raw, re.S)
        if not hdr:
            continue
        domain = re.search(r"domain:\s*(\w+)", hdr.group(1)).group(1)
        label = re.search(r"label:\s*(\w+)", hdr.group(1)).group(1)
        yield f.stem, label, domain, raw[hdr.end():].lstrip("\n")


def score(version, text, domain):
    mod, cat = version
    r = mod.analyze(text, cat, domain)
    highs = [h["quote"] for h in r["hits"] if h["weight"] == "Высокий"]
    highs += [s["label"] for s in r["structural"] if s["weight"] == "Высокий"]
    return SHORT[r["verdict"]], r["density"], "; ".join(highs)[:50]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", help="коммит, с которым сравнить")
    args = ap.parse_args()
    if not TEXTS.exists():
        sys.exit("Нет corpus/texts/. Соберите тексты по списку в corpus/README.md.")

    versions = {"сейчас": load(ROOT / "stop-slop-ru/scripts/check.py", ROOT / "stop-slop-ru/references/markers.md", "new")}
    with tempfile.TemporaryDirectory() as tmp:
        if args.old:
            versions = {args.old: load_ref(args.old, tmp), **versions}
        rows = [(name, label, domain, {k: score(v, text, domain) for k, v in versions.items()})
                for name, label, domain, text in read_corpus()]

    head = "| Файл | Метка | Профиль | " + " | ".join(f"{k}: вердикт | плотность | высокий вес" for k in versions) + " |"
    print(head)
    print("|" + "---|" * (3 + 3 * len(versions)))
    for name, label, domain, res in rows:
        cells = " | ".join(f"{v} | {d} | {h}" for v, d, h in res.values())
        print(f"| {name} | {label} | {domain} | {cells} |")
    print()
    for k in versions:
        for label in ("human", "machine"):
            vs = [res[k][0] for _, lab, _, res in rows if lab == label]
            counts = ", ".join(f"{v} {vs.count(v)}" for v in ("человек", "спорно", "машина"))
            print(f"{k}, {label} ({len(vs)}): {counts}")


if __name__ == "__main__":
    main()
