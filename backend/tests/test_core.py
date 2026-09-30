"""Unit, integration, API тестүүд (pytest)."""
import pytest
from fastapi.testclient import TestClient

from app import features as F
from app import nlp
from app.main import app
from app.rules import HIGH, LOW, MEDIUM, rule_predict


def seq(n, iv_min, dur_s, t0=0.0, pain=6):
    return [F.Contraction(t0 + i * iv_min * 60, t0 + i * iv_min * 60 + dur_s, pain) for i in range(n)]


# ----------------------------------------------------------------- features (unit)
def test_interval_duration_exact():
    f = F.extract(seq(13, 5, 60), ga_week=39)  # 0..60 мин, now = 61 мин -> цонхонд 12 агшилт
    assert f["n_contractions"] == 12
    assert f["int_mean"] == pytest.approx(5.0)
    assert f["dur_mean"] == pytest.approx(60.0)
    assert f["int_cv"] == pytest.approx(0.0, abs=1e-9)
    assert f["span_min"] == pytest.approx(61.0)
    assert f["rule511_minutes"] == pytest.approx(60.0)
    assert f["freq_per_hour"] == pytest.approx(12 / 56 * 60, rel=1e-3)


def test_cleaning_removes_taps_and_merges_overlaps():
    cs = seq(4, 6, 50) + [F.Contraction(100, 104)] + [F.Contraction(30, 70)]
    out = F.clean(cs)
    assert all(c.duration >= F.MIN_VALID_DURATION_S for c in out)
    assert len(out) == 4  # 4 с товшилт хасагдаж, давхцал нэгтгэгдэнэ


def test_empty_input():
    f = F.extract([], ga_week=30)
    assert f["n_contractions"] == 0 and f["preterm"] == 1.0


def test_trend_negative_when_intervals_shrink():
    starts = [0, 600, 1140, 1620, 2040, 2400]
    f = F.extract([F.Contraction(s, s + 50) for s in starts], ga_week=39)
    assert f["int_trend"] < 0


# ----------------------------------------------------------------- NLP (unit)
@pytest.mark.parametrize("text,expected", [
    ("Цус гарч байна", {"bleeding"}),
    ("Цус гараагүй, ус гоожоогүй", set()),
    ("Ус гоожоод байна, халуураагүй", {"fluid_leak"}),
    ("Хүүхэд бараг хөдлөхгүй байна", {"reduced_movement"}),
    ("Гэдэс тасралтгүй өвдөөд огт намдахгүй байна", {"severe_pain"}),
    ("tsus garch baina, uvdult ulam khuchtei bolj baina", {"bleeding", "pain_increasing"}),
    ("нурру их өвдөөд байна", {"back_pain"}),  # үсгийн алдаа
    ("Цус гарсан юм биш", set()),
])
def test_nlp(text, expected):
    r = nlp.extract(text)
    assert {s for s in nlp.SYMPTOMS if r[f"nlp_{s}"]} == expected


def test_nlp_pain_number():
    assert nlp.extract("өвдөлт 8/10")["nlp_pain_text"] == 8


# ----------------------------------------------------------------- rules
def _row(cs, ga, **kw):
    r = F.extract(cs, ga)
    r.update(nlp.extract(None))
    r.update({f"chk_{s}": 0.0 for s in nlp.SYMPTOMS})
    r.update(kw)
    return r


def test_rule_511_high():
    assert rule_predict(_row(seq(14, 4.8, 65), 39)) == HIGH


def test_rule_preterm_frequency():
    assert rule_predict(_row(seq(7, 8, 40), 32)) == HIGH
    assert rule_predict(_row(seq(3, 25, 30), 32)) == LOW


def test_rule_red_flag_only_with_symptoms():
    r = _row(seq(3, 20, 30), 39, chk_bleeding=1.0)
    assert rule_predict(r, use_symptoms=False) == LOW
    assert rule_predict(r, use_symptoms=True) == HIGH


def test_rule_early_labor_medium():
    assert rule_predict(_row(seq(6, 8, 45), 39)) == MEDIUM


# ----------------------------------------------------------------- API (integration)
client = TestClient(app)


def _token():
    return client.post("/api/v1/auth/anonymous").json()["token"]


def test_requires_auth():
    assert client.post("/api/v1/assess", json={"ga_week": 38}).status_code == 401


def test_invalid_symptom_rejected():
    r = client.post("/api/v1/assess", json={"ga_week": 38, "checkbox_symptoms": ["x"]},
                    headers={"Authorization": "Bearer " + _token()})
    assert r.status_code == 422


def test_assess_high_guardrail():
    cs = [{"start": c.start, "end": c.end, "pain": 5} for c in seq(3, 20, 30)]
    r = client.post("/api/v1/assess", json={"ga_week": 38, "contractions": cs, "free_text": "Ус гоожоод байна"},
                    headers={"Authorization": "Bearer " + _token()})
    j = r.json()
    assert r.status_code == 200 and j["risk_level"] == "HIGH" and j["guardrail_triggered"]
    assert "fluid_leak" in j["nlp_symptoms"] and "онош биш" in j["disclaimer"]


def test_assess_active_labour():
    cs = [{"start": c.start, "end": c.end, "pain": 8} for c in seq(16, 4, 65)]
    r = client.post("/api/v1/assess", json={"ga_week": 39, "contractions": cs},
                    headers={"Authorization": "Bearer " + _token()})
    assert r.json()["risk_level"] in ("MEDIUM", "HIGH")
    assert sum(r.json()["probabilities"].values()) == pytest.approx(1.0, abs=1e-3)
