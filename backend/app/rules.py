"""Rule-based baseline ба offline горимын аюулгүй дүрэм.

Эх сурвалж: 5-1-1 дүрэм (агшилт 5 мин тутам, 1 мин үргэлжилж, 1 цаг тогтвортой) — Lamaze International;
дутуу төрөлтийн шинж: цагт 6 ба түүнээс олон агшилт — NICHD.
Анхааруулга: босго утгууд нь эмнэлгийн мэргэжилтний баталгаажуулалт шаардана.
"""
from __future__ import annotations

from .nlp import RED_FLAGS

MN_NAMES = {"bleeding": "цус гарах", "fluid_leak": "ус/шингэн гоожих", "reduced_movement": "ургийн хөдөлгөөн багасах",
            "severe_pain": "тасралтгүй хүчтэй өвдөлт", "fever": "халуурах",
            "headache_vision": "толгой өвдөх/хараа бүрэлзэх", "back_pain": "нуруу өвдөх",
            "pelvic_pressure": "аарцаг дарагдах", "pain_increasing": "өвдөлт нэмэгдэх"}

LOW, MEDIUM, HIGH = 0, 1, 2


def _red_flag(row) -> bool:
    return any(float(row.get(f"chk_{s}", 0)) > 0 or float(row.get(f"nlp_{s}", 0)) > 0 for s in RED_FLAGS)


def rule_predict(row, use_symptoms: bool = False) -> int:
    """row: features.extract() + nlp.extract() + chk_* талбаруудтай dict/Series."""
    if use_symptoms and _red_flag(row):
        return HIGH
    n = float(row["n_contractions"])
    freq = float(row["freq_per_hour"])
    if float(row["preterm"]) > 0:
        if freq >= 6:
            return HIGH
        if freq >= 4:
            return MEDIUM
        if use_symptoms and freq >= 2 and (float(row.get("chk_back_pain", 0)) or float(row.get("nlp_back_pain", 0))
                                          or float(row.get("chk_pelvic_pressure", 0))
                                          or float(row.get("nlp_pelvic_pressure", 0))):
            return MEDIUM
        return LOW
    iv, d = float(row["int_mean"]), float(row["dur_mean"])
    if n >= 3 and iv <= 5.0 and d >= 60.0 and float(row["span_min"]) >= 60:
        return HIGH
    if n >= 3 and ((iv <= 5.0 and d >= 60.0) or (iv <= 10.0 and float(row["int_cv"]) <= 0.35)):
        return MEDIUM
    return LOW


def explain(row) -> list[str]:
    """Хэрэглэгчид харуулах тайлбар (аль нөхцөл биелсэн)."""
    msgs = []
    for s in RED_FLAGS:
        if float(row.get(f"chk_{s}", 0)) or float(row.get(f"nlp_{s}", 0)):
            msgs.append(f"Анхааруулах шинж тэмдэг: {MN_NAMES[s]}")
    if float(row["preterm"]) and float(row["freq_per_hour"]) >= 4:
        msgs.append(f"37 долоо хоногоос өмнө цагт {row['freq_per_hour']:.1f} агшилт")
    if float(row["n_contractions"]) >= 3:
        msgs.append(f"Дундаж интервал {row['int_mean']:.1f} мин, дундаж үргэлжлэх {row['dur_mean']:.0f} с")
    return msgs
