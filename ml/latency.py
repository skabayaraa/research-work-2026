"""E7: Хариу өгөх хугацаа (latency). uvicorn серверийг асааж, httpx-ээр хэмжинэ."""
import json, os, statistics, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx, numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
from generate_data import generate  # noqa

env = dict(os.environ, DB_PATH="/tmp/claude-0/lat.sqlite3", JWT_SECRET="x" * 40)
srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8765", "--log-level", "warning"],
                       cwd=ROOT / "backend", env=env)
try:
    for _ in range(50):
        try:
            httpx.get("http://127.0.0.1:8765/health"); break
        except Exception:
            time.sleep(0.2)
    c = httpx.Client(base_url="http://127.0.0.1:8765")
    tok = c.post("/api/v1/auth/anonymous").json()["token"]
    H = {"Authorization": "Bearer " + tok}
    ss = generate(n_users=150, seed=99)
    bodies = [dict(ga_week=s["ga_week"], contractions=[dict(start=a, end=b, pain=p) for a, b, p in s["contractions"]],
                   checkbox_symptoms=s["checkbox_symptoms"], free_text=s["free_text"] or None, now=s["now"]) for s in ss]
    for b in bodies[:20]:
        c.post("/api/v1/assess", json=b, headers=H)  # warm-up
    rtt, srv_ms = [], []
    for i in range(1000):
        b = bodies[i % len(bodies)]
        t0 = time.perf_counter(); r = c.post("/api/v1/assess", json=b, headers=H); rtt.append((time.perf_counter() - t0) * 1000)
        srv_ms.append(r.json()["server_ms"])
    def one(b):
        with httpx.Client(base_url="http://127.0.0.1:8765") as cc:
            out = []
            for _ in range(25):
                t0 = time.perf_counter(); r = cc.post("/api/v1/assess", json=b, headers=H)
                out.append(((time.perf_counter() - t0) * 1000, r.status_code))
            return out
    t0 = time.perf_counter()
    with ThreadPoolExecutor(20) as ex:
        conc = [x for lst in ex.map(one, bodies[:20]) for x in lst]
    wall = time.perf_counter() - t0
    cl = [x[0] for x in conc]
    pct = lambda a, q: float(np.percentile(a, q))
    res = dict(
        n_seq=len(rtt), n_contr_mean=float(np.mean([len(b["contractions"]) for b in bodies])),
        seq_rtt_p50=pct(rtt, 50), seq_rtt_p95=pct(rtt, 95), seq_rtt_p99=pct(rtt, 99),
        server_p50=pct(srv_ms, 50), server_p95=pct(srv_ms, 95),
        conc_users=20, conc_n=len(cl), conc_p50=pct(cl, 50), conc_p95=pct(cl, 95),
        conc_throughput_rps=len(cl) / wall, conc_errors=sum(1 for x in conc if x[1] != 200),
        cpu=os.popen("nproc").read().strip())
    json.dump(res, open(ROOT / "ml/results/latency.json", "w"), indent=1)
    print(json.dumps(res, indent=1))
finally:
    srv.terminate()
