import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import json
import queue
import threading
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests

from ddgs import DDGS

from services.llm_client import get_ollama_models, create_llm
from utils.stateless_loop import robust_parse_json
from utils.hardware_analyzer import analyze_hardware
from utils.intent_analyzer import analyze_intent, load_templates, get_template_by_name
from agents.debaters import create_expert_agent
from agents.judge import create_judge_agent, create_security_council
from utils.tools import AGENT_TOOLS
from crewai import Task, Crew

app = FastAPI(title="Avaria Multi-Agent Framework")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def extract_search_terms(topic: str) -> str:
    """Uzun Türkçe konudan kısa, aranabilir anahtar kelime bloğu çıkarır."""
    # Uzun soru/açıklama cümlelerini ilk anlamlı kırılma noktasında kes
    short = topic
    for sep in ['. ', '? ', '! ', ', ']:
        idx = topic.find(sep, 10)
        if 10 < idx < 90:
            short = topic[:idx]
            break
    # Max 70 karakter, kelime ortasında kesme
    if len(short) > 70:
        short = short[:70].rsplit(' ', 1)[0]
    return short.strip()


def web_search(query: str, max_results: int = 4, topic_keywords: list = None) -> str:
    """DuckDuckGo araması yapar. Alakasız sonuçları filtreler, en ilgilileri öne alır."""
    _STOP = {'ve', 'bir', 'bu', 'ile', 'için', 'olan', 'de', 'da', 'mi', 'ne',
             'ki', 'o', 'ya', 'ama', 'veya', 'the', 'a', 'an', 'is', 'in',
             'of', 'to', 'and', 'or', 'that', 'it', 'as', 'be', 'at', 'by'}
    try:
        with DDGS() as ddgs:
            # Filtreleme için ekstra sonuç çek
            raw = list(ddgs.text(query, max_results=max_results * 2 + 2))
        if not raw:
            return "Bu sorgu için güncel internet verisi bulunamadı."

        if topic_keywords:
            keywords = {w.lower() for w in topic_keywords if len(w) > 4 and w.lower() not in _STOP}
            relevant, other = [], []
            for r in raw:
                text = (r.get('title', '') + ' ' + r.get('body', '')).lower()
                if any(kw in text for kw in keywords):
                    relevant.append(r)
                else:
                    other.append(r)
            results = (relevant + other)[:max_results]
        else:
            results = raw[:max_results]

        if not results:
            return "Alakalı internet verisi bulunamadı."

        out = "── GÜNCEL İNTERNET ARAŞTIRMASI ──\n\n"
        for i, r in enumerate(results, 1):
            out += f"[{i}] Başlık: {r.get('title', '')}\n"
            out += f"    Özet: {r.get('body', '')}\n"
            out += f"    Kaynak: {r.get('href', '')}\n\n"
        return out
    except Exception as e:
        return f"İnternet araştırması yapılamadı: {e}"

debate_sessions: dict[str, queue.Queue] = {}


class IntentRequest(BaseModel):
    topic: str
    model: str = ""


class TemplateImportRequest(BaseModel):
    url: str = ""
    template_data: dict = {}


class CustomTemplateRequest(BaseModel):
    name: str
    display_name: str
    description: str = ""
    roles: list[dict] = []
    trigger_keywords: list[str] = []


class ExpertRequest(BaseModel):
    model: str
    topic: str
    template: str = "mahkeme"


class AgentConfig(BaseModel):
    model: str
    personality: str = "akademik"
    data: dict


class DebateRequest(BaseModel):
    topic: str
    expert_configs: list[AgentConfig]
    president_model: str
    court_model: str
    devil_advocate: bool = False
    template: str = "mahkeme"


@app.get("/api/hardware")
def get_hardware():
    """Donanım bilgilerini ve model önerilerini döndürür."""
    try:
        return analyze_hardware()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Donanım analizi başarısız: {e}")


@app.get("/api/templates")
def get_templates():
    """Mevcut tüm tartışma şablonlarını döndürür."""
    templates = load_templates()
    return {"templates": [
        {
            "name": t["name"],
            "display_name": t.get("display_name", t["name"]),
            "description": t.get("description", ""),
            "icon": t.get("icon", ""),
            "agent_count": t.get("agent_count", 3),
            "roles": t.get("roles", [])
        }
        for t in templates
    ]}


@app.post("/api/analyze-intent")
def api_analyze_intent(req: IntentRequest):
    """Konuyu analiz edip en uygun şablonu önerir."""
    result = analyze_intent(req.topic, req.model if req.model else None)
    return result


MEMORY_PATH = "avaria_memory.json"
COMMUNITY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents", "community_templates")
os.makedirs(COMMUNITY_DIR, exist_ok=True)


# ── Faz 4: Oturum Geçmişi + Export ─────────────────────────────────

@app.get("/api/history")
def get_history():
    """Geçmiş oturumları döndürür."""
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            history = json.load(f)
        if not isinstance(history, list):
            history = [history]
    except (FileNotFoundError, json.JSONDecodeError):
        history = []
    # Her oturuma index-based ID ekle, kısa özet döndür
    summaries = []
    for i, session in enumerate(history):
        summaries.append({
            "id": i,
            "tarih": session.get("tarih", ""),
            "konu": session.get("konu", ""),
            "ozet": (session.get("muhurlu_karar", "") or "")[:100]
        })
    return {"history": list(reversed(summaries))}  # en yeni üstte


@app.get("/api/history/{session_id}")
def get_session_detail(session_id: int):
    """Tek oturumun detayını döndürür."""
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            history = json.load(f)
        if not isinstance(history, list):
            history = [history]
    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(status_code=404, detail="Geçmiş bulunamadı.")
    if session_id < 0 or session_id >= len(history):
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    return history[session_id]


@app.get("/api/export/{session_id}")
def export_session(session_id: int):
    """Oturumu Markdown formatında döndürür."""
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            history = json.load(f)
        if not isinstance(history, list):
            history = [history]
    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(status_code=404, detail="Geçmiş bulunamadı.")
    if session_id < 0 or session_id >= len(history):
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")

    s = history[session_id]
    sablon_adi = s.get('sablon_adi', 'Avaria')
    md = f"# AVARIA — Araştırma Raporu\n\n"
    md += f"**Konu:** {s.get('konu', '')}\n"
    md += f"**Tarih:** {s.get('tarih', '')}\n"
    md += f"**Şablon:** {sablon_adi}\n\n---\n\n"

    # Dinamik alan isimlerini oku (flow__role formatı)
    step_num = 1
    for key, val in s.items():
        if key in ('tarih', 'konu', 'sablon', 'sablon_adi', 'sentez', 'muhurlu_karar'):
            continue
        # Eski format desteği (agent_1_tez vb.)
        if key.startswith('agent_') or '__' in key:
            label = key.split('__')[-1] if '__' in key else key.replace('_', ' ').title()
            md += f"## {label}\n\n{val}\n\n---\n\n"
            step_num += 1

    md += f"## Sentez\n\n{s.get('sentez', '')}\n\n---\n\n"
    md += f"## Nihai Karar\n\n{s.get('muhurlu_karar', '')}\n"

    from fastapi.responses import Response
    # UTF-8 BOM ile encode — Windows'ta Türkçe karakterler düzgün görünsün
    content_bytes = ('\ufeff' + md).encode('utf-8')
    konu_slug = s.get('konu', 'oturum')[:50].replace(' ', '_')
    return Response(
        content=content_bytes,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=avaria_{konu_slug}.md"}
    )


# ── Faz 5: Plugin Ekosistemi ───────────────────────────────────────

@app.post("/api/templates/create")
def create_custom_template(req: CustomTemplateRequest):
    """Kullanıcının UI'dan oluşturduğu şablonu kaydeder."""
    # İsim doğrulama
    safe_name = "".join(c for c in req.name if c.isalnum() or c == "_").lower()
    if not safe_name:
        raise HTTPException(status_code=400, detail="Geçersiz şablon adı.")

    template = {
        "name": safe_name,
        "display_name": req.display_name,
        "description": req.description,
        "icon": "custom",
        "trigger_keywords": req.trigger_keywords,
        "agent_count": len(req.roles) if req.roles else 3,
        "flow": ["tez", "itiraz", "savunma", "hakem", "sentez", "nihai_karar"],
        "roles": req.roles or [
            {"title": f"Uzman {i+1}", "description": "", "default_personality": "akademik"}
            for i in range(3)
        ],
        "generate_prompt": f"'{{topic}}' konusu için {req.display_name} tartışması yapacak "
                          f"{len(req.roles) if req.roles else 3} uzman profili oluştur.\n\n"
                          "SADECE geçerli bir JSON dizisi döndür. Her nesne şu anahtarları içermeli:\n"
                          '- "role": uzmanın rolü (Türkçe)\n'
                          '- "goal": hedefi (1 Türkçe cümle)\n'
                          '- "backstory": geçmişi (1 Türkçe cümle)\n\n'
                          "SADECE JSON dizisini döndür."
    }

    fpath = os.path.join(COMMUNITY_DIR, f"{safe_name}.json")
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    return {"status": "ok", "name": safe_name, "path": fpath}


@app.post("/api/templates/import")
def import_template(req: TemplateImportRequest):
    """GitHub raw URL'den veya doğrudan JSON'dan şablon import eder."""
    template = {}

    if req.url:
        try:
            resp = requests.get(req.url, timeout=15)
            resp.raise_for_status()
            template = resp.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"URL'den şablon indirilemedi: {e}")
    elif req.template_data:
        template = req.template_data
    else:
        raise HTTPException(status_code=400, detail="URL veya template_data gerekli.")

    # Doğrulama
    if not isinstance(template, dict) or "name" not in template:
        raise HTTPException(status_code=400, detail="Geçersiz şablon formatı. 'name' alanı gerekli.")

    safe_name = "".join(c for c in template["name"] if c.isalnum() or c == "_").lower()
    if not safe_name:
        raise HTTPException(status_code=400, detail="Geçersiz şablon adı.")

    template["name"] = safe_name
    fpath = os.path.join(COMMUNITY_DIR, f"{safe_name}.json")
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    return {"status": "ok", "name": safe_name, "display_name": template.get("display_name", safe_name)}


@app.delete("/api/templates/{name}")
def delete_template(name: str):
    """Community şablonunu siler. Varsayılan şablonlar silinemez."""
    safe_name = "".join(c for c in name if c.isalnum() or c == "_").lower()
    fpath = os.path.join(COMMUNITY_DIR, f"{safe_name}.json")
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="Şablon bulunamadı veya varsayılan şablondur.")
    os.remove(fpath)
    return {"status": "ok", "deleted": safe_name}


# ── Bug 6 Fix: Sandbox dosya erişim endpoint'leri ────────────────────
from utils.tools import _SANDBOX_DIR

@app.get("/api/sandbox/files")
def list_sandbox_files():
    """Sandbox dizinindeki dosyaları listeler."""
    if not os.path.isdir(_SANDBOX_DIR):
        return {"files": []}
    files = []
    for fname in os.listdir(_SANDBOX_DIR):
        fpath = os.path.join(_SANDBOX_DIR, fname)
        if os.path.isfile(fpath) and not fname.startswith("_"):
            files.append({
                "name": fname,
                "size": os.path.getsize(fpath),
            })
    return {"files": files}


@app.get("/api/sandbox/download/{filename}")
def download_sandbox_file(filename: str):
    """Sandbox'taki bir dosyayı indirir."""
    from fastapi.responses import FileResponse
    safe_name = os.path.basename(filename)
    fpath = os.path.join(_SANDBOX_DIR, safe_name)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.")
    return FileResponse(fpath, filename=safe_name)


@app.get("/api/models")
def get_models():
    models = get_ollama_models()
    if not models:
        raise HTTPException(status_code=503, detail="Ollama servisine ulaşılamadı.")
    return {"models": models}


@app.post("/api/generate-experts")
def generate_experts(req: ExpertRequest):
    # Şablondan özel prompt al, yoksa varsayılan kullan
    template = get_template_by_name(req.template)
    if template and template.get("generate_prompt"):
        prompt = template["generate_prompt"].replace("{topic}", req.topic)
        prompt += f"""

Örnek format:
[
  {{"role": "Uzman Rolü", "goal": "Hedef cümlesi", "backstory": "Geçmiş cümlesi"}}
]

SADECE JSON dizisini döndür, başka hiçbir şey ekleme."""
    else:
        prompt = f"""'{req.topic}' konusu için tartışacak 3 akademik uzman profili oluştur.

SADECE geçerli bir JSON dizisi döndür. Her nesne şu anahtarları içermeli:
- "role": uzman unvanı ve alanı (Türkçe, ör. "Yapay Zeka Etiği Profesörü")
- "goal": bu tartışmada neyi kanıtlamak istediği (1 Türkçe cümle)
- "backstory": akademik geçmişi (1 Türkçe cümle)

Örnek:
[
  {{"role": "Yapay Zeka Etiği Profesörü", "goal": "Yapay zeka yargıçların insan haklarını ihlal ettiğini kanıtlamak", "backstory": "20 yıldır yapay zeka etiği üzerine araştırma yapan İstanbul Teknik Üniversitesi öğretim üyesi"}},
  {{"role": "Hukuk Teknolojisi Uzmanı", "goal": "Yapay zeka yargıçların adalet sistemini iyileştirdiğini göstermek", "backstory": "Yapay zeka mahkeme sistemleri tasarlamış eski hakim ve hukuk teknolojisi danışmanı"}},
  {{"role": "Bilişsel Bilimci", "goal": "İnsan ve yapay zeka yargısındaki bilişsel önyargıları karşılaştırmak", "backstory": "Karar verme süreçleri üzerine Orta Doğu Teknik Üniversitesi'nde araştırmacı"}}
]

Şimdi '{req.topic}' konusu için 3 uzman oluştur.
SADECE JSON dizisini döndür, başka hiçbir şey ekleme."""

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": req.model, "prompt": prompt, "stream": False},
            timeout=120
        )
        experts = robust_parse_json(response.json().get("response", ""))

        # 3'ten az geldiyse varsayılanlarla tamamla
        defaults = [
            {"role": f"Uzman {i+1}", "goal": f"'{req.topic}' konusunu analiz etmek", "backstory": "Akademik araştırmacı ve uzman"}
            for i in range(3)
        ]
        while len(experts) < 3:
            experts.append(defaults[len(experts)])

        return {"experts": experts[:3]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _extract_code_blocks(text: str) -> list[str]:
    """Metinden ```python ... ``` veya ```...``` kod bloklarını çıkarır."""
    import re
    pattern = r'```(?:python)?\s*\n(.*?)```'
    return re.findall(pattern, text, re.DOTALL)


def _code_feedback_loop(agent_output: str, agent, q: queue.Queue, step_label: str, max_retries: int = 3) -> str:
    """Yazılım ekibi modunda: ajan kod ürettiyse çalıştır, hata varsa geri besle."""
    code_blocks = _extract_code_blocks(agent_output)
    if not code_blocks:
        return agent_output

    from utils.tools import kod_calistir

    for i, code in enumerate(code_blocks):
        q.put({"type": "tool_call", "tool": "kod_calistir", "agent": step_label,
               "detail": f"Kod bloğu {i+1}/{len(code_blocks)} çalıştırılıyor..."})

        result = kod_calistir.run(code)
        q.put({"type": "tool_result", "tool": "kod_calistir", "result": result[:500]})

        # Hata varsa feedback loop
        if "HATA:" in result or "Error" in result or "Traceback" in result:
            attempt = 0
            current_code = code
            while attempt < max_retries:
                attempt += 1
                q.put({"type": "tool_call", "tool": "kod_calistir",
                       "agent": step_label,
                       "detail": f"Hata tespit edildi. Düzeltme denemesi {attempt}/{max_retries}..."})

                fix_result = getattr(
                    Crew(agents=[agent], tasks=[Task(
                        description=f"""Aşağıdaki Python kodu çalıştırıldığında hata aldı. Düzelt.

KOD:
```python
{current_code}
```

HATA:
{result}

GÖREV: Hatayı düzelt ve SADECE düzeltilmiş kodu ```python ... ``` bloğu içinde döndür.""",
                        agent=agent,
                        expected_output="Düzeltilmiş Python kodu."
                    )]).kickoff(), "raw", "")

                fixed_blocks = _extract_code_blocks(fix_result)
                if not fixed_blocks:
                    q.put({"type": "tool_result", "tool": "kod_calistir",
                           "result": f"Düzeltme {attempt}: Kod bloğu çıkarılamadı."})
                    break

                current_code = fixed_blocks[0]
                result = kod_calistir.run(current_code)
                q.put({"type": "tool_result", "tool": "kod_calistir", "result": result[:500]})

                if "HATA:" not in result and "Error" not in result and "Traceback" not in result:
                    q.put({"type": "log", "message": f"Kod düzeltildi (deneme {attempt})."})
                    break
            else:
                q.put({"type": "log", "message": f"Kod {max_retries} denemede düzeltilemedi."})
        else:
            q.put({"type": "log", "message": "Kod başarıyla çalıştı."})

    return agent_output


def heat_score(text: str) -> int:
    hot = [
        # Türkçe
        'itiraz', 'hata', 'yanlış', 'çürüt', 'yanılıyor', 'çelişki', 'kabul edilemez',
        'spekülatif', 'hatalı', 'geçersiz', 'kanıtsız', 'tehlikeli', 'yanlışlık', 'eksik',
        'saçma', 'yanıltıcı', 'temelsiz', 'çarpıtma', 'reddet', 'reddediyorum',
        # İngilizce (modeller bazen İngilizce kelimeler kullanıyor)
        'wrong', 'false', 'incorrect', 'invalid', 'reject', 'disagree', 'contradict',
        'fallacy', 'error', 'misleading', 'baseless', 'unfounded', 'refute',
    ]
    cool = [
        # Türkçe
        'sentez', 'analiz', 'değerlendirme', 'uzlaşı', 'akademik', 'tarafsız', 'objektif', 'denge',
        'işbirliği', 'ortak', 'mutabakat', 'uzlaşma',
        # İngilizce
        'synthesis', 'analysis', 'balance', 'objective', 'neutral', 'consensus',
    ]
    t = text.lower()
    h = sum(1 for w in hot if w in t)
    c = sum(1 for w in cool if w in t)
    return min(95, max(15, h * 10 - c * 5 + 25))


@app.post("/api/start-debate")
async def start_debate(req: DebateRequest):
    session_id = str(uuid.uuid4())
    q: queue.Queue = queue.Queue()
    debate_sessions[session_id] = q

    def run_crew(agents, task):
        return getattr(Crew(agents=agents, tasks=[task]).kickoff(), "raw", "Hata.")

    def run_debate():
        try:
            topic = req.topic
            configs = req.expert_configs
            roles = [c.data.get('role', f'Uzman {i+1}') for i, c in enumerate(configs)]
            goals = [c.data.get('goal', '') for c in configs]

            template_data = get_template_by_name(req.template) or {}
            use_tools = template_data.get("use_tools", False)
            is_mahkeme = req.template == "mahkeme"
            mode_label = template_data.get("display_name", req.template)
            flow = template_data.get("flow", ["tez", "itiraz", "savunma", "hakem", "sentez", "nihai_karar"])

            # Flow adımlarını okunabilir Türkçe label'lara çevir
            _FLOW_LABELS = {
                "tez": "Açılış Tezi", "itiraz": "İtiraz & Karşı Tez",
                "savunma": "Savunma & Çapraz Sorgu", "hakem": "Bağımsız Hakem Analizi",
                "sentez": "Kapsamlı Sentez", "nihai_karar": "Mühürlü Nihai Karar",
                "tasarim": "Tasarım & Mimari", "uygulama": "Uygulama Detayları",
                "test_review": "Test & Code Review",
                "literatur": "Literatür Taraması", "analiz": "Analiz & Değerlendirme",
                "elestiri": "Eleştirel İnceleme",
                "ders_anlatimi": "Ders Anlatımı", "soru_cevap": "Soru & Cevap",
                "derinlestirme": "Derinleştirme & Tartışma",
            }
            def flow_label(step_idx: int) -> str:
                if step_idx < len(flow):
                    return _FLOW_LABELS.get(flow[step_idx], flow[step_idx].replace("_", " ").title())
                return f"Adım {step_idx + 1}"

            q.put({"type": "log", "message": f"{mode_label} oturumu başlatılıyor..."})

            llm1 = create_llm(configs[0].model)
            llm2 = create_llm(configs[1].model)
            llm3 = create_llm(configs[2].model)
            llm_p = create_llm(req.president_model, temp=0.1)
            llm_c = create_llm(req.court_model, temp=0.0)

            # Şablonda use_tools: true ise ajanlar tool kullanabilir
            # Tool desteklemeyen modellerde (gemma2 vb.) otomatik devre dışı bırak
            _NO_TOOL_MODELS = {"gemma2", "gemma", "phi", "nomic-embed", "qwen2.5"}
            if use_tools:
                model_base = configs[0].model.split(":")[0].lower()
                if any(nt in model_base for nt in _NO_TOOL_MODELS):
                    use_tools = False
                    q.put({"type": "log", "message": f"'{configs[0].model}' tool desteklemiyor — tool'lar devre dışı. Tool için llama3.1 veya codestral kullanın."})

            expert_tools = AGENT_TOOLS if use_tools else []
            agent1 = create_expert_agent(configs[0].data, llm1, configs[0].personality, tools=expert_tools)
            agent2 = create_expert_agent(configs[1].data, llm2, configs[1].personality, tools=expert_tools)
            agent3 = create_expert_agent(configs[2].data, llm3, configs[2].personality, tools=expert_tools)
            president = create_judge_agent(llm_p)
            council = create_security_council(llm_c)

            # ── OTURUM 1 ──────────────────────────────────────
            q.put({"type": "step_start", "step": 1, "title": f"{roles[0]} — {flow_label(0)}"})
            q.put({"type": "log", "message": f"'{topic}' konusunda internet araştırması yapılıyor..."})
            search_base = extract_search_terms(topic)
            q1 = f"{search_base} academic research evidence 2024"
            arastirma1 = web_search(q1, topic_keywords=q1.split())
            r1 = run_crew([agent1], Task(
                description=f"""SEN KİMSİN: {roles[0]}. Uzmanlık alanın ve hedefin: {goals[0]}

GÖREV: '{topic}' konusunda mahkeme oturumunun açılış tezini sunuyorsun.

SANA SAĞLANAN GÜNCEL VERİLER:
{arastirma1}

YANIT FORMATI (Türkçe):
- Ana tezin ve temel iddia
- Yukarıdaki araştırma verilerinden seçtiğin somut kanıtlar (kaynakları belirt)
- Bu konuda senin uzmanlık alanının öngörüsü
- Neden bu pozisyonun tartışmasız olduğuna dair 2-3 güçlü argüman

Mahkeme üslubuyla yaz: ciddi, akademik, iddialı.""",
                agent=agent1,
                expected_output="Kanıta dayalı açılış tezi. Türkçe. 400-600 kelime."
            ))
            q.put({"type": "step_complete", "step": 1, "content": r1, "heat": heat_score(r1)})

            # ── Yazılım Ekibi: Kod Feedback Loop ─────────────────────────
            if use_tools:
                r1 = _code_feedback_loop(r1, agent1, q, step_label=f"{roles[0]}")

            # ── OTURUM 2 ──────────────────────────────────────
            q.put({"type": "step_start", "step": 2, "title": f"{roles[1]} — {flow_label(1)}"})
            q.put({"type": "log", "message": "Karşı argüman için araştırma yapılıyor..."})
            q2 = f"{search_base} criticism counterargument problems 2024"
            arastirma2 = web_search(q2, topic_keywords=q2.split())
            devil_prefix = ""
            if req.devil_advocate and is_mahkeme:
                devil_prefix = f"SEN ŞEYTAN'IN AVUKATISIN. Görüşün ne olursa olsun, '{roles[0]}' nin tezinin TAM KARŞISINDAKİ pozisyonu savunacaksın.\n\n"
            r2 = run_crew([agent2], Task(
                description=f"""{devil_prefix}SEN KİMSİN: {roles[1]}. Uzmanlık alanın ve hedefin: {goals[1]}

⚠️ KRİTİK KURAL: {roles[0]}'ün pozisyonunu HİÇBİR KOŞULDA destekleme veya onaylama. Tezine SERT ve DOĞRUDAN itiraz et. Uzlaşma yok.

KARŞI TARAFIN İDDİASI ({roles[0]}):
\"\"\"{r1}\"\"\"

KARŞI ARGÜMAN İÇİN GÜNCEL VERİLER:
{arastirma2}

GÖREV: Yukarıdaki teze madde madde itiraz et. Her iddiasını tek tek çürüt.

YANIT FORMATI (Türkçe):
- '{roles[0]}' nin hangi iddiası hatalı veya eksik? Neden? (Her madde için)
- Araştırma verilerinden bulduğun somut karşı kanıtlar
- Senin pozisyonunun neden daha güçlü olduğunu açıklayan alternatif çerçeve
- '{roles[0]}' nin kasıtlı olarak görmezden geldiği kritik boyutlar

Keskin, iddialı ve tavizsiz yaz. Rakibini savunmaya çek.""",
                agent=agent2,
                expected_output="Kanıta dayalı itiraz ve karşı tez. Türkçe. 400-600 kelime."
            ))
            q.put({"type": "step_complete", "step": 2, "content": r2, "heat": heat_score(r2)})

            if use_tools:
                r2 = _code_feedback_loop(r2, agent2, q, step_label=f"{roles[1]}")

            # ── OTURUM 3 ──────────────────────────────────────
            q.put({"type": "step_start", "step": 3, "title": f"{roles[0]} — {flow_label(2)}"})
            q.put({"type": "log", "message": "Savunma için ek araştırma yapılıyor..."})
            q3 = f"{search_base} defense rebuttal expert opinion"
            arastirma3 = web_search(q3, topic_keywords=q3.split())
            r3 = run_crew([agent1], Task(
                description=f"""SEN KİMSİN: {roles[0]}. Uzmanlık alanın: {goals[0]}

⚠️ KRİTİK KURAL: Başta savunduğun pozisyondan ASLA sapma. '{roles[1]}' ile uzlaşma, onaylama veya kısmen haklı bulma YOK. Orijinal tezini güçlendir.

SENİN AÇILIŞ TEZİN (unutma — bunu savunuyorsun):
\"\"\"{r1[:600]}\"\"\"

'{roles[1]}' SANA ŞÖYLE İTİRAZ ETTİ:
\"\"\"{r2}\"\"\"

SAVUNMAN İÇİN GÜNCEL VERİLER:
{arastirma3}

GÖREV: Her itiraza tek tek yanıt ver ve orijinal tezini daha güçlü kanıtlarla destekle.

YANIT FORMATI (Türkçe):
- '{roles[1]}' nin her iddiasına sırayla yanıt ver: "X dediniz, ama aslında..."
- Karşı tarafın argümanlarındaki mantık hatalarını ve veri eksikliklerini göster
- Araştırma verilerinden savunmana destek olan kanıtları kullan
- Orijinal tezinin neden hâlâ doğru olduğunu açıklayan yeni argümanlar ekle
- Mahkemeye hitaben kapanış: "Bu nedenle tezim geçerlidir çünkü..."

Savunman güçlü, tutarlı ve orijinal pozisyonuna sadık olsun. Türkçe yaz.""",
                agent=agent1,
                expected_output="Güçlü savunma ve çapraz sorgu yanıtı. Türkçe. 400-600 kelime."
            ))
            q.put({"type": "step_complete", "step": 3, "content": r3, "heat": heat_score(r3)})

            if use_tools:
                r3 = _code_feedback_loop(r3, agent1, q, step_label=f"{roles[0]}")

            # ── OTURUM 4 ───────────────────────────────────────
            q.put({"type": "step_start", "step": 4, "title": f"{roles[2]} — {flow_label(3)}"})
            q.put({"type": "log", "message": "Hakem için ek araştırma yapılıyor..."})
            q4 = f"{search_base} analysis perspectives academic study"
            arastirma4 = web_search(q4, topic_keywords=q4.split())
            r4 = run_crew([agent3], Task(
                description=f"""SEN KİMSİN: {roles[2]}. Uzmanlık alanın: {goals[2]}
Bu tartışmada bağımsız hakemsin — ne {roles[0]} ne de {roles[1]} tarafını tutuyorsun.

TARTIŞMANIN TAM TUTANAĞI:

[{roles[0]} — Açılış Tezi]
{r1}

[{roles[1]} — İtiraz]
{r2}

[{roles[0]} — Savunma]
{r3}

EK ARAŞTIRMA VERİLERİ:
{arastirma4}

GÖREV: Kendi uzmanlığın açısından bu tartışmayı değerlendir.

YANIT FORMATI (Türkçe):
- Her tarafın en güçlü argümanı neydi?
- Hangi iddialar kanıtsız veya spekülatifti?
- İki tarafın da göz ardı ettiği kritik boyut veya veri nedir?
- Senin uzmanlık alanından konuya katkın: hangi perspektif eksikti?
- Tartışmanın genel kalitesi hakkında yorum

Tarafsız, analitik ve akademik yaz. Türkçe.""",
                agent=agent3,
                expected_output="Tarafsız hakem analizi ve değerlendirmesi. Türkçe. 400-600 kelime."
            ))
            q.put({"type": "step_complete", "step": 4, "content": r4, "heat": heat_score(r4)})

            # ── OTURUM 5 ──────────────────────────────────────
            q.put({"type": "step_start", "step": 5, "title": f"Kurul Başkanı — {flow_label(4)}"})
            sentez = run_crew([president], Task(
                description=f"""SEN KİMSİN: Sentezleyici Kurul Başkanı.
'{topic}' konusundaki mahkeme oturumunun tüm tutanakları önünde.

TUTANAKLAR:
[{roles[0]}]: {r1[:1500]}
[{roles[1]}]: {r2[:1500]}
[{roles[0]} Savunma]: {r3[:1500]}
[{roles[2]} Hakem]: {r4[:1500]}

GÖREV: Bu tartışmanın kapsamlı sentezini oluştur.

YANIT FORMATI (Türkçe):
1. TARTIŞMANIN ÖZETİ: Ne tartışıldı, temel anlaşmazlık noktası neydi?
2. GÜÇLÜ YÖNLER: Her tarafın haklı olduğu noktalar
3. ZAYIF YÖNLER: Tartışmada kalan boşluklar ve cevaplanmamış sorular
4. ÖN SONUÇ: Mevcut kanıtlara göre hangi pozisyon daha güçlü görünüyor?
5. AÇIK SORULAR: Nihai karardan önce netleşmesi gereken meseleler

Akademik, tarafsız ve kapsamlı yaz. Türkçe.""",
                agent=president,
                expected_output="Kapsamlı tartışma sentezi. Türkçe. 500-700 kelime."
            ))
            q.put({"type": "step_complete", "step": 5, "content": sentez, "heat": heat_score(sentez)})

            # ── OTURUM 6 ──────────────────────────────────────
            q.put({"type": "step_start", "step": 6, "title": f"Yüksek Güvenlik Konseyi — {flow_label(5)}"})

            # Her kurul üyesi gerçekten çalışıyor — sırayla review zinciri
            q.put({"type": "log", "message": "Mantık Analisti inceliyor..."})
            r_mantik = run_crew([council[0]], Task(
                description=f"""SEN KİMSİN: Mantık Analisti. Yüksek Güvenlik Konseyi üyesisin.
KONU: '{topic}'

KURUL BAŞKANININ SENTEZİ:
{sentez}

GÖREV: Bu sentezdeki mantıksal çelişkileri, argümantasyon hatalarını ve geçersiz çıkarımları tespit et.
- Hangi argümanlar tutarsız ya da döngüsel?
- Hangi sonuçlar öncüllerden gelmiyor?
- Genel argümentasyon kalitesi nasıl?

3-5 madde halinde, Türkçe, kısa ve net yaz.""",
                agent=council[0],
                expected_output="Mantıksal analiz raporu. Türkçe. 150-250 kelime."
            ))

            q.put({"type": "log", "message": "Veri Doğrulama Denetçisi inceliyor..."})
            r_veri = run_crew([council[1]], Task(
                description=f"""SEN KİMSİN: Veri Doğrulama Denetçisi. Yüksek Güvenlik Konseyi üyesisin.
KONU: '{topic}'

KURUL BAŞKANININ SENTEZİ:
{sentez}

MANTIK ANALİSTİNİN BULGULARI:
{r_mantik}

GÖREV: Desteksiz iddiaları, halüsinasyon risklerini ve kanıtsız yargıları tespit et.
- Hangi iddialar somut veriye dayanmıyor?
- Hangi istatistik veya kaynak doğrulanamaz görünüyor?
- Veri kalitesi açısından karar güvenilir mi?

3-5 madde halinde, Türkçe yaz.""",
                agent=council[1],
                expected_output="Veri doğrulama raporu. Türkçe. 150-250 kelime."
            ))

            q.put({"type": "log", "message": "Karşıt Argüman Uzmanı test ediyor..."})
            r_karsit = run_crew([council[2]], Task(
                description=f"""SEN KİMSİN: Karşıt Argüman Uzmanı. Yüksek Güvenlik Konseyi üyesisin.
KONU: '{topic}'

KURUL BAŞKANININ SENTEZİ:
{sentez}

GÖREV: Sentezin tam tersini savunan en güçlü 2-3 argümanı sun. Hangi varsayımlar test edilmedi?
Amaç çürütmek değil, kararın dayanıklılığını sınamak.

Türkçe, kısa ve net yaz.""",
                agent=council[2],
                expected_output="Karşıt senaryo analizi. Türkçe. 150-250 kelime."
            ))

            q.put({"type": "log", "message": "Etik Denetmen değerlendiriyor..."})
            r_etik = run_crew([council[3]], Task(
                description=f"""SEN KİMSİN: Etik Denetmen. Yüksek Güvenlik Konseyi üyesisin.
KONU: '{topic}'

KURUL BAŞKANININ SENTEZİ:
{sentez}

GÖREV: Kararın toplumsal ve ahlaki uygunluğunu değerlendir.
- Hangi gruplar veya değerler göz ardı edildi?
- Olası olumsuz yan etkiler neler?
- Karar etik açıdan savunulabilir mi?

3-5 madde halinde, Türkçe yaz.""",
                agent=council[3],
                expected_output="Etik değerlendirme raporu. Türkçe. 150-250 kelime."
            ))

            q.put({"type": "log", "message": "Nihai Karar Mercii kararı mühürlüyor..."})
            # Şablona göre karar formatı (Bug 8 fix)
            default_verdict = "DAVA NO: AVR-{date}\nKONU: {topic}\n\n§1. KARAR\n§2. GEREKÇE\n§3. SONUÇ"
            verdict_fmt = template_data.get("verdict_format", default_verdict)
            verdict_fmt = verdict_fmt.replace("{date}", datetime.now().strftime('%Y%m%d'))
            verdict_fmt = verdict_fmt.replace("{topic}", topic)
            verdict_fmt = verdict_fmt.replace("{role1}", roles[0])
            verdict_fmt = verdict_fmt.replace("{role2}", roles[1])

            muhurlu = run_crew([council[4]], Task(
                description=f"""SEN KİMSİN: Nihai Karar Mercii — Yüksek Güvenlik Konseyi Başkanı.
'{topic}' davası tamamlandı. Konsey üyelerinin değerlendirmeleri:

[Mantık Analisti]:
{r_mantik}

[Veri Doğrulama Denetçisi]:
{r_veri}

[Karşıt Argüman Uzmanı]:
{r_karsit}

[Etik Denetmen]:
{r_etik}

[Kurul Başkanı Sentezi]:
{sentez}

GÖREV: Tüm bu değerlendirmeleri göz önünde tutarak mühürlü nihai kararı ver.

KARAR FORMATI (Türkçe):

{verdict_fmt}

KARAR MÜHÜRLENMİŞTİR. Türkçe. Kesin ve net.""",
                agent=council[4],
                expected_output="Resmi mühürlü nihai mahkeme kararı. Türkçe. 500-800 kelime."
            ))
            # Sentezin yalnızca "ÖN SONUÇ" bölümünü çıkar (panel 4 özet kartı için)
            # Tam metin zaten timeline step 5'te görünüyor
            synthesis_short = None
            sentez_lower = sentez.lower()
            for marker in ["4. ön sonuç", "ön sonuç:", "**4.", "4.ön sonuç", "ön sonuç\n"]:
                idx = sentez_lower.find(marker)
                if idx != -1:
                    chunk = sentez[idx:]          # orijinal metni kullan (büyük/küçük harf korunur)
                    chunk_lower = chunk.lower()
                    end = len(chunk)
                    for next_marker in ["**5.", "5. açık", "açık sorular", "§"]:
                        ni = chunk_lower.find(next_marker, len(marker))
                        if ni != -1:
                            end = min(end, ni)
                    synthesis_short = chunk[:end].strip()
                    break
            if not synthesis_short:
                # ÖN SONUÇ bulunamazsa ilk 350 karakteri al
                synthesis_short = (sentez[:350].rsplit(' ', 1)[0] + '…') if len(sentez) > 350 else sentez

            q.put({"type": "final_verdict", "content": muhurlu, "synthesis": synthesis_short})

            # ── Full debate saved to memory (append, üzerine yazma) ─────────
            try:
                with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                    history = json.load(f)
                if not isinstance(history, list):
                    history = [history]   # eski format: tek obje → listeye çevir
            except (FileNotFoundError, json.JSONDecodeError):
                history = []
            # Şablona göre dinamik alan isimleri
            flow = template_data.get("flow", ["tez", "itiraz", "savunma", "hakem", "sentez", "nihai_karar"])
            session_record = {
                "tarih": str(datetime.now()),
                "konu": topic,
                "sablon": req.template,
                "sablon_adi": mode_label,
            }
            step_data = [
                (roles[0], r1),
                (roles[1], r2),
                (f"{roles[0]} (Savunma)", r3),
                (f"{roles[2]} (Hakem)", r4),
            ]
            for i, (role, content) in enumerate(step_data):
                label = flow[i] if i < len(flow) else f"adim_{i+1}"
                session_record[f"{label}__{role}"] = content
            session_record["sentez"] = sentez
            session_record["muhurlu_karar"] = muhurlu
            history.append(session_record)
            with open(MEMORY_PATH, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4, ensure_ascii=False)

        except Exception as e:
            import traceback
            q.put({"type": "error", "message": str(e), "traceback": traceback.format_exc()})
        finally:
            q.put(None)
            # Client hiç bağlanmazsa session sızdırmasın — 2 saat sonra temizle
            threading.Timer(7200, lambda: debate_sessions.pop(session_id, None)).start()

    threading.Thread(target=run_debate, daemon=True).start()
    return {"session_id": session_id}


@app.get("/api/debate-stream/{session_id}")
async def debate_stream(session_id: str):
    if session_id not in debate_sessions:
        raise HTTPException(status_code=404, detail="Session bulunamadı.")

    q = debate_sessions[session_id]

    async def generate():
        try:
            while True:
                try:
                    item = q.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.2)
                    continue

                if item is None:
                    yield 'data: {"type":"done"}\n\n'
                    break

                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            debate_sessions.pop(session_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=False)
