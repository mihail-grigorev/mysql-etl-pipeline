from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Set, Tuple, Dict, Optional, Any

from fio_lib import (
    DASHES, HOMOGLYPHS, HONORIFICS_PREFIXES, HONORIFICS_POSTFIXES,
    FOREIGN_PREFIXES_MULTI, FOREIGN_PREFIXES_SINGLE,
    ETYMOLOGY_CLUSTERS, NAME_TO_ETYMOLOGY,
    MALE_FIRST, FEMALE_FIRST, NICKNAMES, SURNAMES,
    get_name_etymology_root, are_names_etymologically_identical,
    to_female, to_male_lemma, canonical_from_parts, match_key
)

AUTO_THRESHOLD = 0.92       # Автоматическое слияние
REVIEW_THRESHOLD = 0.80     # Отправка дата-стюарду на ручную проверку
MIN_GAP = 0.05              # Минимальный отрыв от второго кандидата

_FOLD_MAP = {
    ord("ё"): "е", ord("э"): "е", ord("й"): "и", ord("ы"): "и",
    ord("ь"): None, ord("ъ"): None, ord("'"): None, ord("`"): None, ord("’"): None
}

# Приводит строку к нижнему регистру и меняет 'ё' на 'е'
def norm_str(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    return s.replace("ё", "е")

# Убирает спецсимволы, схлопывает похожие гласные и оставляет только буквы
def fold(s: str) -> str:
    if not s:
        return ""
    s_clean = s.lower().translate(_FOLD_MAP)
    return re.sub(r"[^а-яa-z]", "", s_clean)

# Делает первую букву заглавной, учитывая дефисы в составных словах
def cap(word: str) -> str:
    if not word:
        return ""
    if "-" in word:
        return "-".join(cap(p) for p in word.split("-"))
    return word[:1].upper() + word[1:].lower()

# 1. Алгоритмы расстояния строк и сходства
# Считает расстояние Дамерау — Левенштейна (с перестановками соседних букв)
def osa(a: str, b: str) -> int:
    la, lb = len(a), len(b)
    if not la: return lb
    if not lb: return la
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]

# Нормализует расстояние Дамерау — Левенштейна в коэффициент схожести от 0.0 до 1.0
def sim_osa(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    dist = osa(a, b)
    max_len = max(len(a), len(b))
    return max(0.0, 1.0 - dist / max_len)

# Считает сходство строк по алгоритму Джаро — Винклера (с бонусом за общий префикс)
def jaro_winkler(s1: str, s2: str, p: float = 0.1) -> float:
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if not len1 or not len2:
        return 0.0
    max_dist = max(len1, len2) // 2 - 1
    match1 = [False] * len1
    match2 = [False] * len2
    matches = 0
    for i in range(len1):
        start = max(0, i - max_dist)
        end = min(i + max_dist + 1, len2)
        for j in range(start, end):
            if match2[j] or s1[i] != s2[j]:
                continue
            match1[i] = match2[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0
    t = 0
    point = 0
    for i in range(len1):
        if not match1[i]:
            continue
        while not match2[point]:
            point += 1
        if s1[i] != s2[point]:
            t += 1
        point += 1
    t /= 2.0
    m = matches
    jaro = (m / len1 + m / len2 + (m - t) / m) / 3.0
    prefix_len = 0
    for i in range(min(4, min(len1, len2))):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break
    return jaro + prefix_len * p * (1.0 - jaro)

# 2. Фонетическое кодирование
# Строит упрощенный фонетический код слова (русский Metaphone) для сравнения по звучанию
def cyrillic_metaphone(s: str) -> str:
    s = norm_str(s)
    s = re.sub(r"[^а-я]", "", s)
    if not s:
        return ""
    if s.endswith("б"): s = s[:-1] + "п"
    elif s.endswith("в"): s = s[:-1] + "ф"
    elif s.endswith("г"): s = s[:-1] + "к"
    elif s.endswith("д"): s = s[:-1] + "т"
    elif s.endswith("ж"): s = s[:-1] + "ш"
    elif s.endswith("з"): s = s[:-1] + "с"

    s = s.replace("стн", "сн").replace("здн", "зн").replace("вств", "ств").replace("лнц", "нц")
    s = re.sub(r"[о]", "а", s)
    s = re.sub(r"[еэяию]", "и", s)
    out = [s[0]]
    for ch in s[1:]:
        if ch != out[-1]:
            out.append(ch)
    return "".join(out)

# 3. Раскладка клавиатуры и исправление OCR
_EN_KB = "qwertyuiop[]asdfghjkl;'zxcvbnm,./`"
_RU_KB = "йцукенгшщзхъфывапролджэячсмитьбю.ё"
_EN2RU = str.maketrans(_EN_KB, _RU_KB)
_RU2EN = str.maketrans(_RU_KB, _EN_KB)

# Переводит строку из английской раскладки в русскую, если она похожа на русскую фамилию
def fix_keyboard_layout(s: str) -> str:
    if re.search(r"^[a-zA-Z\s\-\.,';]+$", s):
        converted = s.lower().translate(_EN2RU)
        if any(converted.endswith(sfx) for sfx in ("ов", "ова", "ев", "ева", "ин", "ина", "ский", "ская")):
            return converted
    return s

# Исправляет типовые артефакты распознавания текста (0 на о, 1 на л, rn на m и т.д.)
def fix_ocr_errors(s: str) -> str:
    s = s.replace("rn", "m").replace("vv", "w").replace("cl", "d")
    s = re.sub(r"(?<=[a-zA-Zа-яА-Я])0(?=[a-zA-Zа-яА-Я])", "о", s)
    s = re.sub(r"(?<=[a-zA-Zа-яА-Я])1(?=[a-zA-Zа-яА-Я])", "л", s)
    return s

# 4. Транслитерация
_REV_TRANSLIT = [
    ("shch", "щ"), ("sch", "ш"), ("sh", "ш"), ("ch", "ч"), ("tch", "ч"),
    ("zh", "ж"), ("kh", "х"), ("ts", "ц"), ("tz", "ц"), ("cz", "ц"),
    ("yu", "ю"), ("ju", "ю"), ("ya", "я"), ("ja", "я"), ("yo", "ё"), ("jo", "ё"),
    ("ph", "ф"), ("th", "т"),
    ("a", "а"), ("b", "б"), ("v", "в"), ("g", "г"), ("d", "д"), ("e", "е"),
    ("z", "з"), ("i", "и"), ("y", "й"), ("k", "к"), ("l", "л"), ("m", "м"),
    ("n", "н"), ("o", "о"), ("p", "п"), ("r", "р"), ("s", "с"), ("t", "т"),
    ("u", "у"), ("f", "ф"), ("h", "х"), ("c", "ц"), ("j", "й"), ("q", "к"),
    ("w", "в"), ("x", "кс")
]

# Переводит латинскую транслитерацию обратно в кириллицу
def latin_to_cyr(s: str) -> str:
    s_low = s.lower()
    out, i = [], 0
    while i < len(s_low):
        for lat, cyr in _REV_TRANSLIT:
            if s_low.startswith(lat, i):
                out.append(cyr)
                i += len(lat)
                break
        else:
            out.append(s_low[i])
            i += 1
    return "".join(out)

INTERNATIONAL_NAME_MAP = {
    "george": "Георгий", "georg": "Георгий", "georges": "Георгий", "jorge": "Георгий",
    "yuri": "Юрий", "yury": "Юрий", "egor": "Егор",
    "john": "Иван", "jean": "Иван", "juan": "Иван", "johann": "Иван", "johan": "Иван",
    "ian": "Иван", "jan": "Иван", "giovanni": "Иван",
    "alexander": "Александр", "alex": "Александр", "alexandre": "Александр",
    "michael": "Михаил", "michel": "Михаил", "miguel": "Михаил", "mike": "Михаил",
    "peter": "Петр", "pierre": "Петр", "pedro": "Петр",
    "paul": "Павел", "pablo": "Павел", "paolo": "Павел",
    "andrew": "Андрей", "andre": "Андрей", "andreas": "Андрей",
    "nicholas": "Николай", "nicolas": "Николай", "klaus": "Николай", "nick": "Николай",
    "dmitry": "Дмитрий", "dmitriy": "Дмитрий", "dmitri": "Дмитрий",
    "daniel": "Даниил", "dan": "Даниил",
    "stephen": "Степан", "stefan": "Степан", "steve": "Степан",
    "basil": "Василий", "basile": "Василий",
    "theodore": "Федор", "theo": "Федор",
    "catherine": "Екатерина", "katherine": "Екатерина", "kate": "Екатерина",
    "helen": "Елена", "helene": "Елена", "elena": "Елена",
    "mary": "Мария", "marie": "Мария",
    "anna": "Анна", "ann": "Анна", "anne": "Анна", "hannah": "Анна",
    "elizabeth": "Елизавета", "lisa": "Елизавета",
    "eugene": "Евгений", "gregory": "Григорий", "victor": "Виктор", "roman": "Роман",
    "charles": "Шарль", "louis": "Луи", "napoleon": "Наполеон",
    "ludwig": "Людвиг", "friedrich": "Фридрих", "wilhelm": "Вильгельм", "heinz": "Хайнц"
}

_LAT2CYR_HOMO = {v: k for k, v in HOMOGLYPHS.items()}
_CYR = re.compile(r"[А-Яа-яЁё]")
_LAT = re.compile(r"[A-Za-z]")
_INIT_RE = re.compile(r"^([^\W\d_])\.?([^\W\d_])?\.?$")
_PATR_SUFFIX = re.compile(r"(ович|евич|ьич|ич|овна|евна|ична|инична)$", re.I)

FIRST_CANON: Dict[str, str] = {}
for n in list(MALE_FIRST) + FEMALE_FIRST:
    FIRST_CANON[fold(n)] = n

PATR_CANON: Dict[str, str] = {}
for _m, _f in MALE_FIRST.values():
    PATR_CANON[fold(_m)] = _m
    PATR_CANON[fold(_f)] = _f

NICK_MAP: Dict[str, List[str]] = {}
for _full, _nick in NICKNAMES.items():
    NICK_MAP.setdefault(fold(_nick), []).append(_full)

SURN_CANON: Dict[str, str] = {}
for _s in SURNAMES:
    SURN_CANON[fold(_s)] = _s
    SURN_CANON[fold(to_female(_s))] = to_female(_s)

@dataclass
class Parsed:
    raw: str
    sur: List[str] = field(default_factory=list)          # нормализованные сложенные основы фамилий
    sur_spell: List[str] = field(default_factory=list)    # исходные написания частей фамилий
    prefix: str | None = None                             # иностранная приставка
    titles: List[str] = field(default_factory=list)       # титулы/обращения
    first_names: List[str] = field(default_factory=list)  # составные имена
    first: str | None = None                              # основное первое имя
    first_root: str | None = None                         # этимологический корень имени
    patr: str | None = None                               # отчество
    patr_root: str | None = None                          # этимологический корень отчества
    init_first: str | None = None
    init_patr: str | None = None
    disp_first: str | None = None
    disp_patr: str | None = None
    flags: Set[str] = field(default_factory=set)
    pattern: str = ""

    # Возвращает первую букву имени или инициал
    @property
    def fi(self) -> str | None:
        if self.first:
            f = fold(self.first)
            return f[0] if f else self.init_first
        return self.init_first

    # Возвращает первую букву отчества или инициал
    @property
    def pi(self) -> str | None:
        if self.patr:
            p = fold(self.patr)
            return p[0] if p else self.init_patr
        return self.init_patr

# Разбирает сырую строку ФИО: чистит мусор, находит приставки, инициалы, имя, фамилию и отчество
def parse_fio(raw: str) -> Parsed:
    flags: Set[str] = set()
    s = unicodedata.normalize("NFKC", raw)
    s_ocr = fix_ocr_errors(s)
    if s_ocr != s:
        s = s_ocr
        flags.add("ocr_fixed")

    s_kb = fix_keyboard_layout(s)
    if s_kb != s:
        s = s_kb
        flags.add("layout_fixed")

    s = re.sub("[" + re.escape(DASHES) + "]", "-", s)
    s = re.sub(r"[,;()\[\]]", " ", s)
    s = re.sub(r"(?<=\s)-(?=\s)", " ", s)

    raw_tokens = [t.strip() for t in s.split() if t.strip() and t.strip() != "-"]
    titles: List[str] = []
    tokens: List[str] = []

    # 1. Извлечение титулов, обращений и званий
    for t in raw_tokens:
        t_clean = t.lower().strip(".:;,")
        if t_clean in HONORIFICS_PREFIXES or t_clean in HONORIFICS_POSTFIXES:
            titles.append(t)
            flags.add("honorific")
        else:
            tokens.append(t)

    # 2. Поиск иностранных приставок к фамилиям
    detected_prefix: str | None = None
    prefix_token_idx: int = -1
    prefix_len_tokens: int = 0

    i = 0
    while i < len(tokens):
        if i + 2 < len(tokens):
            triplet = f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}".lower()
            if triplet in FOREIGN_PREFIXES_MULTI:
                detected_prefix = triplet
                prefix_token_idx = i
                prefix_len_tokens = 3
                flags.add("foreign_prefix")
                break
        if i + 1 < len(tokens):
            pair = f"{tokens[i]} {tokens[i+1]}".lower()
            if pair in FOREIGN_PREFIXES_MULTI:
                detected_prefix = pair
                prefix_token_idx = i
                prefix_len_tokens = 2
                flags.add("foreign_prefix")
                break
        single = tokens[i].lower()
        if single in FOREIGN_PREFIXES_SINGLE:
            detected_prefix = single
            prefix_token_idx = i
            prefix_len_tokens = 1
            flags.add("foreign_prefix")
            break
        i += 1

    surname_from_prefix = None
    remaining_tokens = []
    if detected_prefix is not None and prefix_token_idx != -1:
        before = tokens[:prefix_token_idx]
        after = tokens[prefix_token_idx + prefix_len_tokens:]
        if after:
            surname_from_prefix = after[0]
            remaining_tokens = before + after[1:]
        else:
            remaining_tokens = before
    else:
        remaining_tokens = list(tokens)

    # 3. Выделение инициалов и очистка слов
    init_letters: List[str] = []
    clean_words: List[str] = []
    for t in remaining_tokens:
        m = _INIT_RE.match(t)
        if m:
            init_letters += [g for g in m.groups() if g]
        else:
            clean_words.append(t.strip("."))

    # Чистит отдельное слово токена от омоглифов, транслита и интернациональных форм
    def normalize_token_word(w: str) -> List[str]:
        comps = []
        for part in w.split("-"):
            if not part:
                continue
            if _CYR.search(part) and _LAT.search(part):
                part = "".join(_LAT2CYR_HOMO.get(ch, ch) for ch in part)
                flags.add("homoglyph")
            elif _LAT.search(part):
                part_low = part.lower()
                if part_low in INTERNATIONAL_NAME_MAP:
                    part = INTERNATIONAL_NAME_MAP[part_low]
                    flags.add("international_name")
                else:
                    part = latin_to_cyr(part)
                    flags.add("translit")
            comps.append(part)
        return comps

    fixed_words: List[List[str]] = [normalize_token_word(w) for w in clean_words]

    # 4. Определение отчества
    patr = patr_idx = None
    singles = [(idx, w[0]) for idx, w in enumerate(fixed_words) if len(w) == 1]
    compounds = [idx for idx, w in enumerate(fixed_words) if len(w) > 1]

    for idx, c in singles:
        if fold(c) in PATR_CANON:
            patr, patr_idx = PATR_CANON[fold(c)], idx
            break
    if patr is None:
        for idx, c in singles:
            if len(fold(c)) >= 6 and _PATR_SUFFIX.search(norm_str(c)):
                patr, patr_idx = cap(c), idx
                break

    # 5. Определение имён (1..4 составных)
    first_names: List[str] = []
    used_word_indices: Set[int] = set()

    if surname_from_prefix is not None:
        # Если была приставка, фамилия точно известна!
        for idx, comps in enumerate(fixed_words):
            if idx == patr_idx:
                continue
            first_names.extend(comps)
            used_word_indices.add(idx)
        sur_spell = [surname_from_prefix]
        sur = [fold(s) for s in surname_from_prefix.split("-") if s]
    else:
        for c_idx in compounds:
            subparts = fixed_words[c_idx]
            if all(fold(p) in FIRST_CANON or fold(p) in NICK_MAP or get_name_etymology_root(p) for p in subparts):
                first_names.extend(subparts)
                used_word_indices.add(c_idx)
                flags.add("compound_first_name")

        for idx, c in singles:
            if idx == patr_idx:
                continue
            c_fold = fold(c)
            if c_fold in FIRST_CANON:
                first_names.append(FIRST_CANON[c_fold])
                used_word_indices.add(idx)
            elif c_fold in NICK_MAP:
                first_names.append(NICK_MAP[c_fold][0])
                used_word_indices.add(idx)
                flags.add("nick")
            elif get_name_etymology_root(c):
                root, can_name = NAME_TO_ETYMOLOGY[c_fold]
                first_names.append(can_name)
                used_word_indices.add(idx)
                flags.add("etymology")

        sur_spell = []
        sur = []
        for idx, comps in enumerate(fixed_words):
            if idx == patr_idx or idx in used_word_indices:
                continue
            for c in comps:
                sur.append(fold(c))
                sur_spell.append(c)

        if not sur and first_names and len(first_names) >= 2:
            last_taken = first_names.pop()
            sur.append(fold(last_taken))
            sur_spell.append(last_taken)

    primary_first = first_names[0] if first_names else None
    first_root = get_name_etymology_root(primary_first) if primary_first else None
    patr_root = None
    if patr:
        base_m = re.sub(r"(ович|евич|ьич|ич|овна|евна|ична|инична)$", "", norm_str(patr))
        patr_root = get_name_etymology_root(base_m)

    p = Parsed(
        raw=raw,
        sur=sur,
        sur_spell=sur_spell,
        prefix=detected_prefix,
        titles=titles,
        first_names=first_names,
        first=primary_first,
        first_root=first_root,
        patr=patr,
        patr_root=patr_root,
        flags=flags
    )

    ini = list(init_letters)
    if not p.first and ini:
        letter = ini.pop(0)
        p.init_first, p.disp_first = fold(_LAT2CYR_HOMO.get(letter, letter)) or None, letter.upper()
    if not p.patr and ini:
        letter = ini.pop(0)
        p.init_patr, p.disp_patr = fold(_LAT2CYR_HOMO.get(letter, letter)) or None, letter.upper()

    if p.first and p.patr:
        p.pattern = "полное ФИО"
    elif len(p.first_names) > 1:
        p.pattern = f"многосоставное имя ({len(p.first_names)} части)"
    elif p.first:
        p.pattern = "без отчества"
    elif p.init_first:
        p.pattern = "инициалы"
    else:
        p.pattern = "не разобрано"

    return p

# 8. 14 критериев сопоставления фамилий
# Сверяет две фамилии по цепочке из 14 эвристик (опечатки, омоглифы, приставки, род и др.)
def surname_similarity_14_criteria(s1: str, s2: str) -> Tuple[float, List[str]]:
    matches: List[str] = []

    if s1 == s2:
        return 1.0, ["1. Точное совпадение"]

    if norm_str(s1) == norm_str(s2):
        return 1.0, ["2. Регистронезависимое совпадение"]

    s1_u = unicodedata.normalize("NFKD", s1).encode("ASCII", "ignore").decode("utf-8").lower()
    s2_u = unicodedata.normalize("NFKD", s2).encode("ASCII", "ignore").decode("utf-8").lower()
    if s1_u and s2_u and s1_u == s2_u:
        matches.append("3. Unicode и снятие диакритики")

    s1_homo = "".join(_LAT2CYR_HOMO.get(c, c) for c in s1.lower())
    s2_homo = "".join(_LAT2CYR_HOMO.get(c, c) for c in s2.lower())
    if s1_homo == s2_homo:
        return 1.0, ["4. Совпадение с учётом омоглифов"]

    s1_cyr = latin_to_cyr(s1) if _LAT.search(s1) else s1
    s2_cyr = latin_to_cyr(s2) if _LAT.search(s2) else s2
    if norm_str(s1_cyr) == norm_str(s2_cyr):
        return 0.98, ["5. Прямая/обратная транслитерация"]

    s1_nopfx = re.sub(r"^(фон\s*дер|ван\s*дер|фон|ван|де|ди|да|аль|эль|von\s*der|van\s*der|von|van|de|di|da|al)\s*", "", norm_str(s1_cyr))
    s2_nopfx = re.sub(r"^(фон\s*дер|ван\s*дер|фон|ван|де|ди|да|аль|эль|von\s*der|van\s*der|von|van|de|di|da|al)\s*", "", norm_str(s2_cyr))
    if s1_nopfx == s2_nopfx and len(s1_nopfx) >= 4:
        return 0.96, ["6. Иностранные приставки (вариативность)"]

    parts1 = [fold(p) for p in re.split(r"[- ]+", s1) if p]
    parts2 = [fold(p) for p in re.split(r"[- ]+", s2) if p]
    if set(parts1) == set(parts2) and len(parts1) > 1:
        return 0.98, ["7. Составная фамилия (перестановка частей)"]

    lem1 = fold(to_male_lemma(s1_cyr))
    lem2 = fold(to_male_lemma(s2_cyr))
    if lem1 == lem2 and len(lem1) >= 4:
        return 0.99, ["8. Гендерное выравнивание (-ов/-ова, -ский/-ская)"]

    f1 = fold(s1_cyr)
    f2 = fold(s2_cyr)
    if f1 == f2:
        return 0.98, ["9. Орфографическая редукция гласных"]

    f1_nodbl = re.sub(r"(.) +", r" ", f1)
    f2_nodbl = re.sub(r"(.) +", r" ", f2)
    if f1_nodbl == f2_nodbl and len(f1_nodbl) >= 4:
        matches.append("10. Редукция удвоенных согласных")

    m1 = cyrillic_metaphone(s1_cyr)
    m2 = cyrillic_metaphone(s2_cyr)
    if m1 and m2 and m1 == m2 and len(m1) >= 3:
        matches.append("11. Фонетическое совпадение (Metaphone)")

    if fix_keyboard_layout(s1) == norm_str(s2) or fix_keyboard_layout(s2) == norm_str(s1):
        return 0.95, ["12. Исправление раскладки клавиатуры"]

    if fix_ocr_errors(norm_str(s1)) == fix_ocr_errors(norm_str(s2)):
        return 0.95, ["13. Исправление оптических опечаток (OCR)"]

    d_sim = sim_osa(f1, f2)
    jw_sim = jaro_winkler(f1, f2)
    max_metric = max(d_sim, jw_sim)

    if matches:
        final_score = max(0.85, max_metric)
        return final_score, matches + [f"14. Метрики сходства ({max_metric:.2f})"]

    if max_metric >= 0.80:
        return max_metric, [f"14. Дамерау-Левенштейн/Яро-Винклер ({max_metric:.2f})"]

    return max_metric, []

# 9. Сопоставление имён и отчеств
# Сравнивает имена с учетом уменьшительных форм, корней этимологии и инициалов
def first_name_similarity(p1: Parsed, p2: Parsed) -> float:
    fn1, fn2 = p1.first, p2.first
    r1, r2 = p1.first_root, p2.first_root

    if r1 and r2 and r1 == r2:
        return 1.0

    if fn1 and fn2:
        if fold(fn1) == fold(fn2):
            return 1.0
        if are_names_etymologically_identical(fn1, fn2):
            return 1.0
        f1_fold, f2_fold = fold(fn1), fold(fn2)
        if (f1_fold in NICK_MAP and fn2 in NICK_MAP[f1_fold]) or (f2_fold in NICK_MAP and fn1 in NICK_MAP[f2_fold]):
            return 0.95
        set1 = {fold(x) for x in p1.first_names}
        set2 = {fold(x) for x in p2.first_names}
        if set1 & set2:
            return 0.95
        return sim_osa(fold(fn1), fold(fn2))

    i1 = p1.fi
    i2 = p2.fi
    if i1 and i2:
        return 1.0 if i1 == i2 else 0.0

    return 0.5

# Сравнивает отчества по этимологии, полному написанию или первым буквам
def patronymic_similarity(p1: Parsed, p2: Parsed) -> float:
    pt1, pt2 = p1.patr, p2.patr
    r1, r2 = p1.patr_root, p2.patr_root

    if r1 and r2 and r1 == r2:
        return 1.0

    if pt1 and pt2:
        if fold(pt1) == fold(pt2):
            return 1.0
        return sim_osa(fold(pt1), fold(pt2))

    i1 = p1.pi
    i2 = p2.pi
    if i1 and i2:
        return 1.0 if i1 == i2 else 0.0

    return 0.5

# 10. Golden Record и классификация
class Golden:
    # Инициализирует профиль эталонной сущности персоны (Golden Record)
    def __init__(self, gid: int):
        self.gid = gid
        self.recs: List[Tuple[Any, Parsed, str, float]] = []
        self.clusters: List[List[Tuple[str, str, bool]]] = []
        self.order_ref: List[str] = []
        self.first: str | None = None
        self.first_names: List[str] = []
        self.first_root: str | None = None
        self.patr: str | None = None
        self.patr_root: str | None = None
        self.prefix: str | None = None
        self.init_first: str | None = None
        self.init_patr: str | None = None
        self.disp_first: str | None = None
        self.disp_patr: str | None = None
        self.aliases: List[Dict[str, Any]] = []

    # Возвращает множество всех основ фамилий, накопленных в кластерах сущности
    @property
    def sur(self) -> Set[str]:
        return {f for cl in self.clusters for (f, _, _) in cl}

    # Возвращает инициал имени эталонной записи
    @property
    def fi(self) -> str | None:
        if self.first:
            f = fold(self.first)
            return f[0] if f else self.init_first
        return self.init_first

    # Возвращает инициал отчества эталонной записи
    @property
    def pi(self) -> str | None:
        if self.patr:
            p = fold(self.patr)
            return p[0] if p else self.init_patr
        return self.init_patr

    # Добавляет новый распознанный вариант ФИО в кластеры эталонной записи
    def add(self, key: Any, p: Parsed, method: str, score: float):
        self.recs.append((key, p, method, score))
        tl = "translit" in p.flags

        for f, sp in zip(p.sur, p.sur_spell):
            for cl in self.clusters:
                if any(f == x[0] or (sim_osa(f, x[0]) >= 0.80) for x in cl):
                    cl.append((f, sp, tl))
                    break
            else:
                self.clusters.append([(f, sp, tl)])

        if len(p.sur) > len(self.order_ref):
            self.order_ref = list(p.sur)

        if p.prefix and not self.prefix:
            self.prefix = p.prefix

        if p.first and not self.first:
            self.first = p.first
            self.first_names = list(p.first_names)
            self.first_root = p.first_root

        if p.patr and not self.patr:
            self.patr = p.patr
            self.patr_root = p.patr_root

        if p.init_first and not self.init_first:
            self.init_first, self.disp_first = p.init_first, p.disp_first

        if p.init_patr and not self.init_patr:
            self.init_patr, self.disp_patr = p.init_patr, p.disp_patr

    # Возвращает текстовое представление первой привязанной записи
    def label(self) -> str:
        return self.recs[0][1].raw if self.recs else "?"

# Проверяет строгое совпадение входного ФИО с эталоном по высоким порогам сходства
def is_exact(p: Parsed, g: Golden) -> bool:
    if not (p.first and g.first):
        return False

    s_sim, _ = surname_similarity_14_criteria(
        " ".join(p.sur_spell),
        " ".join(g.recs[0][1].sur_spell) if g.recs else ""
    )
    if s_sim < 0.95:
        return False

    fn_sim = first_name_similarity(p, g.recs[0][1] if g.recs else p)
    if fn_sim < 0.95:
        return False

    if p.patr and g.patr:
        pt_sim = patronymic_similarity(p, g.recs[0][1] if g.recs else p)
        if pt_sim < 0.90:
            return False

    return True

# Быстро отсекает заведомо несовместимые записи по несовпадающим инициалам или фамилии
def compatible(p: Parsed, g: Golden) -> bool:
    if not g.recs:
        return False
    ref_p = g.recs[0][1]

    s_sim, _ = surname_similarity_14_criteria(
        " ".join(p.sur_spell),
        " ".join(ref_p.sur_spell)
    )
    if s_sim < 0.85:
        return False

    if p.fi and g.fi and p.fi != g.fi:
        if not (p.first_root and g.first_root and p.first_root == g.first_root):
            return False

    if p.first and g.first:
        if first_name_similarity(p, ref_p) < 0.70:
            return False

    if p.pi and g.pi and p.pi != g.pi:
        if not (p.patr_root and g.patr_root and p.patr_root == g.patr_root):
            return False

    return True

# Вычисляет взвешенную оценку похожести ФИО (50% фамилия, 30% имя, 20% отчество)
def fuzzy_score(p: Parsed, g: Golden) -> Tuple[float, List[str]]:
    if not g.recs:
        return 0.0, []
    ref_p = g.recs[0][1]

    sur_score, sur_crits = surname_similarity_14_criteria(
        " ".join(p.sur_spell),
        " ".join(ref_p.sur_spell)
    )
    if sur_score < 0.70:
        return 0.0, []

    fn_score = first_name_similarity(p, ref_p)
    pt_score = patronymic_similarity(p, ref_p)

    total = 0.50 * sur_score + 0.30 * fn_score + 0.20 * pt_score
    details = [f"Фамилия: {sur_score:.2f} ({', '.join(sur_crits)})",
               f"Имя: {fn_score:.2f}",
               f"Отчество: {pt_score:.2f}"]
    return total, details

# Ищет соответствие входного ФИО среди существующих эталонов (точное, по паттерну, нечёткое или новый профиль)
def resolve(p: Parsed, goldens: List[Golden]) -> Tuple[str, Golden | None, float, str]:
    ex = [g for g in goldens if is_exact(p, g)]
    if len(ex) == 1:
        return "exact", ex[0], 1.0, "Точное совпадение (включая этимологическое тождество)"

    cands = [g for g in goldens if compatible(p, g)]
    if len(cands) == 1:
        return "pattern", cands[0], 1.0, "Совпадение по шаблону (фамилия + инициалы/частичное ФИО)"

    scored = []
    for g in goldens:
        score, details = fuzzy_score(p, g)
        if score >= REVIEW_THRESHOLD:
            scored.append((score, g.gid, g, details))

    scored.sort(key=lambda x: (-x[0], x[1]))

    if scored:
        best_score, _, best_g, details = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        gap = best_score - second_score

        if best_score >= AUTO_THRESHOLD and gap >= MIN_GAP:
            return "fuzzy", best_g, round(best_score, 4), f"Нечёткое совпадение ({best_score:.2f}): {'; '.join(details)}"

        if gap < MIN_GAP:
            return "review", best_g, round(best_score, 4), (
                f"Неоднозначность (оценка {best_score:.2f}, отрыв {gap:.2f} < {MIN_GAP}): "
                f"кандидат «{best_g.label()}»"
            )

        return "review", best_g, round(best_score, 4), (
            f"Спорная запись (оценка {best_score:.2f} в интервале [{REVIEW_THRESHOLD}..{AUTO_THRESHOLD}]): "
            f"кандидат «{best_g.label()}»"
        )

    return "new", None, 0.0, "Новый человек (совпадений не обнаружено)"

# Собирает итоговое нормализованное представление персоны (фамилию, имя, отчество и ключ сопоставления)
def finalize(g: Golden) -> Dict[str, Any]:
    ref_p = g.recs[0][1] if g.recs else None
    if ref_p and ref_p.prefix:
        prefix_part = ref_p.prefix
        base_parts = [sp for sp in ref_p.sur_spell if fold(sp) != fold(prefix_part)]
        last = f"{prefix_part} {'-'.join(cap(b) for b in base_parts)}"
    elif ref_p and ref_p.sur_spell:
        last = "-".join(cap(sp) for sp in ref_p.sur_spell)
    else:
        last = "Неизвестно"

    first = g.first or (f"{g.disp_first}." if g.disp_first else "?")
    middle = g.patr or (f"{g.disp_patr}." if g.disp_patr else None)
    canonical = canonical_from_parts(last, first, middle or "")

    return {
        "last": last,
        "first": first,
        "middle": middle,
        "canonical": canonical,
        "complete": bool(g.first and (g.patr or g.prefix)),
        "key": match_key(last, first, middle or "")
    }