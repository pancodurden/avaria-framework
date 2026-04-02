# Avaria Multi-Agent Framework

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-SSE_Streaming-009688?style=for-the-badge&logo=fastapi)
![CrewAI](https://img.shields.io/badge/CrewAI-Multi_Agent-orange?style=for-the-badge)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLMs-black?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker)

**[English](#english)** | **[Turkce](#türkçe)**

---

<a id="english"></a>
## English

### What is Avaria?

Avaria is a **local multi-agent debate and research framework** powered by CrewAI and Ollama. Give it any topic — it assembles an expert team, runs a structured multi-round debate with live web research, and delivers a sealed verdict. Everything runs locally, no API keys required.

### v3.0 — What's New

- **Smart Hardware Analyzer** — Auto-detects GPU/RAM and recommends optimal models
- **Template System** — 4 built-in debate modes + create your own or import from GitHub
- **Agentic Tool Use** — Agents can execute Python code, read/write files, run terminal commands (sandbox)
- **Code Feedback Loop** — If agent-generated code fails, it auto-retries up to 3 times
- **Intent Analysis** — AI analyzes your topic and suggests the best debate template
- **Session History** — All debates saved, browseable, exportable as Markdown
- **Plugin Ecosystem** — Create templates via UI, import from GitHub raw URL, delete
- **Docker Support** — One-command deploy with `docker-compose up`

### Debate Templates

| Template | Description | Agents |
|----------|-------------|--------|
| Akademik Mahkeme | Courtroom-style thesis vs antithesis debate | Advocate, Opponent, Referee |
| Yazilim Ekibi | Software dev team with tool use enabled | PM/Architect, Senior Dev, QA |
| Arastirma Paneli | Academic research panel | Researcher, Methodologist, Interdisciplinary Analyst |
| Ogretmen-Ogrenci | Teacher-student simulation | Teacher, Curious Student, Advanced Student |
| + Custom | Create your own or import from GitHub | You decide |

### How It Works

```
Topic Input --> Intent Analysis --> Template Selection --> Expert Generation
     |                                                          |
     v                                                          v
Web Research -----> 6-Round Structured Debate -----> Synthesis
                          |                              |
                    [Live SSE Stream]              5-Member Council
                          |                              |
                          v                              v
                   Real-time UI  <------- Sealed Final Verdict
```

| Round | Role |
|-------|------|
| 1 | Opening thesis with web research |
| 2 | Rebuttal & counter-thesis |
| 3 | Defense & cross-examination |
| 4 | Independent referee analysis |
| 5 | Comprehensive synthesis |
| 6 | 5-member High Security Council sealed verdict |

### Recommended Hardware

Tested on **RTX 5070 Ti (16GB VRAM) + AMD 7800X3D + 32GB RAM** with `gemma2:27b`.

| VRAM | Recommended Models |
|------|--------------------|
| < 6 GB | llama3.2:3b, qwen2.5:3b |
| 6-10 GB | llama3.1:8b, mistral:7b |
| 10-16 GB | llama3.1:8b, gemma2:9b |
| 16+ GB | gemma2:27b, mixtral:8x7b |

The hardware analyzer auto-detects your setup and shows recommendations in the UI.

### Installation

**Option 1 — Local**

```bash
# 1. Clone
git clone https://github.com/pancodurden/avaria-framework.git
cd avaria-framework

# 2. Create venv & install
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt

# 3. Install Ollama & pull a model
ollama pull gemma2:27b

# 4. Run
python server.py
```

Open `http://localhost:8080`

**Option 2 — Docker**

```bash
docker-compose up --build
```

This starts both Ollama and Avaria. Access at `http://localhost:8080`.

### Creating Custom Templates

**From UI:**
1. Click "Sablon Olustur" in the sidebar
2. Fill in name, roles, keywords
3. Save — it's immediately available

**From GitHub:**
1. Create a JSON template file (see `agents/templates/` for examples)
2. Push to any public GitHub repo
3. Get the **Raw URL** of the JSON file
4. In Avaria UI: Sablon Olustur --> paste Raw URL --> Import

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/models` | List available Ollama models |
| GET | `/api/hardware` | GPU/RAM info & model recommendations |
| GET | `/api/templates` | List all debate templates |
| POST | `/api/analyze-intent` | Analyze topic & suggest template |
| POST | `/api/generate-experts` | Generate expert profiles for topic |
| POST | `/api/start-debate` | Start a debate session |
| GET | `/api/debate-stream/{id}` | SSE stream for debate events |
| GET | `/api/history` | List past sessions |
| GET | `/api/history/{id}` | Get session detail |
| GET | `/api/export/{id}` | Export session as Markdown |
| POST | `/api/templates/create` | Create custom template |
| POST | `/api/templates/import` | Import template from URL |
| DELETE | `/api/templates/{name}` | Delete community template |
| GET | `/api/sandbox/files` | List sandbox files |
| GET | `/api/sandbox/download/{file}` | Download sandbox file |

### Project Structure

```
avaria-framework/
├── server.py                  # FastAPI backend, 15+ endpoints, SSE streaming
├── Dockerfile                 # Docker image
├── docker-compose.yml         # Ollama + Avaria services
├── requirements.txt           # Pinned dependencies
├── agents/
│   ├── debaters.py            # Expert agent factory (with tool support)
│   ├── judge.py               # Synthesizer + 5-member Security Council
│   ├── templates/             # Built-in debate templates (JSON)
│   │   ├── mahkeme.json
│   │   ├── yazilim_ekibi.json
│   │   ├── arastirma_paneli.json
│   │   └── ogretmen_ogrenci.json
│   └── community_templates/   # User-created & imported templates
├── services/
│   └── llm_client.py          # Ollama LLM client (centralized OLLAMA_HOST)
├── utils/
│   ├── hardware_analyzer.py   # GPU/RAM detection & model recommendations
│   ├── intent_analyzer.py     # Topic-to-template matching (keyword + LLM)
│   ├── tools.py               # Sandboxed agentic tools (code exec, file I/O, terminal)
│   └── stateless_loop.py      # Robust JSON parser
└── static/
    ├── index.html             # Single-page app
    ├── app.js                 # Frontend logic, SSE consumer
    └── style.css              # Woody/creamy UI theme
```

### Contributing

Fork, modify, distribute freely under MIT license. PRs welcome — especially for:
- New debate templates
- Improved prompting strategies
- Multi-language support
- Better argument visualization

---

<a id="türkçe"></a>
## Turkce

### Avaria Nedir?

Avaria, CrewAI ve Ollama uzerine kurulu **yerel cok ajanli tartisma ve arastirma cercevesidir**. Herhangi bir konu verin — sistem otomatik olarak uzman ekip olusturur, canli web arastirmali yapilandirilmis tartisma yurutur ve muhurlu nihai karar verir. API anahtari gerekmez, her sey yerel calisir.

### v3.0 — Yenilikler

- **Akilli Donanim Analizoru** — GPU/RAM otomatik tespit, uygun model onerisi
- **Sablon Sistemi** — 4 hazir tartisma modu + kendi sablonunu olustur veya GitHub'dan import et
- **Agentic Tool Use** — Ajanlar Python kodu calistirabilir, dosya okuyup yazabilir, terminal komutu calistirabilir
- **Kod Geri Bildirim Dongusu** — Ajan kodu hata verirse otomatik 3 denemeye kadar duzeltir
- **Niyet Analizi** — Konunuzu analiz edip en uygun tartisma sablonunu onerir
- **Oturum Gecmisi** — Tum tartismalar kaydedilir, goruntulenebilir, Markdown olarak export edilir
- **Plugin Ekosistemi** — UI'dan sablon olustur, GitHub raw URL'den import et, sil
- **Docker Destegi** — `docker-compose up` ile tek komutla deploy

### Tartisma Sablonlari

| Sablon | Aciklama | Ajanlar |
|--------|----------|---------|
| Akademik Mahkeme | Tez vs antitez mahkeme tartismasi | Savunucu, Muhalif, Hakem |
| Yazilim Ekibi | Tool kullanan yazilim gelistirme ekibi | PM/Mimar, Senior Dev, QA |
| Arastirma Paneli | Akademik arastirma paneli | Arastirmaci, Metodolog, Disiplinlerarasi Analist |
| Ogretmen-Ogrenci | Ogretmen-ogrenci simulasyonu | Ogretmen, Merakli Ogrenci, Ileri Ogrenci |
| + Ozel | Kendin olustur veya GitHub'dan import et | Sen karar ver |

### Nasil Calisir

| Tur | Gorev |
|-----|-------|
| 1 | Web arastirmali acilis tezi |
| 2 | Itiraz ve karsi tez |
| 3 | Savunma ve capraz sorgu |
| 4 | Bagimsiz hakem analizi |
| 5 | Kapsamli sentez |
| 6 | 5 uyeli Yuksek Guvenlik Konseyi muhurlu nihai karar |

### Onerilen Donanim

**RTX 5070 Ti (16GB VRAM) + AMD 7800X3D + 32GB RAM** uzerinde `gemma2:27b` ile test edildi.

| VRAM | Onerilen Modeller |
|------|-------------------|
| < 6 GB | llama3.2:3b, qwen2.5:3b |
| 6-10 GB | llama3.1:8b, mistral:7b |
| 10-16 GB | llama3.1:8b, gemma2:9b |
| 16+ GB | gemma2:27b, mixtral:8x7b |

Donanim analizoru kurulumunuzu otomatik tespit edip UI'da onerileri gosterir.

### Kurulum

**Yontem 1 — Yerel**

```bash
# 1. Klonla
git clone https://github.com/pancodurden/avaria-framework.git
cd avaria-framework

# 2. Venv olustur & kur
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt

# 3. Ollama kur & model indir
ollama pull gemma2:27b

# 4. Calistir
python server.py
```

Tarayicida ac: `http://localhost:8080`

**Yontem 2 — Docker**

```bash
docker-compose up --build
```

Ollama ve Avaria birlikte baslar. `http://localhost:8080` adresinden erisin.

### Ozel Sablon Olusturma

**UI'dan:**
1. Kenar cubugunda "Sablon Olustur"a tikla
2. Ad, roller, anahtar kelimeler doldur
3. Kaydet — aninda kullanilabilir

**GitHub'dan:**
1. JSON sablon dosyasi olustur (`agents/templates/` icindeki orneklere bak)
2. Herhangi bir public GitHub reposuna push et
3. JSON dosyasinin **Raw URL**'sini al
4. Avaria UI'da: Sablon Olustur --> Raw URL yapistir --> Import

### Katki

MIT lisansi altinda forklayip dagitabilirsiniz. PR'lar memnuniyetle karsilanir.
