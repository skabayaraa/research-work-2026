"""Монгол хэлний чөлөөт бичвэрээс шинж тэмдгийн бүтэцтэй feature гаргах (rule-based NLP).

Алхам: (1) латин -> кирилл хөрвүүлэлт, (2) үсэг нугалах (ү,ө,о->у; й->и ...),
(3) токенчлох, (4) үгийн язгуур-угтвараар тааруулах (агглютинатив хэл),
(5) NegEx-д суурилсан үгүйсгэлийн илрүүлэлт, (6) өвдөлтийн тоон утга гаргах.

Энэ модуль онош тавихгүй; зөвхөн хэрэглэгчийн бичсэн мэдээллийг бүтэцтэй болгоно.
"""
from __future__ import annotations

import re

SYMPTOMS = [
    "bleeding",          # цус гарах
    "fluid_leak",        # ус/шингэн гоожих
    "reduced_movement",  # ургийн хөдөлгөөн багасах
    "severe_pain",       # тасралтгүй хүчтэй өвдөлт
    "fever",             # халуурах
    "headache_vision",   # хүчтэй толгой өвдөх, хараа бүрэлзэх
    "back_pain",         # нуруу/бүсэлхий өвдөх
    "pelvic_pressure",   # аарцаг дарагдах
    "pain_increasing",   # өвдөлт нэмэгдэх
]
RED_FLAGS = SYMPTOMS[:6]

# ---------------------------------------------------------------- normalisation
_LAT2CYR = [
    ("shch", "щ"), ("kh", "х"), ("ts", "ц"), ("ch", "ч"), ("sh", "ш"), ("ya", "я"),
    ("yo", "е"), ("yu", "ю"), ("ye", "е"), ("ai", "ай"), ("ei", "эй"), ("oi", "ой"), ("ui", "уй"),
    ("a", "а"), ("b", "б"), ("v", "в"), ("w", "в"), ("g", "г"), ("d", "д"), ("e", "э"), ("j", "ж"),
    ("z", "з"), ("i", "и"), ("y", "и"), ("k", "к"), ("l", "л"), ("m", "м"), ("n", "н"), ("o", "о"),
    ("p", "п"), ("r", "р"), ("s", "с"), ("t", "т"), ("u", "у"), ("f", "ф"), ("h", "х"), ("c", "ц"),
    ("q", "к"), ("x", "х"),
]
_FOLD = str.maketrans({"ү": "у", "ө": "у", "о": "у", "ё": "е", "й": "и", "ы": "и", "ъ": "", "ь": "", "е": "э"})


def latin_to_cyrillic(text: str) -> str:
    out, i, t = [], 0, text.lower()
    while i < len(t):
        for lat, cyr in _LAT2CYR:
            if t.startswith(lat, i):
                out.append(cyr)
                i += len(lat)
                break
        else:
            out.append(t[i])
            i += 1
    return "".join(out)


def normalize(text: str) -> str:
    t = text.lower()
    if re.search(r"[a-z]", t):
        t = latin_to_cyrillic(t)
    t = t.translate(_FOLD)
    t = re.sub(r"([а-я])\1{2,}", r"\1\1", t)  # "маш иииих" -> "маш иих"
    return t


def tokenize(text: str) -> list[str]:
    return re.findall(r"[а-я]+|\d+(?:[.,]\d+)?|[.,!?;:]", text)


# ------------------------------------------------------------------- lexicon
# Нэг trigger = дараалсан язгуурын жагсаалт (token бүр тухайн язгуураар эхлэх ёстой).
# Бүх язгуурыг normalize() хийсэн хэлбэрээр бичнэ (у/о нугалагдсан).
_LEX: dict[str, list[list[str]]] = {
    "bleeding": [["цус"], ["цуст"], ["толбо", "гар"]],
    "fluid_leak": [["ус", "гоож"], ["ус", "гар"], ["ус", "нь", "гар"], ["шингэн", "гоож"], ["шингэн", "гар"],
                   ["хуухэд", "ус"], ["усан", "хуудии"], ["ус", "хагар"], ["нойт"], ["гоожоод"]],
    "reduced_movement": [["ходолгоон", "багас"], ["ходолгоон", "цоор"], ["ходолгоон", "мэдрэгдэхгу"],
                         ["ходлохгуи"], ["ходлохоо", "бол"], ["ходлох", "нь", "ховор"],
                         ["хоодлохгуи"], ["ходлоогуи"], ["хоосон", "хэвтэж"], ["хуухэд", "тайван", "болчих"]],
    "severe_pain": [["тасралтгуи"], ["тэвчихийн", "арга"], ["тэвчихгуи"], ["тэсэхгуи"], ["намдахгуи"],
                    ["намжихгуи"], ["хэт", "хучтэи"], ["аргагуи", "овд"]],
    "fever": [["халуур"], ["халуун", "их"], ["халуун", "38"], ["халуун", "39"], ["чичр"], ["бие", "халуу"]],
    "headache_vision": [["толгои", "хучтэи"], ["толгои", "маш"], ["толгои", "их", "овд"], ["толгои", "овд"],
                        ["нуд", "бурэлз"], ["нудни", "омно"], ["хараа", "бурэлз"], ["нуд", "гялб"], ["хараа", "муд"],
                        ["гэрэл", "гялб"], ["бурэлзэ"]],
    "back_pain": [["нуруу"], ["бусэлхии"], ["ууц"]],
    "pelvic_pressure": [["аарцаг"], ["доошоо", "тулх"], ["доошоо", "дар"], ["доошоо", "шахаж"], ["дарагд"]],
    "pain_increasing": [["овдолт", "нэмэгд"], ["овдолт", "ихэс"], ["улам", "хучтэи"], ["улам", "ихэс"],
                        ["улам", "овд"], ["нэмэгдээд"], ["хучтэи", "болж"], ["ихсээд"], ["ойртоод"]],
}

_LEX = {k: [[normalize(s) for s in pat] for pat in pats] for k, pats in _LEX.items()}

# Үгүйсгэлийн тэмдэглэгээ (NegEx-ийн адил: trigger-ээс хойшхи 3 токен дотор)
_NEG_TOKENS = {"уугуи", "угуи", "биш", "алга", "баихгуи", "бишээ", "бхгуи", "бхгу"}
_NEG_SUFFIX = ("гуи", "гуи", "гуиэ", "гуигээр", "гуиээ", "гуиб", "хгуи", "аагуи", "оогуи", "ээгуи")
_POS_OVERRIDE = {"тасралтгуи", "намдахгуи", "намжихгуи", "тэвчихгуи", "тэсэхгуи", "ходлохгуи",
                 "хоодлохгуи", "ходлоогуи", "мэдрэгдэхгуи", "аргагуи", "зогсохгуи"}
_SCOPE_BREAK = {"гэхдээ", "харин", "бас", "мон", "тэгээд", ".", ",", "!", "?", ";", ":"}


_NEG_TOKENS = {normalize(x) for x in _NEG_TOKENS}
_NEG_SUFFIX = tuple(sorted({normalize(x) for x in _NEG_SUFFIX}))
_POS_OVERRIDE = {normalize(x) for x in _POS_OVERRIDE}
_SCOPE_BREAK = {normalize(x) for x in _SCOPE_BREAK}


def _is_neg(tok: str) -> bool:
    if tok in _POS_OVERRIDE:
        return False
    return tok in _NEG_TOKENS or tok.endswith(_NEG_SUFFIX)


def _lev1(a: str, b: str) -> bool:
    """Левенштейн зай <= 1 эсэх (хурдан шалгалт)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    i = 0
    while i < min(la, lb) and a[i] == b[i]:
        i += 1
    if la == lb:
        return a[i + 1:] == b[i + 1:]
    if la > lb:
        return a[i + 1:] == b[i:]
    return a[i:] == b[i + 1:]


FUZZY = True


def _stem_match(tok: str, stem: str) -> bool:
    if tok.startswith(stem):
        return True
    if not FUZZY or len(stem) < 4:
        return False
    L = len(stem)
    return any(_lev1(tok[:k], stem) for k in (L - 1, L, L + 1) if 0 < k <= len(tok))


def _match_at(tokens: list[str], i: int, pattern: list[str]) -> int:
    """pattern-ийг i байрлалаас (хоорондоо ≤1 токен зайтай) тааруулна; таарсан сүүлийн индекс эсвэл -1."""
    j = i
    for k, stem in enumerate(pattern):
        limit = j + (1 if k == 0 else 3)
        found = -1
        for m in range(j, min(limit, len(tokens))):
            if _stem_match(tokens[m], stem):
                found = m
                break
        if found < 0:
            return -1
        if k == 0 and found != i:
            return -1
        j = found + 1
    return j - 1


def _negated(tokens: list[str], start: int, end: int) -> bool:
    # trigger-ийн өөрийнх нь сүүлийн токен үгүйсгэл агуулж болно (ж: "гоожоогүй")
    if _is_neg(tokens[end]) and tokens[end] not in _POS_OVERRIDE:
        return True
    for m in range(end + 1, min(end + 4, len(tokens))):
        if tokens[m] in _SCOPE_BREAK:
            break
        if _is_neg(tokens[m]):
            return True
    return False


_PAIN_NUM = re.compile(r"(\d{1,2})\s*(?:/\s*10|оноо|балл)")


def extract(text: str | None, use_negation: bool = True) -> dict[str, float]:
    """Бичвэрээс {symptom: 0/1, ..., pain_text: 0-10, n_mentions} гаргана."""
    out = {f"nlp_{s}": 0.0 for s in SYMPTOMS}
    out["nlp_pain_text"] = 0.0
    out["nlp_has_text"] = 0.0
    if not text or not text.strip():
        return out
    out["nlp_has_text"] = 1.0
    norm = normalize(text)
    tokens = tokenize(norm)
    for sym, patterns in _LEX.items():
        pos = neg = 0
        for i in range(len(tokens)):
            for pat in patterns:
                e = _match_at(tokens, i, pat)
                if e >= 0:
                    if use_negation and _negated(tokens, i, e):
                        neg += 1
                    else:
                        pos += 1
                    break
        if pos > 0:
            out[f"nlp_{sym}"] = 1.0
    m = _PAIN_NUM.search(norm)
    if m:
        out["nlp_pain_text"] = min(10.0, float(m.group(1)))
    return out


NLP_FEATURE_NAMES = [f"nlp_{s}" for s in SYMPTOMS] + ["nlp_pain_text", "nlp_has_text"]
