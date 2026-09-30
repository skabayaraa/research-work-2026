"""E1–E8 туршилтууд: rule-based, time-series, symptom/NLP, hybrid загваруудын харьцуулалт.

Ажиллуулах:  python ml/experiments.py            (5 seed, үр дүн ml/results/ дотор)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "ml"))
from app import features as F  # noqa: E402
from app import nlp  # noqa: E402
from app.rules import rule_predict  # noqa: E402
from generate_data import LABELS, generate  # noqa: E402

OUT = ROOT / "ml" / "results"
OUT.mkdir(parents=True, exist_ok=True)

TS = [k for k in F.FEATURE_NAMES if not k.startswith("pain_")]
PAIN = ["pain_last", "pain_mean", "pain_trend", "nlp_pain_text"]
CHECK = [f"chk_{s}" for s in nlp.SYMPTOMS]
NLP = [f"nlp_{s}" for s in nlp.SYMPTOMS] + ["nlp_has_text"]
GROUPS = {
    "TS": TS,
    "SYM": PAIN + CHECK + NLP + ["ga_week", "preterm"],
    "TS+PAIN": TS + PAIN,
    "TS+CHECK": TS + CHECK,
    "TS+NLP": TS + NLP,
    "HYBRID": TS + PAIN + CHECK + NLP,
}


def featurize(sessions: list[dict]) -> pd.DataFrame:
    rows = []
    for s in sessions:
        cs = [F.Contraction(a, b, p) for a, b, p in s["contractions"]]
        f = F.extract(cs, s["ga_week"], now=s["now"])
        f.update(nlp.extract(s["free_text"]))
        for sym in nlp.SYMPTOMS:
            f[f"chk_{sym}"] = 1.0 if sym in s["checkbox_symptoms"] else 0.0
        f["user_id"] = s["user_id"]
        f["y"] = LABELS.index(s["label"])
        rows.append(f)
    return pd.DataFrame(rows)


def make_model(name: str):
    if name == "LR":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=1.0, class_weight="balanced"))
    if name == "RF":
        return RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced", n_jobs=-1,
                                      random_state=0)
    if name == "XGB":
        return XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.9,
                             colsample_bytree=0.9, objective="multi:softprob", eval_metric="mlogloss",
                             n_jobs=4, random_state=0)
    raise ValueError(name)


def fit(model, X, y):
    if isinstance(model, XGBClassifier):
        model.fit(X, y, sample_weight=compute_sample_weight("balanced", y))
    else:
        model.fit(X, y)
    return model


def metrics(y, p) -> dict:
    return dict(
        acc=accuracy_score(y, p), macro_f1=f1_score(y, p, average="macro"),
        f1_low=f1_score(y, p, labels=[0], average="macro"), f1_med=f1_score(y, p, labels=[1], average="macro"),
        f1_high=f1_score(y, p, labels=[2], average="macro"),
        rec_high=recall_score(y, p, labels=[2], average="macro"),
        prec_high=precision_score(y, p, labels=[2], average="macro", zero_division=0),
    )


def safety_decision(proba: np.ndarray, t_high: float) -> np.ndarray:
    """P(HIGH) >= t_high бол HIGH, эс бөгөөс argmax (LOW/MEDIUM)."""
    p = proba[:, :2].argmax(1)
    return np.where(proba[:, 2] >= t_high, 2, p)


def guardrail(df_rows: pd.DataFrame, p: np.ndarray) -> np.ndarray:
    """Аюулгүй байдлын хамгаалалт: хэрэглэгч улаан тугтай шинж тэмдэг (checkbox эсвэл текст) мэдээлсэн бол HIGH."""
    red = np.zeros(len(df_rows), dtype=bool)
    for s in nlp.RED_FLAGS:
        red |= (df_rows[f"chk_{s}"].values > 0) | (df_rows[f"nlp_{s}"].values > 0)
    return np.where(red, 2, p)


def tune_threshold(Xtr, ytr, gtr, cols) -> float:
    """GroupKFold OOF магадлал дээр HIGH ангиллын F2 (recall-д 2 дахин жин) хамгийн их байх босго."""
    from sklearn.metrics import fbeta_score
    oof = np.zeros((len(ytr), 3))
    for tr, va in GroupKFold(n_splits=5).split(Xtr, ytr, gtr):
        m = fit(make_model("XGB"), Xtr.iloc[tr][cols], ytr[tr])
        oof[va] = m.predict_proba(Xtr.iloc[va][cols])
    best, best_f2 = 0.5, -1.0
    for t in np.arange(0.10, 0.61, 0.02):
        pred = guardrail(Xtr, safety_decision(oof, t))
        f2 = fbeta_score(ytr, pred, beta=2, labels=[2], average="macro")
        if f2 > best_f2:
            best, best_f2 = float(t), f2
    return best


def run_seed(seed: int):
    sessions = generate(n_users=700, seed=seed)
    df = featurize(sessions)
    y, g = df["y"].values, df["user_id"].values
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=seed).split(df, y, g))
    Xtr, Xte, ytr, yte = df.iloc[tr], df.iloc[te], y[tr], y[te]
    assert not set(g[tr]) & set(g[te]), "өгөгдөл алдагдал: нэг хэрэглэгч train/test хоёуланд"

    res, preds = [], {}
    # --- A. Rule-based
    for name, use_sym in [("A1 Rule (timing)", False), ("A2 Rule (timing+red flags)", True)]:
        p = np.array([rule_predict(r, use_symptoms=use_sym) for _, r in Xte.iterrows()])
        preds[name] = p
        res.append(dict(model=name, group="RULE", **metrics(yte, p)))
    # --- B/C/D. ML
    grid = [("TS", "LR"), ("TS", "RF"), ("TS", "XGB"), ("SYM", "XGB"),
            ("HYBRID", "LR"), ("HYBRID", "RF"), ("HYBRID", "XGB"),
            ("TS+PAIN", "XGB"), ("TS+CHECK", "XGB"), ("TS+NLP", "XGB")]
    models = {}
    for grp, mname in grid:
        cols = GROUPS[grp]
        m = fit(make_model(mname), Xtr[cols], ytr)
        t0 = time.perf_counter()
        p = m.predict(Xte[cols])
        dt = (time.perf_counter() - t0) / len(Xte) * 1000
        key = f"{grp}/{mname}"
        preds[key] = p
        models[key] = m
        res.append(dict(model=key, group=grp, infer_ms_per_sample=dt, **metrics(yte, p)))
    # --- Аюулгүй байдлын давхарга: guardrail, guardrail + F2 босго
    p = guardrail(Xte, preds["HYBRID/XGB"])
    preds["HYBRID/XGB+guard"] = p
    res.append(dict(model="HYBRID/XGB+guard", group="HYBRID", **metrics(yte, p)))
    t_high = tune_threshold(Xtr.reset_index(drop=True), ytr, g[tr], GROUPS["HYBRID"])
    proba = models["HYBRID/XGB"].predict_proba(Xte[GROUPS["HYBRID"]])
    p = guardrail(Xte, safety_decision(proba, t_high))
    preds["HYBRID/XGB+safety"] = p
    res.append(dict(model="HYBRID/XGB+safety", group="HYBRID", t_high=t_high, **metrics(yte, p)))

    extra = dict(
        n_sessions=len(df), n_users=df.user_id.nunique(), n_train=len(tr), n_test=len(te),
        label_dist=df.y.value_counts().sort_index().tolist(),
        cm={k: confusion_matrix(yte, preds[k], labels=[0, 1, 2]).tolist()
            for k in ["A1 Rule (timing)", "A2 Rule (timing+red flags)", "TS/XGB", "HYBRID/XGB", "HYBRID/XGB+guard",
                      "HYBRID/XGB+safety"]},
        yte=yte.tolist(), preds={k: v.tolist() for k, v in preds.items()},
    )
    if seed == 0:
        imp = models["HYBRID/XGB"].get_booster().get_score(importance_type="gain")
        cols = GROUPS["HYBRID"]
        extra["importance"] = {cols[int(k[1:])] if k.startswith("f") and k[1:].isdigit() else k: v
                               for k, v in imp.items()}
        # E1: хугацааны тооцооны нарийвчлал (ажиглалт vs жинхэнэ)
        e1 = []
        for s, (_, r) in zip(sessions, df.iterrows()):
            ts = s["true_stats"]
            if ts["n"] >= 3 and r["n_contractions"] >= 3:
                e1.append(dict(iv_err=abs(r["int_mean"] - ts["iv_mean"]), d_err=abs(r["dur_mean"] - ts["d_mean"]),
                               n_true=ts["n"], n_obs=r["n_contractions"]))
        e1 = pd.DataFrame(e1)
        raw = []
        for s in sessions:  # цэвэрлэгээгүй хувилбар
            ts = s["true_stats"]
            c = sorted(s["contractions"])
            c = [x for x in c if x[0] >= s["now"] - 3600]
            if ts["n"] >= 3 and len(c) >= 3:
                iv = np.diff([x[0] for x in c]) / 60
                d = np.array([x[1] - x[0] for x in c])
                raw.append(dict(iv_err=abs(iv.mean() - ts["iv_mean"]), d_err=abs(d.mean() - ts["d_mean"])))
        raw = pd.DataFrame(raw)
        extra["E1"] = dict(clean_iv_mae_min=e1.iv_err.mean(), clean_d_mae_s=e1.d_err.mean(),
                           raw_iv_mae_min=raw.iv_err.mean(), raw_d_mae_s=raw.d_err.mean(),
                           clean_iv_median=e1.iv_err.median(), clean_d_median=e1.d_err.median())
        models["HYBRID/XGB"].save_model(str(ROOT / "backend" / "app" / "model_hybrid_xgb.json"))
        json.dump(dict(features=GROUPS["HYBRID"], t_high=t_high, labels=LABELS),
                  open(ROOT / "backend" / "app" / "model_meta.json", "w"), indent=2)
    return res, extra


def mcnemar(y, a, b):
    from statsmodels.stats.contingency_tables import mcnemar as mc
    ca, cb = (a == y), (b == y)
    tbl = [[int((ca & cb).sum()), int((ca & ~cb).sum())], [int((~ca & cb).sum()), int((~ca & ~cb).sum())]]
    r = mc(tbl, exact=False, correction=True)
    return dict(table=tbl, stat=float(r.statistic), p=float(r.pvalue))


if __name__ == "__main__":
    seeds = [0, 1, 2, 3, 4]
    allres, extras = [], {}
    for sd in seeds:
        r, e = run_seed(sd)
        for x in r:
            x["seed"] = sd
        allres += r
        extras[sd] = e
        print("seed", sd, "done", e["n_sessions"], e["label_dist"])
    df = pd.DataFrame(allres)
    df.to_csv(OUT / "all_results.csv", index=False)
    agg = df.groupby("model", sort=False)[["acc", "macro_f1", "f1_low", "f1_med", "f1_high", "rec_high", "prec_high"]]
    summ = agg.mean().round(3).astype(str) + " ± " + agg.std().round(3).astype(str)
    print(summ.to_string())
    summ.to_csv(OUT / "summary.csv")
    # pooled McNemar
    Y = np.concatenate([extras[s]["yte"] for s in seeds])
    P = {k: np.concatenate([extras[s]["preds"][k] for s in seeds]) for k in extras[0]["preds"]}
    tests = {
        "HYBRID/XGB vs TS/XGB": mcnemar(Y, P["HYBRID/XGB"], P["TS/XGB"]),
        "HYBRID/XGB vs A2": mcnemar(Y, P["HYBRID/XGB"], P["A2 Rule (timing+red flags)"]),
        "TS/XGB vs A1": mcnemar(Y, P["TS/XGB"], P["A1 Rule (timing)"]),
        "HYBRID/XGB vs TS+NLP/XGB": mcnemar(Y, P["HYBRID/XGB"], P["TS+NLP/XGB"]),
        "HYBRID+safety vs A2": mcnemar(Y, P["HYBRID/XGB+safety"], P["A2 Rule (timing+red flags)"]),
        "HYBRID+guard vs A2": mcnemar(Y, P["HYBRID/XGB+guard"], P["A2 Rule (timing+red flags)"]),
    }
    print(json.dumps(tests, indent=1))
    ex0 = {k: v for k, v in extras[0].items() if k not in ("yte", "preds")}
    json.dump(dict(tests=tests, seed0=ex0,
                   dataset=[{k: extras[s][k] for k in ("n_sessions", "n_users", "n_train", "n_test", "label_dist")}
                            for s in seeds],
                   cm_sum={k: np.sum([extras[s]["cm"][k] for s in seeds], axis=0).tolist() for k in extras[0]["cm"]},
                   t_high=[r["t_high"] for r in allres if "t_high" in r and r["t_high"] == r["t_high"]]),
              open(OUT / "extras.json", "w"), indent=1, default=float)
