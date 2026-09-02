#!/usr/bin/env python3
"""Считает лексические маркеры в русском тексте по каталогу скилла.

Скрипт делает ту часть работы, которую модель делает плохо: считает.
Он находит фразы из каталога, считает плотность на тысячу знаков,
смотрит распределение по абзацам и контрпризнаки. Он не видит
нанизывание падежей, спрятанного деятеля, ложную субъектность и ритм
смысла: это остаётся модели.

Использование:
    python check.py текст.md
    python check.py текст.md --domain legal
    python check.py текст.md --json
    cat текст.md | python check.py -

Каталог берётся из ../references/markers.md (ревьюер) или
../references/stop-words.md (писатель), смотря какой лежит рядом.
Только стандартная библиотека.
"""

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

WEIGHTS = ("Высокий", "Средний", "Низкий")

# Секции, где первая колонка таблицы это фраза, а не описание.
TABLE_PHRASE_SECTIONS = {
    "Канцелярит",
    "Пассив и безличные обороты",
    "Ложная субъектность",
    "Translationese",
    "Бизнес-жаргон",
}

# Секции с перечнем слов через запятую.
COMMA_LIST_SECTIONS = {
    "Отглагольные существительные",
    "Оценочные слова без факта",
    "Усилители и наречия",
    "Усилители",
    "Ложная субъектность",
    "Мёртвые метафоры",
}

# Вес секций для каталога без заголовков веса (stop-words.md писателя).
WRITER_SECTION_WEIGHTS = {
    "Артефакты диалога": "Высокий",
    "Типографика": "Высокий",
    "Заполнители": "Высокий",
    "Значимость без содержания": "Высокий",
    "Меризм": "Высокий",
    "Штампы": "Высокий",
    "Мета-комментарии": "Средний",
}

# Что отключает профиль домена. Ключи это названия секций каталога.
DOMAIN_DISABLE = {
    "full": set(),
    "post": set(),
    "tech": {"Ритм", "Правило трёх"},
    "science": {
        "Пассив и безличные обороты",
        "Отглагольные существительные",
        "Обтекаемые атрибуции",
        "Рассказчик со стороны",
        "Ритм",
    },
    "legal": {"Пассив и безличные обороты", "Ритм", "Правило трёх"},
}

PARTICLE_RE = re.compile(r"(?<![а-яё])(же|ведь|вот|ну|уж|разве|ж)(?![а-яё])|[а-яё]+-то(?![а-яё])", re.I)
NUMBER_RE = re.compile(r"\d+([.,]\d+)?")
EMOJI_BULLET_RE = re.compile(r"^\s*[\U0001F300-\U0001FAFF☀-➿✅✔▪-◾]")
BOLD_HEADING_ITEM_RE = re.compile(r"^\s*(?:[-*•]\s*)?\*\*[^*\n]{2,60}[:.]\*\*")
CAPS_AFTER_COLON_RE = re.compile(r":\s+[А-ЯЁ][а-яё]+")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+)$")

CONTRAST_PATTERNS = [
    (r"(?<![а-яё])не просто (?![а-яё]*так)", "не просто X, а Y"),
    (r"(?<![а-яё])не только\b", "не только X, но и Y"),
    (r"(?<![а-яё])не столько\b", "не столько X, сколько Y"),
    (r"(?<![а-яё])не потому,? что\b", "не потому что X, а потому что Y"),
    (r"(?<![а-яё])(дело|проблема|вопрос|суть) не в\b", "дело не в X, дело в Y"),
    (r"(?<![а-яё])это не [^.!?\n]{2,60}[.!?] это\b", "это не X. это Y"),
    (r"(?<![а-яё])перестаёт быть\b", "перестаёт быть X и становится Y"),
]


def norm(s):
    return s.replace("ё", "е").replace("Ё", "Е").lower()


NOUN_IYA = r"(ие|ия|ию|ием|ии|ий|иям|иями|иях)"
ADJ = r"(ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ой|ей|ому|ему|ым|им|ую|юю|ыми|ими|ых|их|ом|ем|о|е)"


def word_regex(w, single=False):
    """Регулярка на одно слово с учётом парадигмы, чтобы «данных» не ловилось как «данный».

    Для однословных фраз основа длиннее: у «знакомо» без контекста
    короткая основа ловила «знаков»."""
    n = len(w)
    if w == "данный":
        return r"данн(ый|ая|ое|ого|ой|ому|ым|ую|ыми|ом)"
    if w.endswith(("ние", "ция", "сия", "тие", "ствие")) and n >= 6:
        return re.escape(w[:-2]) + NOUN_IYA
    if w.endswith(("ый", "ий", "ой")) and n >= 6:
        return re.escape(w[:-2]) + ADJ
    if single and n >= 6:
        return re.escape(w[: n - 1]) + r"[а-яё]{0,3}"
    if n >= 7:
        return re.escape(w[: n - 2]) + r"[а-яё]{0,4}"
    if n >= 5:
        return re.escape(w[: n - 1]) + r"[а-яё]{0,3}"
    return re.escape(w)


def phrase_to_regex(phrase):
    words = re.findall(r"[а-яёa-z-]+", norm(phrase))
    if not words:
        return None
    parts = [word_regex(w, single=(len(words) == 1)) for w in words]
    body = r"[\s,]+".join(parts)
    return re.compile(r"(?<![а-яё])" + body + r"(?![а-яё])", re.I)


def clean_phrase(cell):
    cell = cell.strip()
    m = re.match(r"^«([^»]+)»", cell)
    if m:
        cell = m.group(1)
    cell = cell.strip(" .")
    if any(tok in cell for tok in ("[", "X", "Y", " N ", "...")):
        return None
    if ":" in cell and len(cell.split()) > 4:
        return None
    if len(cell.split()) > 10 or len(cell) < 3:
        return None
    return cell


def parse_catalog(path):
    """Возвращает список (фраза, секция, вес, замена)."""
    text = Path(path).read_text(encoding="utf-8-sig")
    writer_mode = "stop-words" in Path(path).name
    weight = "Средний"
    section = ""
    items = []
    seen = set()

    def add(phrase, sec, w, repl=""):
        p = clean_phrase(phrase)
        if not p:
            return
        key = norm(p)
        if key in seen:
            return
        seen.add(key)
        items.append((p, sec, w, repl.strip()))

    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^#\s+(Высокий|Средний|Низкий) вес", s)
        if m:
            weight = m.group(1)
            continue
        m = re.match(r"^##\s+(.+)$", s)
        if m:
            section = m.group(1).strip()
            if writer_mode:
                weight = WRITER_SECTION_WEIGHTS.get(section, "Средний")
            continue
        if not section:
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) < 2 or set(cells[0]) <= {"-", " "}:
                continue
            if cells[0] in ("Находка", "Не пиши", "Признак", "Что", "Значение", "Вес"):
                continue
            if section in TABLE_PHRASE_SECTIONS:
                add(cells[0], section, weight, cells[1])
            continue
        if s.startswith("- "):
            body = s[2:].strip()
            quoted = re.findall(r"«([^»]+)»", body)
            if body.startswith("«") and 1 <= len(quoted) <= 2:
                add(quoted[0], section, weight)
            continue
        if section in COMMA_LIST_SECTIONS and "," in s and not s.startswith(("«", "*", ">")):
            tokens = [t.strip(" .") for t in s.split(",")]
            if len(tokens) >= 4 and all(len(t.split()) <= 3 for t in tokens):
                for t in tokens:
                    add(t, section, weight)
    return items


def split_paragraphs(text):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return paras or [text]


def find_lexical(text, catalog, disabled):
    compiled = []
    for phrase, section, weight, repl in catalog:
        if section in disabled:
            continue
        rx = phrase_to_regex(phrase)
        if rx:
            compiled.append((rx, phrase, section, weight, repl))
    paras = split_paragraphs(text)
    hits = []
    offset = 0
    ntext = norm(text)
    for pi, para in enumerate(paras):
        start = ntext.find(norm(para), offset)
        if start < 0:
            start = offset
        offset = start + len(para)
        for rx, phrase, section, weight, repl in compiled:
            for m in rx.finditer(norm(para)):
                hits.append({
                    "quote": para[m.start(): m.end()],
                    "phrase": phrase,
                    "type": section,
                    "weight": weight,
                    "replacement": repl,
                    "paragraph": pi + 1,
                    "span": (start + m.start(), start + m.end()),
                })
    # Убираем вложенные совпадения: длинная фраза важнее короткой.
    hits.sort(key=lambda h: (h["span"][0], -(h["span"][1] - h["span"][0])))
    kept = []
    last_end = -1
    for h in hits:
        if h["span"][0] < last_end:
            continue
        kept.append(h)
        last_end = h["span"][1]
    return kept, paras


def is_title_case(line):
    """Три и больше слов, и каждое с прописной: «Как Мы Работаем». Предлоги тоже считаются."""
    words = [w for w in re.findall(r"[А-ЯЁа-яёA-Za-z-]+", line) if len(w) >= 2]
    if len(words) < 3:
        return False
    caps = [w for w in words if w[0].isupper()]
    return len(caps) == len(words)


def find_structural(text, paras, disabled):
    out = []
    lines = text.splitlines()
    title_case = []
    intro_outro = []
    for ln in lines:
        m = HEADING_RE.match(ln)
        h = m.group(1) if m else (ln.strip() if 0 < len(ln.strip()) < 70 and not ln.strip().endswith((".", ",", ":", ";", "!", "?")) and not ln.strip().startswith(("-", "|", ">", "*")) else "")
        if not h:
            continue
        if is_title_case(h):
            title_case.append(h)
        if re.match(r"^\W*(введение|заключение|итоги|выводы|резюме)\W*$", h, re.I):
            intro_outro.append(h)
    if title_case:
        out.append(("Высокий", "Типографика", "Заголовки С Больших Букв", title_case[:3], len(title_case)))
    if intro_outro:
        out.append(("Высокий", "Композиция", "Разделы «Введение»/«Заключение», проверь по домену", intro_outro, len(intro_outro)))
    emoji = [ln.strip()[:40] for ln in lines if EMOJI_BULLET_RE.match(ln)]
    if emoji:
        out.append(("Высокий", "Типографика", "Эмодзи как маркеры списка", emoji[:3], len(emoji)))
    bold_items = [ln.strip()[:50] for ln in lines if BOLD_HEADING_ITEM_RE.match(ln)]
    if len(bold_items) >= 3:
        out.append(("Высокий", "Типографика", "Пункты «**Заголовок:** пояснение» подряд", bold_items[:3], len(bold_items)))
    caps = CAPS_AFTER_COLON_RE.findall(text)
    if len(caps) >= 2:
        out.append(("Высокий", "Типографика", "Прописная после двоеточия (проверь, не имена ли это)", caps[:3], len(caps)))
    for rx, label in CONTRAST_PATTERNS:
        found = re.findall(r"[^.!?\n]{0,30}" + rx + r"[^.!?\n]{0,30}", norm(text), re.I)
        if found:
            out.append(("Средний", "Бинарные контрасты", label, [f.strip() for f in found[:3]], len(found)))
    if "Ритм" not in disabled:
        sents = [s for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) >= 3]
        lens = [len(s) for s in sents]
        runs = 0
        for i in range(len(lens) - 2):
            a, b, c = lens[i: i + 3]
            if max(a, b, c) - min(a, b, c) <= 0.15 * max(a, b, c):
                runs += 1
        if runs:
            out.append(("Низкий", "Ритм", "Три предложения подряд почти одной длины", [], runs))
        plens = [len(p) for p in paras if len(p) > 60]
        if len(plens) >= 3 and statistics.pstdev(plens) / statistics.mean(plens) < 0.2:
            out.append(("Низкий", "Ритм", "Все абзацы почти одного размера", [], len(plens)))
    return out


def counter_signals(text):
    particles = [m.group(0) for m in PARTICLE_RE.finditer(text)]
    numbers = NUMBER_RE.findall(text)
    # Имена: слово с прописной не в начале предложения и не после кавычки.
    names = re.findall(r"(?<![.!?»\n]\s)(?<![.!?»\n])\s([А-ЯЁ][а-яё]{2,})", text)
    return {
        "particles": len(particles),
        "particle_examples": sorted(set(p.lower() for p in particles))[:6],
        "numbers": len(numbers),
        "capitalized_mid_sentence": len(names),
    }


def verdict(high, density, even, signals):
    if high > 0:
        return "похоже на машину", "есть находки высокого веса"
    if density > 6:
        if even and signals["particles"] == 0:
            return "похоже на машину", "плотность выше 6, распределение ровное, частиц нет"
        return "спорно", "плотность выше 6, но распределение неровное или есть контрпризнаки"
    if density >= 3:
        return "спорно", "плотность от 3 до 6"
    return "похоже на человека", "плотность ниже 3, высокого веса нет"


def analyze(text, catalog, domain):
    disabled = DOMAIN_DISABLE.get(domain, set())
    hits, paras = find_lexical(text, catalog, disabled)
    structural = find_structural(text, paras, disabled)
    chars = len(text)
    by_weight = {w: 0 for w in WEIGHTS}
    for h in hits:
        by_weight[h["weight"]] += 1
    for w, _, _, _, n in structural:
        by_weight[w] += 1
    counted = by_weight["Высокий"] + by_weight["Средний"]
    density = counted / chars * 1000 if chars else 0
    per_para = [0] * len(paras)
    for h in hits:
        if h["weight"] != "Низкий":
            per_para[h["paragraph"] - 1] += 1
    long_paras = [i for i, p in enumerate(paras) if len(p) > 150]
    empty = [i + 1 for i in long_paras if per_para[i] == 0]
    even = bool(long_paras) and not empty
    signals = counter_signals(text)
    v, why = verdict(by_weight["Высокий"], density, even, signals)
    by_type = {}
    for h in hits:
        by_type[h["type"]] = by_type.get(h["type"], 0) + 1
    for _, t, _, _, n in structural:
        by_type[t] = by_type.get(t, 0) + n
    return {
        "chars": chars,
        "paragraphs": len(paras),
        "domain": domain,
        "by_weight": by_weight,
        "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "density": round(density, 1),
        "per_paragraph": per_para,
        "paragraphs_without_hits": empty,
        "even": even,
        "counter_signals": signals,
        "verdict": v,
        "verdict_reason": why,
        "hits": [{k: v2 for k, v2 in h.items() if k != "span"} for h in hits],
        "structural": [
            {"weight": w, "type": t, "label": l, "examples": ex, "count": n}
            for w, t, l, ex, n in structural
        ],
    }


def render(r):
    lines = []
    lines.append(f"Знаков: {r['chars']}   Абзацев: {r['paragraphs']}   Профиль: {r['domain']}")
    bw = r["by_weight"]
    lines.append(f"Находки: высокий {bw['Высокий']}, средний {bw['Средний']}, низкий {bw['Низкий']}")
    lines.append(f"Лексическая плотность: {r['density']} на 1000 знаков (высокий + средний, без синтаксических находок)")
    dist = " ".join(str(n) for n in r["per_paragraph"])
    kind = "ровное" if r["even"] else "неровное"
    extra = f", чистые абзацы: {r['paragraphs_without_hits']}" if r["paragraphs_without_hits"] else ""
    lines.append(f"Распределение по абзацам: {dist}  ({kind}{extra})")
    cs = r["counter_signals"]
    ex = ", ".join(cs["particle_examples"]) if cs["particle_examples"] else "нет"
    lines.append(f"Контрпризнаки: частицы {cs['particles']} ({ex}), числа {cs['numbers']}, слова с прописной внутри фразы {cs['capitalized_mid_sentence']}")
    lines.append(f"Предварительный вердикт по лексике: {r['verdict']} ({r['verdict_reason']})")
    if r["by_type"]:
        lines.append("По типам: " + ", ".join(f"{t} {n}" for t, n in r["by_type"].items()))
    lines.append("")
    lines.append("Структура:")
    if not r["structural"]:
        lines.append("  ничего не найдено")
    for s in r["structural"]:
        ex = ("  напр.: " + " | ".join(s["examples"])) if s["examples"] else ""
        lines.append(f"  [{s['weight'].lower()}] {s['type']}: {s['label']} ×{s['count']}{ex}")
    lines.append("")
    lines.append("Лексические находки (по весу):")
    order = {w: i for i, w in enumerate(WEIGHTS)}
    for h in sorted(r["hits"], key=lambda h: (order[h["weight"]], h["paragraph"])):
        repl = f" → {h['replacement']}" if h["replacement"] else ""
        lines.append(f"  [{h['weight'].lower()}] {h['type']} | абз. {h['paragraph']} | «{h['quote']}»{repl}")
    if not r["hits"]:
        lines.append("  ничего не найдено")
    lines.append("")
    lines.append("Скрипт не видит: нанизывание падежей, спрятанного деятеля, ложную субъектность вне списка, воду, повтор сказанного, выдуманные факты. Это досчитывает модель.")
    return "\n".join(lines)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description="Считает маркеры машинного и слабого письма в русском тексте.")
    ap.add_argument("file", help="путь к тексту или - для stdin")
    ap.add_argument("--domain", default="full", choices=sorted(DOMAIN_DISABLE), help="профиль домена")
    ap.add_argument("--catalog", help="путь к каталогу маркеров (по умолчанию ищется рядом со скриптом)")
    ap.add_argument("--json", action="store_true", help="вывести JSON вместо отчёта")
    args = ap.parse_args()

    if args.catalog:
        catalog_path = Path(args.catalog)
    else:
        here = Path(__file__).resolve().parent
        candidates = [here.parent / "references" / "markers.md", here.parent / "references" / "stop-words.md"]
        catalog_path = next((c for c in candidates if c.exists()), None)
        if catalog_path is None:
            sys.exit("Каталог не найден. Укажите --catalog.")

    if args.file == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.file).read_text(encoding="utf-8-sig")

    catalog = parse_catalog(catalog_path)
    result = analyze(text, catalog, args.domain)
    result["catalog"] = str(catalog_path)
    result["catalog_phrases"] = len(catalog)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result))


if __name__ == "__main__":
    main()
