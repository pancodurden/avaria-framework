"""
Avaria — Dinamik Şablon Eşleştirici
Kullanıcının konusunu analiz edip en uygun tartışma şablonunu seçer.
"""

import json
import os
import requests

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "agents", "templates")
COMMUNITY_DIR = os.path.join(os.path.dirname(__file__), "..", "agents", "community_templates")


def _load_from_dir(directory: str) -> list[dict]:
    """Bir dizindeki tüm JSON şablonları yükler."""
    templates = []
    tdir = os.path.normpath(directory)
    if not os.path.isdir(tdir):
        return templates
    for fname in sorted(os.listdir(tdir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(tdir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                t = json.load(f)
                t["_file"] = fname
                templates.append(t)
        except (json.JSONDecodeError, OSError):
            continue
    return templates


def load_templates() -> list[dict]:
    """agents/templates/ ve agents/community_templates/ altındaki tüm şablonları yükler."""
    builtin = _load_from_dir(TEMPLATES_DIR)
    community = _load_from_dir(COMMUNITY_DIR)
    # Community şablonlarını "community" olarak işaretle
    for t in community:
        t["_community"] = True
    # İsim çakışmasında builtin kazanır
    builtin_names = {t["name"] for t in builtin}
    merged = builtin + [t for t in community if t.get("name") not in builtin_names]
    return merged


def get_template_by_name(name: str) -> dict | None:
    """İsme göre şablon döndürür."""
    for t in load_templates():
        if t.get("name") == name:
            return t
    return None


def keyword_match(topic: str, templates: list[dict]) -> tuple[str, float]:
    """Anahtar kelime eşleşmesiyle hızlı şablon tahmini yapar."""
    topic_lower = topic.lower()
    best_name = "mahkeme"
    best_score = 0

    for t in templates:
        keywords = t.get("trigger_keywords", [])
        hits = sum(1 for kw in keywords if kw.lower() in topic_lower)
        score = hits / max(len(keywords), 1)
        if score > best_score:
            best_score = score
            best_name = t["name"]

    return best_name, best_score


def llm_match(topic: str, templates: list[dict], model: str) -> str:
    """Ollama LLM ile konuyu şablona eşleştirir."""
    names = [t["name"] for t in templates]
    descriptions = "\n".join(
        f"- {t['name']}: {t.get('description', '')}" for t in templates
    )

    prompt = f"""Aşağıdaki konu için en uygun tartışma modunu seç.

KONU: {topic}

MEVCUT MODLAR:
{descriptions}

SADECE mod adını döndür, başka hiçbir şey yazma. Seçenekler: {', '.join(names)}"""

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        resp = requests.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=30
        )
        answer = resp.json().get("response", "").strip().lower()

        # Yanıttan şablon adını çıkar
        for name in names:
            if name in answer:
                return name

        return "mahkeme"  # varsayılan
    except Exception:
        return "mahkeme"


def analyze_intent(topic: str, model: str = None) -> dict:
    """Konuyu analiz eder, en uygun şablonu belirler.

    Önce keyword match dener. Skor düşükse ve model verilmişse LLM'e sorar.
    """
    templates = load_templates()
    if not templates:
        return {"template": "mahkeme", "confidence": "low", "method": "fallback"}

    kw_name, kw_score = keyword_match(topic, templates)

    # Yüksek skor → LLM'e gerek yok
    if kw_score >= 0.15:
        template = get_template_by_name(kw_name)
        return {
            "template": kw_name,
            "display_name": template.get("display_name", kw_name) if template else kw_name,
            "confidence": "high" if kw_score >= 0.25 else "medium",
            "method": "keyword",
            "score": round(kw_score, 3)
        }

    # Düşük skor → LLM ile doğrula
    if model:
        llm_name = llm_match(topic, templates, model)
        template = get_template_by_name(llm_name)
        return {
            "template": llm_name,
            "display_name": template.get("display_name", llm_name) if template else llm_name,
            "confidence": "medium",
            "method": "llm",
            "score": round(kw_score, 3)
        }

    # Model yok, skor düşük → varsayılan
    template = get_template_by_name(kw_name)
    return {
        "template": kw_name,
        "display_name": template.get("display_name", kw_name) if template else kw_name,
        "confidence": "low",
        "method": "keyword",
        "score": round(kw_score, 3)
    }
