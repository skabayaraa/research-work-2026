import os, subprocess, sys, time, json
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
env = dict(os.environ, DB_PATH="/tmp/claude-0/shot.sqlite3", JWT_SECRET="y" * 40)
srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8766", "--log-level", "warning"], cwd=ROOT / "backend", env=env)
try:
    for _ in range(50):
        try: httpx.get("http://127.0.0.1:8766/health"); break
        except Exception: time.sleep(0.2)
    now = time.time()
    cs = []
    t = now - 75 * 60
    import random; random.seed(3)
    while t < now - 90:
        d = random.uniform(58, 72); cs.append(dict(start=t, end=t + d, pain=random.choice([7, 8, 8, 9])))
        t += random.uniform(3.9, 4.8) * 60
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        pg = b.new_page(viewport=dict(width=390, height=844), device_scale_factor=2)
        pg.goto("http://127.0.0.1:8766/")
        pg.evaluate(f"localStorage.setItem('cs', JSON.stringify({json.dumps(cs)}))")
        pg.reload()
        pg.fill("#ga", "39")
        pg.fill("#text", "Сүүлийн 20 минутад өвдөлт улам хүчтэй болж байна, нуруу их өвдөөд байна. Ус гоожоогүй.")
        pg.locator("#pain").fill("8")
        pg.click("text=Аарцаг дарагдах")
        pg.screenshot(path=str(ROOT / "paper_figs/ui_timer.png"))
        pg.click("#assess"); pg.wait_for_timeout(800)
        pg.locator("#result").scroll_into_view_if_needed()
        pg.screenshot(path=str(ROOT / "paper_figs/ui_result.png"))
        print(pg.inner_text("#result"))
        pg.click("nav button[data-tab=history]"); pg.wait_for_timeout(300)
        pg.screenshot(path=str(ROOT / "paper_figs/ui_history.png"))
        b.close()
finally:
    srv.terminate()
