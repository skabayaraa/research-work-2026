"""NLP-ийн ерөнхийлөх чадварыг шалгах "B" багц: lexicon-ийг тааруулж ДУУССАНЫ ДАРАА
бичигдсэн, A багцаас өөр хэллэгтэй эх бичвэрүүд. Энэ багцаар lexicon-ийг засахгүй.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_data import make_text  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.nlp import SYMPTOMS  # noqa: E402

POS_B = {
    "bleeding": ["доороос цус гоожоод байна", "цусархаг юм гарсан", "бор улаан шүүрэл гарч байна",
                 "шээх үед цус харагдсан"],
    "fluid_leak": ["гэнэт их хэмжээний ус гарчихлаа", "доороос тунгалаг шингэн урсаад байна",
                   "дотуур хувцас норсон, шингэн зогсохгүй байна", "хөвөн ус гарсан байх"],
    "reduced_movement": ["хүүхэд өглөөнөөс хойш хөдлөхөө больчихлоо", "үр хөдлөхгүй удаж байна",
                         "хүүхэд их тайван болчихсон, хөдөлгөөн цөөрсөн", "ургийн хөдөлгөөн мэдрэгдэхээ байлаа"],
    "severe_pain": ["гэдэс зогсолтгүй хүчтэй өвдөөд байна", "өвдөлт намжихгүй байна",
                    "хэвлий хатуурчихаад тасралтгүй өвдөж байна", "өвдөлтөө тэсэхгүй нь"],
    "fever": ["температур 38 гарсан", "бие халуу дүүгээд байна", "жихүүдэс хүрээд халуурч байна",
              "халуун их байна"],
    "headache_vision": ["толгой хагарах гээд байна", "нүд харанхуйлаад толгой эргэж байна",
                        "нүдэнд од гялалзаад байна", "хараа муудчихлаа"],
    "back_pain": ["нурууны доод хэсэг хөндүүрлээд байна", "бүсэлхийгээр хүчтэй базлаад байна",
                  "ууц орчмоор өвдөөд байна"],
    "pelvic_pressure": ["бэлхүүс доошоо дарагдаад байна", "аарцгаар хүнд юм дарж байгаа юм шиг",
                        "доошоо шахаад байна"],
    "pain_increasing": ["агшилт улам ойртож байна", "өвдөлт хүчтэй болсоор байна", "өвдөлт ихсээд л байна",
                        "өвдөлт нэмэгдсээр байна"],
}
NEG_B = {
    "bleeding": ["цус огт гараагүй", "цус гарсангүй"],
    "fluid_leak": ["ус гараагүй байна", "шингэн гоожихгүй байна"],
    "reduced_movement": [],
    "severe_pain": [],
    "fever": ["халуурахгүй байна", "температур хэвийн"],
    "headache_vision": ["толгой өвдөөгүй", "хараа хэвийн"],
    "back_pain": ["нуруу өвдөхгүй"],
    "pelvic_pressure": [],
    "pain_increasing": [],
}
OPEN_B = ["Эмч ээ,", "Хоёр цаг орчим", "Оройноос хойш", "Одоохондоо", ""]
FILL_B = ["айж байна", "эмнэлэг явах уу", "ээж хажууд байна", "усанд орсон ч нэмэр болсонгүй", ""]


def build(n=1200, seed=123):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        k = int(rng.integers(1, 4))
        sym = set(rng.choice(SYMPTOMS, size=k, replace=False).tolist())
        text, mentioned = make_text(sym, rng.uniform(2, 9), rng, pos=POS_B, neg=NEG_B, openers=OPEN_B,
                                    fillers=FILL_B, p_mention=1.0, p_neg=0.2)
        out.append(dict(free_text=text, mentioned_symptoms=sorted(mentioned)))
    return out


if __name__ == "__main__":
    p = Path(__file__).resolve().parent / "data" / "heldout_B.jsonl"
    with p.open("w", encoding="utf8") as fh:
        for r in build():
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(p)
