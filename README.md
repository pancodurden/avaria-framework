# ⚖️ Avaria Multi-Agent Framework

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-Liquid_Glass-FF4B4B?style=for-the-badge&logo=streamlit)
![CrewAI](https://img.shields.io/badge/CrewAI-AI_Committee-orange?style=for-the-badge)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLMs-black?style=for-the-badge)

🌍 **[English](#english)** | 🇹🇷 **[Türkçe](#türkçe)**

---

<a id="english"></a>
## 🌍 English

### What is Avaria?
Avaria is a **CrewAI-based AI Agent Committee** framework. It creates a dynamic courtroom/debate environment where multiple local AI experts debate a given topic, critique each other, and synthesize a final verdict. 

### ⚙️ Hardware & Dynamic Model Selection
To improve the user experience and hardware flexibility, I implemented a **Dynamic Model Selection** feature. You don't need a supercomputer to run this!
* **Hardware Flexibility:** I personally ran and tested this project on my setup (RTX 5070 Ti & AMD 7800X3D) using heavier models like `gemma2:27b` for the experts and `llama3.1:8b` for the Architect. 
* **Ollama Integration:** If you have a lower-end or higher-end device, you can easily change the models. As long as you download a model via **Ollama**, Avaria will automatically detect it and show it in the dropdown menus!

### 🚀 Installation & Usage
1. **Install Requirements:** You need to install the necessary libraries to run the UI and the framework.
   ```bash
   pip install streamlit requests crewai
   ```
2. **Setup Ollama:** Make sure [Ollama](https://ollama.ai/) is installed and running on your machine. Pull the models you want to use:
   ```bash
   ollama pull llama3.1:latest
   ollama pull gemma2:27b
   ```
3. **Run the App:**
   ```bash
   streamlit run app.py
   ```

### 🤝 Open Source & Contributing
I give full permission for anyone to fork, modify, change, and distribute this project. I want to see this community grow! 

*A quick note:* I did my best with the UI, but I am not exactly a frontend wizard. If you want to touch up the UI and make it look even better, feel free to lend a hand! :)

---

<a id="türkçe"></a>
## 🇹🇷 Türkçe

### Avaria Nedir?
Avaria, **CrewAI tabanlı bir Yapay Zeka Ajan Komitesi** (AI Agent Committee) projesidir. Verdiğiniz herhangi bir konuyu, farklı disiplinlerden gelen yerel yapay zeka uzmanlarının birbirleriyle tartıştığı, birbirlerini eleştirdiği ve Ana Karar Verici'nin (Başkan) nihai bir sonuca bağladığı dinamik bir mahkeme/kurul ortamı yaratır.

### ⚙️ Donanım ve Dinamik Model Seçimi
Proje üzerindeki kullanım deneyimini iyileştirmek için sisteme **Dinamik Model Seçme** özelliği sundum. 
* **Donanım Esnekliği:** Ben bu projeyi geliştirirken kendi cihazımda (RTX 5070 Ti ekran kartı ve AMD 7800X3D işlemci) uzmanlar için `gemma2:27b`, mimar model için `llama3.1:8b` gibi ağır modeller kullandım. 
* **Ollama Entegrasyonu:** Ancak daha kötü veya çok daha iyi bir cihaza sahip olabilirsiniz! Sadece sisteminize uygun modelleri **Ollama** üzerinden indirmeniz yeterli. Uygulama, indirdiğiniz tüm modelleri otomatik olarak algılar ve arayüzden seçmenize olanak tanır.

###  Kurulum ve Kullanım
1. **Kütüphaneleri İndirin:** Arayüz ve yapay zeka altyapısı için gerekli kütüphaneleri kurun.
   ```bash
   pip install streamlit requests crewai
   ```
2. **Ollama'yı Hazırlayın:** Bilgisayarınızda [Ollama](https://ollama.ai/)'nın kurulu ve açık olduğundan emin olun. Kullanmak istediğiniz modelleri indirin:
   ```bash
   ollama pull llama3.1:latest
   ollama pull gemma2:27b
   ```
3. **Uygulamayı Başlatın:**
   ```bash
   streamlit run app.py
   ```

### 🤝 Açık Kaynak ve Topluluk Katkısı
Bu projenin isteyen herkes tarafından değiştirilmesine, modifiye edilmesine ve topluluğun geliştirmesine sonuna kadar izin veriyorum. İstediğiniz gibi çatallayabilir (fork) ve kullanabilirsiniz!

*Küçük bir note:* UI (Arayüz) tarafını pek yapamadım, elimden bu kadarı geldi. İsteyen ve anlayan arkadaşlar frontend/UI tarafına el atabilir, PR (Pull Request) gönderebilirsiniz! :)