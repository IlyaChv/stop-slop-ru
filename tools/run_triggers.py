#!/usr/bin/env python3
"""Проверяет, какой скилл вызывает настоящий Claude Code на каждый запрос.

На каждый запрос из evals/trigger_queries.json запускается
`claude -p ... --max-turns 1` в пустой папке, и из потока событий берётся
первый вызов инструмента Skill. Скиллы берутся из установленных
(~/.claude/skills), поэтому перед прогоном синхронизируйте копии.

Один запрос стоит около $0,2 по ценам API (2026-09-30, Sonnet).

Использование:
    python tools/run_triggers.py --model sonnet --jobs 4
    python tools/run_triggers.py --only r01,w13
"""

import argparse
import datetime
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERIES = ROOT / "evals" / "trigger_queries.json"
RESULTS = ROOT / "evals" / "trigger_results.json"


def run_one(q, model):
    with tempfile.TemporaryDirectory() as tmp:
        try:
            proc = subprocess.run(
                ["claude", "-p", q["query"], "--model", model, "--max-turns", "1",
                 "--output-format", "stream-json", "--verbose"],
                cwd=tmp, capture_output=True, text=True, encoding="utf-8", timeout=240, shell=sys.platform == "win32",
            )
            out = proc.stdout
        except subprocess.TimeoutExpired:
            return {**q, "got": "timeout", "cost": None}
    got, cost = "none", None
    for line in out.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "assistant" and got == "none":
            for c in e["message"].get("content", []):
                if c.get("type") == "tool_use" and c.get("name") == "Skill":
                    got = c["input"].get("skill", "?")
                    break
        if e.get("type") == "result":
            cost = e.get("total_cost_usd")
    return {**q, "got": got, "cost": cost}


def verdict(r):
    # «other:a|b» значит: верен любой из соседних скиллов.
    got = r["got"].split(":")[-1]
    return any(got == w for w in r["expect"].removeprefix("other:").split("|"))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", help="id через запятую")
    args = ap.parse_args()
    qs = json.loads(QUERIES.read_text(encoding="utf-8"))
    if args.only:
        keep = set(args.only.split(","))
        qs = [q for q in qs if q["id"] in keep]
    with ThreadPoolExecutor(args.jobs) as ex:
        res = list(ex.map(lambda q: run_one(q, args.model), qs))
    for r in res:
        r["ok"] = verdict(r)
    ok = sum(r["ok"] for r in res)
    cost = sum(r["cost"] or 0 for r in res)
    for r in res:
        mark = "ok " if r["ok"] else "ОШИБКА"
        print(f"{mark} {r['id']} ждали {r['expect']}, вызван {r['got']}")
    print(f"\nВерно {ok} из {len(res)}. Стоимость по API ${cost:.2f}")
    RESULTS.write_text(json.dumps({
        "date": datetime.date.today().isoformat(),
        "model": args.model,
        "method": "claude -p --max-turns 1 в пустой папке, первый вызов Skill; скиллы из ~/.claude/skills",
        "correct": ok, "total": len(res), "cost_usd": round(cost, 2),
        "results": [{k: r[k] for k in ("id", "expect", "got", "ok")} for r in res],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
