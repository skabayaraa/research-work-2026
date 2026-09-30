"""Rule-based NLP vs сургалттай (char n-gram TF-IDF + LR) шинж тэмдэг ялгагчийн харьцуулалт.
Сургалт: A багцын train хэрэглэгчид, тест: A багцын test хэрэглэгчид ба үл мэдэгдэх B багц."""
import json, sys
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.multiclass import OneVsRestClassifier
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend")); sys.path.insert(0, str(ROOT / "ml"))
from app import nlp  # noqa
from nlp_eval import evaluate  # noqa

ss = [json.loads(l) for l in open(ROOT / "ml/data/sessions_seed0.jsonl", encoding="utf8") if json.loads(l)["free_text"]]
B = [json.loads(l) for l in open(ROOT / "ml/data/heldout_B.jsonl", encoding="utf8")]
g = [s["user_id"] for s in ss]
tr, te = next(GroupShuffleSplit(1, test_size=0.3, random_state=0).split(ss, groups=g))
Y = lambda rows: np.array([[s in r["mentioned_symptoms"] for s in nlp.SYMPTOMS] for r in rows], dtype=int)
prep = lambda t: nlp.normalize(t)
vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, preprocessor=prep, sublinear_tf=True)
Xtr = vec.fit_transform([ss[i]["free_text"] for i in tr])
clf = OneVsRestClassifier(LogisticRegression(max_iter=2000, C=5, class_weight="balanced")).fit(Xtr, Y([ss[i] for i in tr]))
out = {}
for name, rows in [("A_test", [ss[i] for i in te]), ("B_heldout", B)]:
    y = Y(rows)
    p = clf.predict(vec.transform([r["free_text"] for r in rows]))
    ml = dict(P=precision_score(y, p, average="micro"), R=recall_score(y, p, average="micro"),
              F1=f1_score(y, p, average="micro"), macroF1=f1_score(y, p, average="macro", zero_division=0))
    pairs = [(r["free_text"], set(r["mentioned_symptoms"])) for r in rows]
    rb = {}
    for tag, neg, fz in [("rule_base", False, False), ("rule_neg", True, False), ("rule_neg_fuzzy", True, True)]:
        e = evaluate(pairs, neg, fz)
        rb[tag] = dict(P=e["micro"]["P"], R=e["micro"]["R"], F1=e["micro"]["F1"], macroF1=e["macro_F1"])
    out[name] = dict(n=len(rows), charLR=ml, **rb)
    # hybrid NLP: rule OR ML
    rp = np.array([[nlp.extract(r["free_text"])["nlp_" + s] for s in nlp.SYMPTOMS] for r in rows], dtype=int)
    un = np.maximum(rp, p)
    out[name]["rule_or_charLR"] = dict(P=precision_score(y, un, average="micro"), R=recall_score(y, un, average="micro"),
                                       F1=f1_score(y, un, average="micro"), macroF1=f1_score(y, un, average="macro"))
# negation-specific test on B: sentences with only negated mentions
json.dump(out, open(ROOT / "ml/results/nlp_compare.json", "w"), indent=1)
for k, v in out.items():
    print(k, v["n"])
    for m, r in v.items():
        if isinstance(r, dict): print(f"  {m:16s} P={r['P']:.3f} R={r['R']:.3f} F1={r['F1']:.3f} macroF1={r['macroF1']:.3f}")
