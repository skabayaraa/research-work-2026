"""NLP модулийн үнэлгээ: шинж тэмдэг бүрийн Precision/Recall/F1 (micro, macro)."""
import json, sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app import nlp  # noqa


def evaluate(pairs, use_negation=True, fuzzy=True):
    nlp.FUZZY = fuzzy
    tp, fp, fn = Counter(), Counter(), Counter()
    for text, gold in pairs:
        r = nlp.extract(text, use_negation=use_negation)
        for s in nlp.SYMPTOMS:
            g, p = s in gold, r["nlp_" + s] == 1
            tp[s] += g and p; fp[s] += p and not g; fn[s] += g and not p
    nlp.FUZZY = True
    res = {}
    for s in nlp.SYMPTOMS:
        P = tp[s] / max(1, tp[s] + fp[s]); R = tp[s] / max(1, tp[s] + fn[s])
        res[s] = dict(P=P, R=R, F1=2 * P * R / max(1e-9, P + R), n=tp[s] + fn[s])
    T, FP_, FN_ = sum(tp.values()), sum(fp.values()), sum(fn.values())
    P = T / max(1, T + FP_); R = T / max(1, T + FN_)
    res["micro"] = dict(P=P, R=R, F1=2 * P * R / max(1e-9, P + R))
    res["macro_F1"] = sum(res[s]["F1"] for s in nlp.SYMPTOMS) / len(nlp.SYMPTOMS)
    return res


if __name__ == "__main__":
    f = sys.argv[1]
    ss = [json.loads(l) for l in open(f, encoding="utf8")]
    pairs = [(s["free_text"], set(s["mentioned_symptoms"])) for s in ss if s["free_text"]]
    for neg, fz in [(False, False), (True, False), (True, True)]:
        r = evaluate(pairs, neg, fz)
        print(f"neg={neg} fuzzy={fz} micro P={r['micro']['P']:.3f} R={r['micro']['R']:.3f} F1={r['micro']['F1']:.3f} macroF1={r['macro_F1']:.3f}")
