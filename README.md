# ⚖️ Avaria Multi-Agent Framework

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-SSE_Streaming-009688?style=for-the-badge&logo=fastapi)
![CrewAI](https://img.shields.io/badge/CrewAI-Multi_Agent-orange?style=for-the-badge)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLMs-black?style=for-the-badge)

🌍 **[English](#english)** | 🇹🇷 **[Türkçe](#türkçe)**

---

<a id="english"></a>
## 🌍 English

### What is Avaria?

Avaria is a **local multi-agent debate framework** powered by CrewAI and Ollama. You give it any research topic and it assembles a full courtroom: three expert agents debate each other across 6 structured rounds, a synthesizer summarizes the arguments, and a 5-member High Security Council delivers a sealed final verdict — all running on your local machine, no API keys required.

### 🏛️ How It Works

| Round | Agent | Role |
|-------|-------|------|
| 1 | Expert 1 | Opening thesis with web research |
| 2 | Expert 2 | Rebuttal & counter-thesis |
| 3 | Expert 1 | Defense & cross-examination |
| 4 | Expert 3 (Referee) | Independent analysis |
| 5 | Synthesizer | Comprehensive synthesis |
| 6 | High Security Council (5 agents) | Sealed final verdict |

- **Real-time web search**: DuckDuckGo results are injected into each round's prompt
- **Live streaming**: Results stream in real-time via Server-Sent Events (SSE)
- **Auto expert generation**: AI generates 3 domain experts from your topic automatically
- **Devil's Advocate mode**: Force Expert 2 to always argue the opposing side
- **Argument map**: Visual SVG graph of the debate structure
- **Export**: Download the full debate as Markdown

### ⚙️ Recommended Hardware

Tested on **RTX 5070 Ti + AMD 7800X3D** with `gemma2:27b` for experts. 

- **Minimum recommended**: 27B parameter model for coherent arguments
- **Lower-end devices**: 7B/13B models work but argument quality drops significantly
- You can mix models — lighter model for the council, heavier for experts

### 🚀 Installation

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install & start Ollama**, then pull a model
   ```bash
   ollama pull gemma2:27b
   ```

3. **Run the server**
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8080
   ```

4. **Open your browser** → `http://localhost:8080`

### 📁 Project Structure

```
avaria-framework/
├── server.py          # FastAPI backend, debate orchestration, SSE streaming
├── agents/
│   ├── debaters.py    # Expert agent factory
│   └── judge.py       # Synthesizer + 5-member Security Council
├── services/
│   └── llm_client.py  # Ollama LLM client
├── utils/
│   └── stateless_loop.py  # Robust JSON parser
└── static/
    ├── index.html     # Single-page app
    ├── app.js         # Frontend logic, SSE consumer
    └── style.css      # Woody/creamy UI theme
```

### 🤝 Contributing

Fork, modify, distribute freely. PRs welcome — especially for:
- Improved prompting strategies
- New agent personality types
- Better argument visualization
- Multi-language support

---

<a id="türkçe"></a>
## 🇹🇷 Türkçe

### Avaria Nedir?

Avaria, CrewAI ve Ollama üzerine kurulu **yerel çok ajanlı tartışma çerçevesidir**. Herhangi bir araştırma konusu verin — sistem otomatik olarak 3 uzman ajan oluşturur, 6 turlu yapılandırılmış bir mahkeme tartışması yürütür ve 5 üyeli Yüksek Güvenlik Konseyi mühürlü nihai kararı verir. API anahtarı gerekmez, her şey yerel çalışır.

### 🏛️ Tartışma Yapısı

| Tur | Ajan | Görev |
|-----|------|-------|
| 1 | Uzman 1 | Web araştırmalı açılış tezi |
| 2 | Uzman 2 | İtiraz ve karşı tez |
| 3 | Uzman 1 | Savunma ve çapraz sorgu |
| 4 | Uzman 3 (Hakem) | Bağımsız analiz |
| 5 | Sentezleyici | Kapsamlı sentez |
| 6 | Yüksek Güvenlik Konseyi (5 ajan) | Mühürlü nihai karar |

- **Gerçek zamanlı web araması**: Her turda DuckDuckGo sonuçları prompt'a enjekte edilir
- **Canlı akış**: Sonuçlar SSE (Server-Sent Events) ile gerçek zamanlı akar
- **Otomatik uzman üretimi**: Konudan 3 alan uzmanı otomatik oluşturulur
- **Şeytan'ın Avukatı modu**: Uzman 2'yi her zaman karşı pozisyonu savunmaya zorlar
- **Argüman haritası**: Tartışma yapısının görsel SVG grafiği
- **Dışa aktarma**: Tartışmayı Markdown olarak indirin

### ⚙️ Önerilen Donanım

**RTX 5070 Ti + AMD 7800X3D** üzerinde `gemma2:27b` ile test edildi.

- **Önerilen minimum**: Tutarlı argümanlar için 27B parametre model
- **Düşük donanım**: 7B/13B modeller çalışır ama argüman kalitesi düşer
- Modelleri karıştırabilirsiniz — konsey için hafif, uzmanlar için ağır model

### 🚀 Kurulum

1. **Bağımlılıkları yükleyin**
   ```bash
   pip install -r requirements.txt
   ```

2. **Ollama'yı kurun ve model indirin**
   ```bash
   ollama pull gemma2:27b
   ```

3. **Sunucuyu başlatın**
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8080
   ```

4. **Tarayıcıda açın** → `http://localhost:8080`

### 🤝 Katkı

Forklayın, değiştirin, dağıtın — tamamen serbesttir. PR'lar memnuniyetle karşılanır.
