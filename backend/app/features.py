"""Агшилтын хугацааны цувааг цэвэрлэж, time-series шинж чанар (feature) гаргах модуль.

Оролт: агшилт бүрийн (start, end) хугацаа секундээр (эсвэл epoch).
Гаралт: тогтмол урттай тоон вектор (dict).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

MIN_VALID_DURATION_S = 10.0     # 10 с-ээс богино "товч дарж орхисон" бичлэгийг хасна
MAX_VALID_DURATION_S = 180.0    # 3 минутаас урт бичлэгийг алдаатай гэж үзэж таслана
WINDOW_S = 60 * 60              # сүүлийн 60 минутын цонх


@dataclass
class Contraction:
    start: float  # секунд
    end: float    # секунд
    pain: float | None = None  # 1-10

    @property
    def duration(self) -> float:
        return self.end - self.start


def clean(contractions: Iterable[Contraction]) -> list[Contraction]:
    """Өгөгдөл цэвэрлэх: эрэмбэлэх, буруу/давхцсан/хэт богино бичлэгийг засах."""
    items = sorted((c for c in contractions if c.end > c.start), key=lambda c: c.start)
    out: list[Contraction] = []
    for c in items:
        if c.duration < MIN_VALID_DURATION_S:
            continue  # санамсаргүй товшилт
        if c.duration > MAX_VALID_DURATION_S:
            c = Contraction(c.start, c.start + MAX_VALID_DURATION_S, c.pain)
        if out and c.start < out[-1].end:  # давхцал -> нэгтгэнэ
            prev = out[-1]
            pains = [p for p in (prev.pain, c.pain) if p is not None]
            out[-1] = Contraction(prev.start, max(prev.end, c.end), max(pains) if pains else None)
            continue
        out.append(c)
    return out


def _slope(y: Sequence[float]) -> float:
    """Энгийн шугаман регрессийн налалт (индексээр)."""
    if len(y) < 3:
        return 0.0
    x = np.arange(len(y), dtype=float)
    return float(np.polyfit(x, np.asarray(y, dtype=float), 1)[0])


FEATURE_NAMES = [
    "n_contractions", "freq_per_hour", "span_min",
    "dur_mean", "dur_min", "dur_max", "dur_std",
    "int_mean", "int_min", "int_max", "int_std", "int_cv",
    "int_trend", "dur_trend",
    "frac_int_le5", "frac_dur_ge60", "regularity",
    "rule511_minutes",
    "pain_last", "pain_mean", "pain_trend",
    "ga_week", "preterm",
]


def extract(contractions: Iterable[Contraction], ga_week: int, now: float | None = None) -> dict[str, float]:
    """Сүүлийн 60 минутын цонхноос шинж чанар гаргах.

    D_avg = ΣD_i/n,  I_avg = ΣI_i/(n-1),  σ_I = sqrt(Σ(I_i - I_avg)^2/(n-1)),  CV_I = σ_I / I_avg
    regularity = 1 / (1 + CV_I)
    """
    cs = clean(contractions)
    if now is None:
        now = cs[-1].end if cs else 0.0
    win = [c for c in cs if c.start >= now - WINDOW_S]

    f = {k: 0.0 for k in FEATURE_NAMES}
    f["ga_week"] = float(ga_week)
    f["preterm"] = 1.0 if ga_week < 37 else 0.0
    n = len(win)
    f["n_contractions"] = float(n)
    if n == 0:
        f["int_mean"] = f["int_min"] = f["int_max"] = 60.0
        f["regularity"] = 0.0
        return f

    d = np.array([c.duration for c in win])
    starts = np.array([c.start for c in win])
    # нийт бүртгэлийн үргэлжлэх хугацаа (5-1-1-ийн "1 цаг" нөхцөлд хэрэгтэй)
    f["span_min"] = max(now - cs[0].start, 1.0) / 60.0
    win_s = max(now - starts[0], 1.0)
    # цонхны урт богино бол давтамжийг бодит хугацаагаар хэвийн болгоно (доод тал нь 15 мин)
    f["freq_per_hour"] = n / max(win_s, 15 * 60) * 3600.0
    f["dur_mean"], f["dur_min"], f["dur_max"] = float(d.mean()), float(d.min()), float(d.max())
    f["dur_std"] = float(d.std(ddof=1)) if n > 1 else 0.0
    f["dur_trend"] = _slope(d)

    if n >= 2:
        iv = np.diff(starts) / 60.0  # эхлэлээс эхлэл хүртэлх интервал (минут)
        f["int_mean"], f["int_min"], f["int_max"] = float(iv.mean()), float(iv.min()), float(iv.max())
        f["int_std"] = float(iv.std(ddof=1)) if len(iv) > 1 else 0.0
        f["int_cv"] = f["int_std"] / f["int_mean"] if f["int_mean"] > 0 else 0.0
        f["int_trend"] = _slope(iv)
        f["frac_int_le5"] = float((iv <= 5.0).mean())
        f["regularity"] = 1.0 / (1.0 + f["int_cv"])
    else:
        f["int_mean"] = f["int_min"] = f["int_max"] = 60.0
        f["regularity"] = 0.0
    if len(cs) >= 2:
        # 5-1-1: интервал ≤5 мин, үргэлжлэх ≥60 с нөхцөл тасралтгүй хэдэн минут хадгалагдсан (бүх түүхээр)
        s_all = np.array([c.start for c in cs])
        d_all = np.array([c.duration for c in cs])
        iv_all = np.diff(s_all) / 60.0
        ok = (iv_all <= 5.0) & (d_all[1:] >= 55.0)  # 5 с хүлцэл
        run, best = 0.0, 0.0
        for i, good in enumerate(ok):
            run = run + iv_all[i] if good else 0.0
            best = max(best, run)
        f["rule511_minutes"] = best
    f["frac_dur_ge60"] = float((d >= 60.0).mean())

    pains = [c.pain for c in win if c.pain is not None]
    if pains:
        f["pain_last"] = float(pains[-1])
        f["pain_mean"] = float(np.mean(pains))
        f["pain_trend"] = _slope(pains)
    return f


def to_vector(f: dict[str, float]) -> list[float]:
    return [float(f[k]) for k in FEATURE_NAMES]
