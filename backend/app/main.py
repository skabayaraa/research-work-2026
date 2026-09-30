"""FastAPI backend: агшилтын үнэлгээ, эрсдэлийн ангилал (decision-support, онош биш).

Ажиллуулах:  uvicorn app.main:app --host 0.0.0.0 --port 8000   (backend/ хавтас дотроос)
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import numpy as np
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from xgboost import XGBClassifier

from . import features as F
from . import nlp
from .rules import explain, rule_predict

HERE = Path(__file__).resolve().parent
SECRET = os.environ.get("JWT_SECRET", "dev-only-change-me")
DB_PATH = os.environ.get("DB_PATH", str(HERE / "data.sqlite3"))
LABELS = ["LOW", "MEDIUM", "HIGH"]
DISCLAIMER = ("Энэ нь эмнэлгийн онош биш. Эргэлзэж байвал эсвэл биеийн байдал муудвал "
              "эмч, эх баригчтай холбогдох эсвэл 103 руу залгана уу.")
ADVICE = {
    "LOW": "Ажиглалтаа үргэлжлүүлж, агшилтаа бүртгэсээр байгаарай.",
    "MEDIUM": "Эмч эсвэл эх баригчтайгаа холбогдож зөвлөгөө аваарай.",
    "HIGH": "Эмнэлгийн тусламж яаралтай аваарай. Яаралтай холбоо барих хүндээ мэдэгдэх үү?",
}

app = FastAPI(title="Uterine Contraction Decision-Support API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ------------------------------------------------------------------ model
_meta = json.loads((HERE / "model_meta.json").read_text())
_model = XGBClassifier()
_model.load_model(str(HERE / "model_hybrid_xgb.json"))
FEATS: list[str] = _meta["features"]


# ------------------------------------------------------------------ DB (хамгийн бага өгөгдөл)
def _db():
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS assessment (id TEXT PRIMARY KEY, user_ref TEXT, ts TEXT, "
                "ga_week INT, n_contractions INT, level TEXT, guardrail INT)")
    return con


# ------------------------------------------------------------------ auth
bearer = HTTPBearer(auto_error=False)


def issue_token(user_ref: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=30)
    return jwt.encode({"sub": user_ref, "exp": exp}, SECRET, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    if cred is None:
        raise HTTPException(401, "Token шаардлагатай")
    try:
        return jwt.decode(cred.credentials, SECRET, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "Token хүчингүй")


# ------------------------------------------------------------------ schemas
class ContractionIn(BaseModel):
    start: float = Field(..., description="Unix секунд")
    end: float
    pain: float | None = Field(None, ge=1, le=10)


class AssessIn(BaseModel):
    ga_week: int = Field(..., ge=20, le=42)
    contractions: list[ContractionIn] = Field(default_factory=list, max_length=500)
    checkbox_symptoms: list[str] = Field(default_factory=list)
    free_text: str | None = Field(None, max_length=1000)
    now: float | None = None

    @field_validator("checkbox_symptoms")
    @classmethod
    def _known(cls, v):
        bad = [s for s in v if s not in nlp.SYMPTOMS]
        if bad:
            raise ValueError(f"Үл мэдэгдэх шинж тэмдэг: {bad}")
        return v


class AssessOut(BaseModel):
    risk_level: str
    probabilities: dict[str, float]
    guardrail_triggered: bool
    rule_baseline: str
    advice: str
    explanations: list[str]
    features: dict[str, float]
    nlp_symptoms: list[str]
    disclaimer: str
    model_version: str
    server_ms: float


# ------------------------------------------------------------------ core
def build_row(req: AssessIn) -> dict[str, float]:
    cs = [F.Contraction(c.start, c.end, c.pain) for c in req.contractions]
    row = F.extract(cs, req.ga_week, now=req.now)
    row.update(nlp.extract(req.free_text))
    for s in nlp.SYMPTOMS:
        row[f"chk_{s}"] = 1.0 if s in req.checkbox_symptoms else 0.0
    return row


def assess(req: AssessIn) -> AssessOut:
    t0 = time.perf_counter()
    row = build_row(req)
    x = np.array([[row[k] for k in FEATS]], dtype=float)
    proba = _model.predict_proba(x)[0]
    level = int(proba.argmax())
    guard = any(row[f"chk_{s}"] or row[f"nlp_{s}"] for s in nlp.RED_FLAGS)
    if guard:
        level = 2  # аюулгүй байдлын давхарга
    lab = LABELS[level]
    return AssessOut(
        risk_level=lab, probabilities={LABELS[i]: round(float(p), 4) for i, p in enumerate(proba)},
        guardrail_triggered=bool(guard), rule_baseline=LABELS[rule_predict(row, use_symptoms=True)],
        advice=ADVICE[lab], explanations=explain(row),
        features={k: round(float(row[k]), 3) for k in ("n_contractions", "freq_per_hour", "int_mean", "dur_mean",
                                                        "int_cv", "rule511_minutes", "pain_last")},
        nlp_symptoms=[s for s in nlp.SYMPTOMS if row[f"nlp_{s}"]],
        disclaimer=DISCLAIMER, model_version="hybrid-xgb-0.1",
        server_ms=round((time.perf_counter() - t0) * 1000, 3),
    )


# ------------------------------------------------------------------ routes
@app.get("/health")
def health():
    return {"status": "ok", "model": "hybrid-xgb-0.1"}


@app.post("/api/v1/auth/anonymous")
def anonymous():
    """Нэр, утасны дугааргүйгээр псевдоним ID олгоно."""
    ref = uuid.uuid4().hex
    return {"user_ref": ref, "token": issue_token(ref)}


@app.post("/api/v1/assess", response_model=AssessOut)
def assess_route(req: AssessIn, user: str = Depends(current_user)):
    out = assess(req)
    with _db() as con:  # чөлөөт бичвэрийг хадгалахгүй (privacy by design)
        con.execute("INSERT INTO assessment VALUES (?,?,?,?,?,?,?)",
                    (uuid.uuid4().hex, user, datetime.now(timezone.utc).isoformat(), req.ga_week,
                     int(out.features["n_contractions"]), out.risk_level, int(out.guardrail_triggered)))
    return out


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")
