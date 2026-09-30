import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np, pandas as pd
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "paper_figs"; OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "Liberation Serif", "font.size": 8, "axes.edgecolor": "#8a8a86",
                     "axes.linewidth": 0.6, "xtick.color": "#3a3a38", "ytick.color": "#3a3a38",
                     "axes.labelcolor": "#1f1f1e", "savefig.dpi": 300})
BLUE, ORANGE, AQUA, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#1f1f1e", "#6b6b67"
df = pd.read_csv(ROOT / "ml/results/all_results.csv")
ex = json.load(open(ROOT / "ml/results/extras.json"))

# ---------------- Fig 1: architecture
fig, ax = plt.subplots(figsize=(3.3, 2.55)); ax.set_xlim(0, 10); ax.set_ylim(0, 7.8); ax.axis("off")
def box(x, y, w, h, t, fc="#eef4fc", ec=BLUE, fs=6.3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.15", fc=fc, ec=ec, lw=0.8))
    ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, color=INK)
def arr(x1, y1, x2, y2):
    ax.annotate("", (x2, y2), (x1, y1), arrowprops=dict(arrowstyle="-|>", lw=0.8, color=MUTED, shrinkA=1, shrinkB=1))
box(0.1, 6.5, 9.8, 1.1, "Гар утасны апп: таймер · өвдөлт · шинж тэмдэг · бичвэр", fc="#fff4ee", ec=ORANGE)
box(0.1, 5.0, 4.6, 1.0, "Офлайн: агшилтын тооцоо\n+ аюулгүйн дүрэм", fc="#fff4ee", ec=ORANGE)
box(5.3, 5.0, 4.6, 1.0, "REST API (FastAPI)\nJWT · псевдоним ID")
box(0.1, 3.4, 3.1, 1.1, "Time-series\nшинж чанар (20)")
box(3.45, 3.4, 3.1, 1.1, "NLP модуль\nшинж чанар (10)")
box(6.8, 3.4, 3.1, 1.1, "Өвдөлт ба\ncheckbox (13)")
box(1.8, 1.9, 6.4, 1.1, "Feature fusion → XGBoost\n(LOW / MEDIUM / HIGH)")
box(1.8, 0.75, 6.4, 0.85, "Guardrail: аюултай шинж → HIGH", fc="#e8f7f1", ec=AQUA)
box(0.1, -0.2, 9.8, 0.6, "Түвшин, тайлбар, зөвлөмж → баталгаажуулсан яаралтай холбоо", fc="#fff4ee", ec=ORANGE)
arr(2.4, 6.5, 2.4, 6.0); arr(7.6, 6.5, 7.6, 6.0)
for x in (1.65, 5.0, 8.35): arr(7.6, 5.0, x, 4.5)
for x in (1.65, 5.0, 8.35): arr(x, 3.4, 5.0, 2.9)
arr(5.0, 1.9, 5.0, 1.6); arr(5.0, 0.75, 5.0, 0.4)
ax.set_ylim(-0.3, 7.7)
fig.savefig(OUT / "fig1_arch.png", bbox_inches="tight", pad_inches=0.02); plt.close(fig)

# ---------------- Fig 2: UI screenshots
a = Image.open(OUT / "ui_timer.png").crop((0, 0, 780, 1200))
b = Image.open(OUT / "ui_result.png").crop((0, 760, 780, 1600))
c = Image.open(OUT / "ui_history.png").crop((0, 0, 780, 1200))
H = 1200; b2 = Image.new("RGB", (780, H), "#f6f7f9"); b2.paste(b, (0, 0))
canvas = Image.new("RGB", (780 * 3 + 40, H), "white")
for i, im in enumerate([a, b2, c]): canvas.paste(im, (i * 800, 0))
fig, ax = plt.subplots(figsize=(3.3, 1.75)); ax.imshow(canvas); ax.axis("off")
for i, t in enumerate(["(a) Таймер ба оролт", "(b) Үнэлгээ", "(c) Түүх, график"]):
    ax.text(i * 800 + 390, H + 60, t, ha="center", va="top", fontsize=7)
fig.savefig(OUT / "fig2_ui.png", bbox_inches="tight", pad_inches=0.02); plt.close(fig)

# ---------------- Fig 3: model comparison
order = [("A1 Rule (timing)", "A1 Дүрэм (хугацаа)"), ("A2 Rule (timing+red flags)", "A2 Дүрэм (+шинж тэмдэг)"),
         ("TS/XGB", "B Зөвхөн time-series"), ("SYM/XGB", "C Зөвхөн шинж тэмдэг/NLP"),
         ("HYBRID/XGB", "D Hybrid"), ("HYBRID/XGB+guard", "D Hybrid + guardrail")]
g = df.groupby("model")
m1 = [g.macro_f1.mean()[k] for k, _ in order]; s1 = [g.macro_f1.std()[k] for k, _ in order]
m2 = [g.rec_high.mean()[k] for k, _ in order]; s2 = [g.rec_high.std()[k] for k, _ in order]
fig, ax = plt.subplots(figsize=(3.3, 2.3))
y = np.arange(len(order))[::-1]; h = 0.36
ax.barh(y + h / 2, m1, h, xerr=s1, color=BLUE, label="Macro-F1", error_kw=dict(lw=0.6, capsize=1.5, ecolor=INK))
ax.barh(y - h / 2, m2, h, xerr=s2, color=ORANGE, label="HIGH ангиллын Recall", error_kw=dict(lw=0.6, capsize=1.5, ecolor=INK))
for yy, v, e in zip(y, m1, s1): ax.text(v + e + 0.008, yy + h / 2, f"{v:.3f}", va="center", fontsize=6.3, color=INK)
for yy, v, e in zip(y, m2, s2): ax.text(v + e + 0.008, yy - h / 2, f"{v:.3f}", va="center", fontsize=6.3, color=INK)
ax.set_yticks(y); ax.set_yticklabels([n for _, n in order]); ax.set_xlim(0.5, 1.06)
ax.set_xlabel("Үзүүлэлтийн утга (5 давталтын дундаж ± SD)")
ax.grid(axis="x", color="#e4e4e0", lw=0.5); ax.set_axisbelow(True)
for sp in ("top", "right"): ax.spines[sp].set_visible(False)
ax.legend(loc="lower center", bbox_to_anchor=(0.4, 1.0), ncol=2, frameon=False, fontsize=7)
fig.savefig(OUT / "fig3_models.png", bbox_inches="tight", pad_inches=0.02); plt.close(fig)

# ---------------- Fig 4: confusion matrices
from matplotlib.colors import LinearSegmentedColormap
cmap = LinearSegmentedColormap.from_list("b", ["#f4f8fd", "#a9c9ef", BLUE, "#123f78"])
keys = [("TS/XGB", "(a) Зөвхөн TS"), ("HYBRID/XGB", "(b) Hybrid"), ("HYBRID/XGB+guard", "(c) Hybrid+guardrail")]
fig, axs = plt.subplots(1, 3, figsize=(3.3, 1.45))
for ax, (k, t) in zip(axs, keys):
    cm = np.array(ex["cm_sum"][k], float); pct = cm / cm.sum(1, keepdims=True) * 100
    ax.imshow(pct, cmap=cmap, vmin=0, vmax=100)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{pct[i, j]:.0f}", ha="center", va="center", fontsize=6.5,
                    color="white" if pct[i, j] > 55 else INK)
    ax.set_xticks(range(3)); ax.set_yticks(range(3))
    ax.set_xticklabels(["L", "M", "H"], fontsize=6.5); ax.set_yticklabels(["L", "M", "H"] if k == "TS/XGB" else [], fontsize=6.5)
    ax.set_title(t, fontsize=6.8, pad=3); ax.tick_params(length=0)
    for sp in ax.spines.values(): sp.set_visible(False)
axs[0].set_ylabel("Бодит ангилал", fontsize=6.8); axs[1].set_xlabel("Таамагласан ангилал (%, мөрөөр)", fontsize=6.8)
fig.tight_layout(w_pad=0.4)
fig.savefig(OUT / "fig4_cm.png", bbox_inches="tight", pad_inches=0.02); plt.close(fig)

# ---------------- Fig 5: feature importance
MN = {"preterm": "Дутуу хугацаа (<37 д.х.)", "freq_per_hour": "Цагт ногдох агшилт", "int_mean": "Дундаж интервал",
      "ga_week": "Жирэмсний долоо хоног", "rule511_minutes": "5-1-1 тогтвортой хугацаа",
      "nlp_reduced_movement": "NLP: хөдөлгөөн багасах", "nlp_fluid_leak": "NLP: ус гоожих",
      "nlp_pain_increasing": "NLP: өвдөлт нэмэгдэх", "chk_fever": "Checkbox: халуурах", "pain_mean": "Дундаж өвдөлт",
      "int_cv": "Интервалын CV", "nlp_severe_pain": "NLP: хүчтэй өвдөлт", "nlp_bleeding": "NLP: цус гарах",
      "chk_bleeding": "Checkbox: цус гарах", "chk_reduced_movement": "Checkbox: хөдөлгөөн",
      "nlp_fever": "NLP: халуурах", "nlp_headache_vision": "NLP: толгой/хараа", "dur_mean": "Дундаж үргэлжлэх",
      "chk_fluid_leak": "Checkbox: ус гоожих", "span_min": "Бүртгэлийн хугацаа", "frac_int_le5": "Интервал≤5 мин хувь",
      "chk_headache_vision": "Checkbox: толгой/хараа", "chk_severe_pain": "Checkbox: хүчтэй өвдөлт"}
imp = sorted(ex["seed0"]["importance"].items(), key=lambda x: -x[1])[:12]
tot = sum(ex["seed0"]["importance"].values())
fig, ax = plt.subplots(figsize=(3.3, 2.1))
names = [MN.get(k, k) for k, _ in imp][::-1]; vals = [v / tot * 100 for _, v in imp][::-1]
cols = [ORANGE if k.startswith(("nlp_", "chk_", "pain")) else BLUE for k, _ in imp][::-1]
ax.barh(range(len(vals)), vals, 0.62, color=cols)
for i, v in enumerate(vals): ax.text(v + 0.2, i, f"{v:.1f}", va="center", fontsize=6.3)
ax.set_yticks(range(len(vals))); ax.set_yticklabels(names, fontsize=6.8)
ax.set_xlabel("Харьцангуй ач холбогдол (gain, %)")
for sp in ("top", "right"): ax.spines[sp].set_visible(False)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=BLUE, label="Хугацааны цуваа / хугацаа"), Patch(color=ORANGE, label="Шинж тэмдэг, өвдөлт")],
          loc="lower right", frameon=False, fontsize=6.5)
fig.savefig(OUT / "fig5_imp.png", bbox_inches="tight", pad_inches=0.02); plt.close(fig)
print("ok")
