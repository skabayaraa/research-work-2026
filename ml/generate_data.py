"""Synthetic (зохиомол) судалгааны өгөгдөл үүсгэгч.

Бодит жирэмсэн хүний өгөгдөл ашиглахгүй. Эмнэлгийн нийтэд ил удирдамжид
(NICHD: дутуу төрөлтийн үед цагт >=6 агшилт; Lamaze: 5-1-1 дүрэм) суурилсан
латент (далд) хувьсагчаас "жинхэнэ" ангилал тогтоож, дараа нь хэрэглэгчийн
гараар оруулах алдаа, орхигдол, чөлөөт бичвэрийн олон янз байдлыг загварчилна.

Гаралт: sessions.jsonl — сесс бүр: user_id, ga_week, contractions[(start,end,pain)],
checkbox_symptoms, free_text, true_symptoms, true_stats, label
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.nlp import RED_FLAGS, SYMPTOMS  # noqa: E402

LABELS = ["LOW", "MEDIUM", "HIGH"]

# ----------------------------------------------------------- текстийн загвар (A багц)
POS_A = {
    "bleeding": ["цус гарч байна", "бага зэрэг цус харагдлаа", "цустай ялгадас гарсан", "улаан цус гарлаа",
                 "дотуур хувцсанд цус толбо гарсан"],
    "fluid_leak": ["ус гоожоод байна", "ус нь гарсан бололтой", "шингэн гоожиж байна", "усан хүүдий хагарсан юм шиг",
                   "шингэн их гарлаа"],
    "reduced_movement": ["хүүхэд бараг хөдлөхгүй байна", "хүүхдийн хөдөлгөөн багассан", "хүүхэд хөдлөх нь ховор болсон",
                         "өнөөдөр хөдөлгөөн мэдрэгдэхгүй байна"],
    "severe_pain": ["гэдэс тасралтгүй маш хүчтэй өвдөж байна", "өвдөлт огт намдахгүй байна",
                    "тэвчихийн аргагүй өвдөж байна", "өвдөлт хэт хүчтэй, тэсэхгүй нь"],
    "fever": ["халуураад байна", "биеийн халуун 38.5 байна", "чичрүүдэж халуурч байна", "бие халуу оргиод байна"],
    "headache_vision": ["толгой хүчтэй өвдөөд нүд бүрэлзэж байна", "нүдний өмнө гэрэл гялбаад байна",
                        "толгой их өвдөж байна", "хараа бүрэлзээд байна"],
    "back_pain": ["нуруу их өвдөөд байна", "бүсэлхий өвдөж байна", "нуруу руу өвдөлт дамжаад байна", "ууц өвдөөд байна"],
    "pelvic_pressure": ["аарцаг дарагдаж байгаа юм шиг", "доошоо түлхээд байна", "доошоо дарж байгаа мэдрэмж байна"],
    "pain_increasing": ["өвдөлт нэмэгдээд байна", "улам хүчтэй болж байна", "өвдөлт ихэссэн", "агшилт ойртоод байна"],
}
NEG_A = {
    "bleeding": ["цус гараагүй", "цус алга", "цус гарахгүй байна"],
    "fluid_leak": ["ус гоожоогүй", "шингэн гараагүй"],
    "reduced_movement": ["хөдөлгөөн багасаагүй"],
    "severe_pain": [],
    "fever": ["халуураагүй", "халуун байхгүй"],
    "headache_vision": ["толгой өвдөхгүй байна", "хараа бүрэлзээгүй"],
    "back_pain": ["нуруу өвдөөгүй"],
    "pelvic_pressure": [],
    "pain_increasing": [],
}
OPENERS = ["Сүүлийн 20 минутын турш", "Өглөөнөөс хойш", "Одоо", "Сая", "Шөнөөс хойш", "Цагийн өмнөөс", ""]
FILLERS = ["санаа зовж байна", "гэртээ байна", "унтаж чадахгүй байна", "яах вэ", "нөхөр хажууд байгаа",
           "хүүхэд сайн хөдөлж байна", "ядраад байна", ""]

_CYR2LAT = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "ye", "ё": "yo", "ж": "j", "з": "z", "и": "i",
            "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "ө": "u", "п": "p", "р": "r", "с": "s",
            "т": "t", "у": "u", "ү": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "",
            "ы": "ii", "ь": "i", "э": "e", "ю": "yu", "я": "ya"}


def to_latin(text: str, rng) -> str:
    h = "h" if rng.random() < 0.5 else "kh"
    o_map = "o" if rng.random() < 0.5 else "u"
    out = []
    for ch in text.lower():
        if ch == "х":
            out.append(h)
        elif ch == "ө":
            out.append(o_map)
        else:
            out.append(_CYR2LAT.get(ch, ch))
    return "".join(out)


def typo(word: str, rng) -> str:
    if len(word) < 4 or not word.isalpha():
        return word
    i = int(rng.integers(1, len(word)))
    r = rng.random()
    if r < 0.4:
        return word[:i] + word[i + 1:]
    if r < 0.8:
        return word[:i] + word[i] + word[i:]
    return word.replace("ү", "у").replace("ө", "о")


def make_text(true_sym: set[str], pain: float, rng, pos=POS_A, neg=NEG_A, openers=OPENERS, fillers=FILLERS,
              p_mention=0.8, p_neg=0.12, p_typo=0.05, p_latin=0.12) -> tuple[str, set[str]]:
    parts, mentioned = [], set()
    for s in SYMPTOMS:
        if s in true_sym and rng.random() < p_mention:
            parts.append(str(rng.choice(pos[s])))
            mentioned.add(s)
        elif s not in true_sym and neg[s] and rng.random() < p_neg:
            parts.append(str(rng.choice(neg[s])))
    if rng.random() < 0.25:
        parts.append(f"өвдөлт {int(round(pain))}/10")
    f = str(rng.choice(fillers))
    if f:
        parts.append(f)
    rng.shuffle(parts)
    op = str(rng.choice(openers))
    text = (op + " " if op else "") + ", ".join(parts)
    text = " ".join(typo(w, rng) if rng.random() < p_typo else w for w in text.split(" "))
    if rng.random() < p_latin:
        text = to_latin(text, rng)
    return text.strip().capitalize(), mentioned


# ----------------------------------------------------------- агшилтын хугацаа
TIMING = {  # interval (мин) хүрээ, CV, duration (с)
    "irregular": dict(iv=(10, 35), cv=(0.40, 0.80), dur=(20, 45), pain=(2, 4)),
    "early": dict(iv=(6, 12), cv=(0.15, 0.35), dur=(35, 55), pain=(4, 6)),
    "borderline": dict(iv=(4.3, 6.5), cv=(0.10, 0.25), dur=(50, 68), pain=(5, 7)),
    "active": dict(iv=(2.5, 5.0), cv=(0.08, 0.22), dur=(55, 80), pain=(6, 9)),
}
TIMING_P = {"irregular": 0.42, "early": 0.22, "borderline": 0.16, "active": 0.20}


def gen_true_contractions(kind: str, t_obs_min: float, rng):
    p = TIMING[kind]
    mu_iv = rng.uniform(*p["iv"])
    cv = rng.uniform(*p["cv"])
    mu_d = rng.uniform(*p["dur"])
    trend = rng.uniform(-0.25, 0.0) if kind in ("early", "active", "borderline") else 0.0  # интервал багасах
    t, out, k = rng.uniform(0, mu_iv) * 60, [], 0
    horizon = t_obs_min * 60
    while t < horizon:
        d = float(np.clip(rng.normal(mu_d, 0.12 * mu_d), 12, 150))
        out.append([t, t + d])
        iv = max(1.5, (mu_iv + trend * k)) * 60 * float(np.clip(rng.normal(1, cv), 0.3, 2.5))
        t += max(iv, d + 20)
        k += 1
    return out, dict(mu_iv=mu_iv, cv=cv, mu_d=mu_d)


def true_stats(cs, t_end):
    win = [c for c in cs if c[0] >= t_end - 3600]
    n = len(win)
    span = (t_end - cs[0][0]) / 60 if cs else 0  # нийт ажиглалтын хугацаа
    rate = n / max(t_end - (win[0][0] if n else t_end), 900) * 3600 if n else 0.0
    iv = np.diff([c[0] for c in win]) / 60 if n > 1 else np.array([60.0])
    d = np.array([c[1] - c[0] for c in win]) if n else np.array([0.0])
    cv = float(iv.std() / iv.mean()) if len(iv) > 1 else 1.0
    # 5-1-1: сүүлийн 60 минутад интервал<=5, үргэлжлэх>=60 с (бүх агшилтын 80%+)
    ok = (iv <= 5.0) & (d[1:] >= 60.0) if n > 1 else np.array([False])
    sustained = span >= 60 and ok.mean() >= 0.8 and iv.mean() <= 5.0 and d.mean() >= 60
    timing_511 = n > 1 and iv.mean() <= 5.0 and d.mean() >= 60
    return dict(n=n, span=span, rate=rate, iv_mean=float(iv.mean()), cv=cv, d_mean=float(d.mean()),
                sustained_511=bool(sustained), timing_511=bool(timing_511))


def true_label(ga: int, st: dict, sym: set[str]) -> str:
    """Судалгааны (эмнэлгийн баталгаажаагүй) ангиллын дүрэм — латент утгад хэрэглэнэ."""
    if sym & set(RED_FLAGS):
        return "HIGH"
    if ga < 37:
        if st["rate"] >= 6:
            return "HIGH"
        if st["rate"] >= 4 or (st["rate"] >= 2 and sym & {"back_pain", "pelvic_pressure"}):
            return "MEDIUM"
        return "LOW"
    if st["sustained_511"]:
        return "HIGH"
    if st["timing_511"] or (st["iv_mean"] <= 10 and st["cv"] <= 0.35 and st["n"] >= 3):
        return "MEDIUM"
    return "LOW"


def observe(true_cs, pains, user, rng):
    """Хэрэглэгчийн гараар бүртгэх үеийн алдааг загварчлах."""
    obs = []
    for (s, e), pn in zip(true_cs, pains):
        if rng.random() < user["p_miss"]:
            continue  # бүртгэхээ мартсан
        s_o = s + rng.normal(user["delay"], 4.0)
        e_o = e + rng.normal(user["delay"] * 0.5, 6.0)
        pain = float(np.clip(round(pn + rng.normal(0, 0.8)), 1, 10)) if rng.random() < 0.7 else None
        obs.append([round(s_o, 1), round(max(e_o, s_o + 1), 1), pain])
        if rng.random() < 0.03:  # санамсаргүй давхар товшилт
            t0 = e_o + rng.uniform(5, 40)
            obs.append([round(t0, 1), round(t0 + rng.uniform(1, 8), 1), None])
    return obs


def generate(n_users=700, seed=0):
    rng = np.random.default_rng(seed)
    sessions = []
    for u in range(n_users):
        user = dict(delay=rng.uniform(0, 8), p_miss=rng.uniform(0.0, 0.12),
                    p_text=rng.uniform(0.3, 0.95), p_check=rng.uniform(0.3, 0.8),
                    p_latin=0.6 if rng.random() < 0.15 else 0.03)
        ga0 = int(rng.integers(26, 37)) if rng.random() < 0.35 else int(rng.integers(37, 42))
        for k in range(int(rng.integers(1, 4))):
            ga = int(min(41, ga0 + k * int(rng.integers(0, 2))))
            kind = str(rng.choice(list(TIMING_P), p=list(TIMING_P.values())))
            t_obs = float(rng.uniform(20, 120))
            true_cs, _ = gen_true_contractions(kind, t_obs, rng)
            t_end = true_cs[-1][1] + rng.uniform(0, 120) if true_cs else t_obs * 60
            st = true_stats(true_cs, t_end)
            sym: set[str] = set()
            if rng.random() < 0.12:
                sym |= set(rng.choice(RED_FLAGS, size=int(rng.integers(1, 3)), replace=False).tolist())
            if rng.random() < {"irregular": 0.25, "early": 0.45, "borderline": 0.55, "active": 0.7}[kind]:
                sym.add("back_pain")
            if rng.random() < {"irregular": 0.10, "early": 0.25, "borderline": 0.35, "active": 0.55}[kind]:
                sym.add("pelvic_pressure")
            if kind in ("active", "borderline", "early") and rng.random() < 0.5:
                sym.add("pain_increasing")
            base = rng.uniform(*TIMING[kind]["pain"]) + (3 if "severe_pain" in sym else 0)
            pains = [float(np.clip(base + rng.normal(0, 0.7), 1, 10)) for _ in true_cs]
            label = true_label(ga, st, sym)
            if rng.random() < 0.03:  # мэргэжилтнүүдийн санал зөрөлдөөнийг загварчлах шошгоны шуугиан
                i = LABELS.index(label)
                label = LABELS[int(np.clip(i + rng.choice([-1, 1]), 0, 2))]
            obs = observe(true_cs, pains, user, rng)
            checks = sorted(s for s in SYMPTOMS if (s in sym and rng.random() < user["p_check"])
                            or (s not in sym and rng.random() < 0.02))
            text, mentioned = ("", set())
            if rng.random() < user["p_text"]:
                text, mentioned = make_text(sym, base, rng, p_latin=user["p_latin"])
            sessions.append(dict(
                user_id=f"u{u:04d}", session_id=f"u{u:04d}_s{k}", ga_week=ga, timing_kind=kind,
                contractions=obs, now=round(t_end, 1), checkbox_symptoms=checks, free_text=text,
                true_symptoms=sorted(sym), mentioned_symptoms=sorted(mentioned), true_stats=st, label=label))
    return sessions


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    out = Path(__file__).resolve().parent / "data" / f"sessions_seed{seed}.jsonl"
    out.parent.mkdir(exist_ok=True)
    ss = generate(seed=seed)
    with out.open("w", encoding="utf8") as fh:
        for s in ss:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    from collections import Counter
    print(len(ss), Counter(s["label"] for s in ss), out)
