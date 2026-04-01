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
from agents.debaters import create_expert_agent
from agents.judge import create_judge_agent, create_security_council
from crewai import Task, Crew

app = FastAPI(title="Avaria Multi-Agent Framework")


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


class ExpertRequest(BaseModel):
    model: str
    topic: str


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


@app.get("/api/models")
def get_models():
    models = get_ollama_models()
    if not models:
        raise HTTPException(status_code=503, detail="Ollama servisine ulaşılamadı.")
    return {"models": models}


@app.post("/api/generate-experts")
def generate_experts(req: ExpertRequest):
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
            "http://localhost:11434/api/generate",
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

            q.put({"type": "log", "message": "Mahkeme oturumu başlatılıyor..."})

            llm1 = create_llm(configs[0].model)
            llm2 = create_llm(configs[1].model)
            llm3 = create_llm(configs[2].model)
            llm_p = create_llm(req.president_model, temp=0.1)
            llm_c = create_llm(req.court_model, temp=0.0)

            agent1 = create_expert_agent(configs[0].data, llm1, configs[0].personality)
            agent2 = create_expert_agent(configs[1].data, llm2, configs[1].personality)
            agent3 = create_expert_agent(configs[2].data, llm3, configs[2].personality)
            president = create_judge_agent(llm_p)
            council = create_security_council(llm_c)

            # ── OTURUM 1: Açılış Tezi ──────────────────────────────────────
            q.put({"type": "step_start", "step": 1, "title": f"{roles[0]} — Açılış Tezi"})
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

            # ── OTURUM 2: İtiraz ve Karşı Tez ──────────────────────────────
            q.put({"type": "step_start", "step": 2, "title": f"{roles[1]} — İtiraz & Karşı Tez"})
            q.put({"type": "log", "message": "Karşı argüman için araştırma yapılıyor..."})
            q2 = f"{search_base} criticism counterargument problems 2024"
            arastirma2 = web_search(q2, topic_keywords=q2.split())
            devil_prefix = ""
            if req.devil_advocate:
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

            # ── OTURUM 3: Savunma ve Çapraz Sorgu ──────────────────────────
            q.put({"type": "step_start", "step": 3, "title": f"{roles[0]} — Savunma & Çapraz Sorgu"})
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

            # ── OTURUM 4: Bağımsız Hakem Değerlendirmesi ───────────────────
            q.put({"type": "step_start", "step": 4, "title": f"{roles[2]} — Bağımsız Hakem Analizi"})
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

            # ── OTURUM 5: Kurul Başkanı Sentezi ────────────────────────────
            q.put({"type": "step_start", "step": 5, "title": "Kurul Başkanı — Kapsamlı Sentez"})
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

            # ── OTURUM 6: Yüksek Mahkeme Nihai Kararı ──────────────────────
            q.put({"type": "step_start", "step": 6, "title": "Yüksek Güvenlik Konseyi — Mühürlü Nihai Karar"})

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

KARAR FORMATI (Türkçe, resmi mahkeme üslubu):

DAVA NO: AVR-{datetime.now().strftime('%Y%m%d')}
KONU: {topic}

§1. KARAR: [Açık bir sonuç belirt]
§2. GEREKÇE: [Hangi argümanlar belirleyiciydi, konsey bulgularına atıfla]
§3. HANGİ TARAF DAHA GÜÇLÜYDÜ: [{roles[0]} mi {roles[1]} mi ve neden]
§4. KABUL EDİLEN İDDİALAR: [Tartışmasız doğru kabul edilen noktalar]
§5. REDDEDİLEN İDDİALAR: [Kanıtsız veya çürütülmüş iddialar]
§6. TOPLUMSAL ÖNERİ: [Politika, bilim veya topluma öneri]
§7. AZINLIK GÖRÜŞÜ: [ZORUNLU — Tartışmada karşı tarafın en güçlü argümanını temel alarak azınlık görüşü yaz. 'Yok' yazamazsın.]

KARAR MÜHÜRLENMİŞTİR. Türkçe. Resmi ve kesin.""",
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
            memory_path = "avaria_memory.json"
            try:
                with open(memory_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
                if not isinstance(history, list):
                    history = [history]   # eski format: tek obje → listeye çevir
            except (FileNotFoundError, json.JSONDecodeError):
                history = []
            history.append({
                "tarih": str(datetime.now()),
                "konu": topic,
                "agent_1_tez": r1,
                "agent_2_itiraz": r2,
                "agent_1_savunma": r3,
                "agent_3_hakem": r4,
                "sentez": sentez,
                "muhurlu_karar": muhurlu
            })
            with open(memory_path, "w", encoding="utf-8") as f:
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
