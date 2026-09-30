# Агшилт AI — умайн агшилтыг үнэлэх decision-support прототип

Судалгааны прототип. **Эмнэлгийн онош тавихгүй.** Бүх туршилт зохиомол (synthetic) өгөгдөл дээр хийгдсэн.

## Бүтэц
```
backend/            FastAPI сервер (features.py, nlp.py, rules.py, main.py), вэб клиент (app/static/index.html), тестүүд
ml/                 өгөгдөл үүсгэгч, туршилтууд, NLP үнэлгээ, latency, зураг гаргах скриптүүд; results/ — үр дүн
mobile_flutter/     Flutter (Android/iOS) клиентийн эх код
paper_figs/         өгүүлэлд орсон зургууд
docker-compose.yml  серверийг Docker-оор ажиллуулах
```

## Хурдан эхлэх (Python 3.11+)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export JWT_SECRET="доод-тал-нь-32-тэмдэгттэй-санамсаргүй-нууц-үг"
uvicorn app.main:app --host 0.0.0.0 --port 8000
# хөтчөөр http://localhost:8000  (вэб клиент),  http://localhost:8000/docs  (API баримт)
```

## Туршилтыг дахин давтах
```bash
cd ..                                   # project/ хавтас
python ml/generate_data.py 0            # өгөгдөл
python ml/heldout_texts.py              # NLP-ийн B багц
python ml/experiments.py                # 5 давталт, ml/results/summary.csv (≈1 мин)
python ml/nlp_eval.py ml/data/heldout_B.jsonl
python ml/nlp_compare.py
python ml/latency.py
python ml/figures.py
cd backend && python -m pytest -q       # 21 тест
```

## Flutter клиент
```bash
flutter create agshilt_ai && cd agshilt_ai
# mobile_flutter/lib/*, test/*, pubspec.yaml-г хуулна; android_snippets/-ийн мөрүүдийг AndroidManifest.xml-д нэмнэ
flutter pub get
flutter run --dart-define=API_BASE=http://10.0.2.2:8000     # Android emulator
```
Тэмдэглэл: Flutter код энэ орчинд компиляцлагдаж шалгагдаагүй; эхний `flutter analyze`-ээр гарсан жижиг алдааг засна уу.
