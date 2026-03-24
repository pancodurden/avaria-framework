import streamlit as st
import requests
import json
import os
import sys
import re
import traceback

# --- FRAMEWORK IMPORTS ---
from crewai import Agent, Task, Crew, LLM

# --- ENVIRONMENT CONFIGURATION ---
# Bypass external API key requirement for local Ollama execution
os.environ["OPENAI_API_KEY"] = "NA"

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Avaria Multi-Agent Framework", layout="wide")


st.markdown("""
<style>
    /* Tatlı Pembe/Mor Gradient Arka Plan */
    .stApp {
        background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 99%, #fecfef 100%) !important;
        background-attachment: fixed !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    /* Tüm Yazı Renkleri (Pembe arka planda okunaklı olması için koyu gri/lacivert) */
    h1, h2, h3, h4, h5, h6, p, label, span {
        color: #2d3436 !important;
        font-weight: 500;
    }
    
    /* Ana Başlık Özel Efekt */
    h2 {
        text-align: center;
        background: -webkit-linear-gradient(45deg, #ff0844 0%, #ffb199 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }

    /* LİQUİD GLASS (Cam Efekti) KUTULAR: Input, Selectbox, Alert ve Containerlar */
    div[data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlock"],
    div[data-testid="stAlert"], 
    .stTextInput > div > div > input, 
    .stSelectbox > div > div > div {
        background: rgba(255, 255, 255, 0.35) !important; /* Yarı saydam beyaz */
        backdrop-filter: blur(12px) !important; /* Buzlu cam efekti */
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.6) !important; /* Parlak cam kenarlığı */
        border-radius: 20px !important; /* Yuvarlak köşeler */
        box-shadow: 0 8px 32px 0 rgba(255, 117, 140, 0.15) !important; /* Hafif pembe gölge */
        color: #2d3436 !important;
        transition: all 0.3s ease;
    }
    
    /* Input ve Selectbox'a tıklayınca parlaması */
    .stTextInput > div > div > input:focus, 
    .stSelectbox > div > div > div:focus {
        background: rgba(255, 255, 255, 0.5) !important;
        border: 1px solid #ff758c !important;
        box-shadow: 0 0 15px rgba(255, 117, 140, 0.4) !important;
    }

    /* Buton Tasarımı (Canlı Pembe Gradient) */
    div.stButton > button {
        background: linear-gradient(135deg, #ff758c 0%, #ff7eb3 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 25px !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        box-shadow: 0 8px 15px rgba(255, 117, 140, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    
    div.stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 12px 20px rgba(255, 117, 140, 0.5) !important;
        background: linear-gradient(135deg, #ff7eb3 0%, #ff758c 100%) !important;
    }

    /* Selectbox içindeki açılır menü yazıları */
    ul[data-testid="stSelectboxVirtualDropdown"] li {
        color: #2d3436 !important;
    }

    /* Üstteki gereksiz Streamlit çizgisini gizleme */
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

def get_ollama_models():
    """Fetches available local models from the Ollama API."""
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        return [model['name'] for model in response.json()['models']]
    except requests.exceptions.RequestException: 
        return []

def robust_parse_json(raw_text):
    """
    A robust JSON parser designed to handle unpredictable outputs from local LLMs.
    Extracts the expert list regardless of surrounding markdown or structural anomalies.
    """
    text = re.sub(r'```json\s*', '', raw_text)
    text = re.sub(r'```', '', text)
    try:
        data = json.loads(text)
        expert_list = []
        
        # Traverse nested dictionaries if the model wrapped the array
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    data = value
                    break
            if isinstance(data, dict):
                data = [data]
                
        # Map varying key names to standard formats
        for item in data:
            if not isinstance(item, dict): 
                continue
            role = next((v for k, v in item.items() if k.lower() in ["role", "rol", "unvan", "title"]), "Uzman")
            goal = next((v for k, v in item.items() if k.lower() in ["goal", "amac", "hedef", "purpose"]), "Analiz")
            backstory = next((v for k, v in item.items() if k.lower() in ["backstory", "gecmis", "background"]), "Akademisyen")
            expert_list.append({"role": role, "goal": goal, "backstory": backstory})
            
        return expert_list
    except json.JSONDecodeError:
        # Fallback: Regex extraction for severely malformed JSON
        roles = re.findall(r'"(?:role|rol|unvan|title)"\s*:\s*"([^"]+)"', text, re.I)
        goals = re.findall(r'"(?:goal|amac|hedef|purpose)"\s*:\s*"([^"]+)"', text, re.I)
        backs = re.findall(r'"(?:backstory|gecmis|background)"\s*:\s*"([^"]+)"', text, re.I)
        return [{"role": r, "goal": g, "backstory": b} for r, g, b in zip(roles, goals, backs)]

def safe_output(task_obj):
    """Safely extracts task output to prevent UI crashes if generation fails."""
    if hasattr(task_obj, 'output') and task_obj.output is not None:
        return getattr(task_obj.output, 'raw', str(task_obj.output))
    return "Sistem uyarısı: Bu aşamada model geçerli bir yanıt üretemedi."

# --- SESSION STATE INITIALIZATION ---
if "agent_list" not in st.session_state:
    st.session_state.agent_list = []

# ==========================================
# USER INTERFACE
# ==========================================
st.markdown("<h2>Avaria Dynamic Multi-Agent Framework</h2>", unsafe_allow_html=True)
st.markdown("---")

available_models = get_ollama_models()

if not available_models:
    st.error("Ollama servisine ulaşılamadı. Lütfen yerel sunucunun (localhost:11434) aktif olduğundan emin olun.")
    st.stop()

# --- PHASE 1: SYSTEM ARCHITECT CONFIGURATION ---
st.markdown("#### 1. Sistem Mimarı ve Vaka Konfigürasyonu")
col1, col2 = st.columns([1, 2])
with col1:
    arch_model = st.selectbox("Mimar Model (Architect LLM):", available_models)
with col2:
    research_topic = st.text_input("Araştırma Konusu:", "Evrensel temel gelir ekonomik büyümeyi nasıl etkiler?")

if st.button("Uzman Komitesini Başlat"):
    with st.spinner("Sistem Mimarı uzman profillerini oluşturuyor..."):
        prompt = f"""You are a strict JSON generator. Topic: '{research_topic}'.
        Create exactly 3 distinct academic experts to debate this topic.
        OUTPUT FORMAT RULES:
        1. YOU MUST RETURN A RAW ARRAY. DO NOT WRAP IT IN AN OBJECT.
        2. START EXACTLY WITH '[' AND END EXACTLY WITH ']'.
        
        Example Output:
        [
            {{"role": "Ekonomist", "goal": "Makroekonomik etkileri incelemek.", "backstory": "Davranışsal iktisat uzmanı."}},
            {{"role": "Sosyolog", "goal": "Toplumsal sınıf dinamiklerini analiz etmek.", "backstory": "Uygulamalı sosyoloji profesörü."}},
            {{"role": "Veri Bilimcisi", "goal": "Ekonomik simülasyonları değerlendirmek.", "backstory": "Ekonometri ve veri analizi uzmanı."}}
        ]
        
        Write the content in Turkish, but keep keys exactly as 'role', 'goal', 'backstory'."""
        
        try:
            response = requests.post(
                "http://localhost:11434/api/generate", 
                json={"model": arch_model, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.1}}, 
                timeout=120
            )
            raw_text = response.json().get('response', '')
            extracted_experts = robust_parse_json(raw_text)
            
            if len(extracted_experts) < 3:
                st.error("Sistem Mimarı JSON formatını tam olarak sağlayamadı. Lütfen daha uygun bir mimar model (örn. Llama 3) seçerek tekrar deneyin.")
                st.code(raw_text, language="json")
            else:
                st.session_state.agent_list = extracted_experts[:3]
                st.success("Uzman komitesi başarıyla tanımlandı.")
                st.rerun()
                
        except Exception as e:
            st.error(f"API Bağlantı Hatası: {e}")

# --- PHASE 2: MODEL ASSIGNMENT & EXECUTION ---
if st.session_state.agent_list and len(st.session_state.agent_list) >= 3:
    st.markdown("---")
    st.markdown(f"#### 2. Model Atamaları ve Analiz Süreci\n**Bağlam:** {research_topic}")
    
    with st.container(border=True):
        selected_configs = {}
        col_u1, col_u2, col_u3 = st.columns(3)
        
        with col_u1:
            st.markdown(f"**Uzman 1:** {st.session_state.agent_list[0]['role']}")
            m1 = st.selectbox("Uzman 1 Modeli:", available_models, key="m1")
            selected_configs[0] = {"model": m1, "data": st.session_state.agent_list[0]}
        
        with col_u2:
            st.markdown(f"**Uzman 2:** {st.session_state.agent_list[1]['role']}")
            m2 = st.selectbox("Uzman 2 Modeli:", available_models, key="m2")
            selected_configs[1] = {"model": m2, "data": st.session_state.agent_list[1]}

        with col_u3:
            st.markdown(f"**Uzman 3:** {st.session_state.agent_list[2]['role']}")
            m3 = st.selectbox("Uzman 3 Modeli:", available_models, key="m3")
            selected_configs[2] = {"model": m3, "data": st.session_state.agent_list[2]}
        
        st.divider()
        st.markdown("**Sentezleyici (Ana Karar Verici):**")
        president_model = st.selectbox("Sentezleyici Modeli:", available_models, key="m_president")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Akademik Sentezi Başlat", use_container_width=True):
        st.info("Sistem başlatıldı. İzole (stateless) analiz süreci yürütülüyor. Büyük modellerin bellek tahsisi zaman alabilir.")
        
        with st.spinner("Avaria Çekirdek Sistemi: Görevler bağımsız bağlamlarda işleniyor..."):
            try:
                # TIMEOUT SET TO 1200 SECONDS FOR COMPLEX REASONING
                def create_llm(model_name, temp=0.7):
                    return LLM(model=f"ollama/{model_name}", base_url="http://localhost:11434", temperature=temp, timeout=1200)

                # --- EXECUTION STAGE 1 ---
                st.toast("1. Aşama yürütülüyor...")
                agent1 = Agent(role=selected_configs[0]['data']['role'], goal=selected_configs[0]['data']['goal'], backstory=selected_configs[0]['data']['backstory'], llm=create_llm(selected_configs[0]['model']))
                task1 = Task(
                    description=f"Araştırma Konusu: '{research_topic}'. Kendi disiplininiz dahilinde kapsamlı bir tez sununuz. Çıktınızı maddeler halinde biçimlendiriniz.",
                    expected_output="Maddelendirilmiş akademik analiz.", agent=agent1
                )
                crew1 = Crew(agents=[agent1], tasks=[task1])
                result_1 = getattr(crew1.kickoff(), 'raw', "Sistem Hatası.")

                # --- EXECUTION STAGE 2 ---
                st.toast("2. Aşama yürütülüyor...")
                agent2 = Agent(role=selected_configs[1]['data']['role'], goal=selected_configs[1]['data']['goal'], backstory=selected_configs[1]['data']['backstory'], llm=create_llm(selected_configs[1]['model']))
                task2 = Task(
                    description=f"""Araştırma Konusu: '{research_topic}'. 
                    Aşağıdaki referans metni inceleyiniz:
                    "{result_1}"
                    
                    ZORUNLU DİREKTİF: Referans metni kopyalamayınız. Kendi uzmanlık alanınızdan bağımsız bir tez sununuz, ardından referans metne yönelik akademik bir eleştiri getiriniz ve metin sahibine 2 adet analitik soru yöneltiniz.""",
                    expected_output="Tez, akademik eleştiri ve sorular.", agent=agent2
                )
                crew2 = Crew(agents=[agent2], tasks=[task2])
                result_2 = getattr(crew2.kickoff(), 'raw', "Sistem Hatası.")

                # --- EXECUTION STAGE 3 ---
                st.toast("3. Aşama yürütülüyor...")
                agent1_rev = Agent(role=selected_configs[0]['data']['role'], goal=selected_configs[0]['data']['goal'], backstory=selected_configs[0]['data']['backstory'], llm=create_llm(selected_configs[0]['model']))
                task3 = Task(
                    description=f"""Tarafınıza yöneltilen sorular ve eleştiriler aşağıdadır:
                    "{result_2}"
                    
                    ZORUNLU DİREKTİF: Disiplininiz çerçevesinde yöneltilen sorulara maddeler halinde net cevaplar veriniz. Metin tekrarından kaçınınız.""",
                    expected_output="Maddelendirilmiş savunma ve cevap metni.", agent=agent1_rev
                )
                crew3 = Crew(agents=[agent1_rev], tasks=[task3])
                result_3 = getattr(crew3.kickoff(), 'raw', "Sistem Hatası.")

                # --- EXECUTION STAGE 4 ---
                st.toast("4. Aşama yürütülüyor...")
                agent3 = Agent(role=selected_configs[2]['data']['role'], goal=selected_configs[2]['data']['goal'], backstory=selected_configs[2]['data']['backstory'], llm=create_llm(selected_configs[2]['model']))
                task4 = Task(
                    description=f"""Araştırma Konusu: '{research_topic}'. 
                    Aşağıdaki analiz geçmişini değerlendiriniz:
                    Bölüm 1: {result_1}
                    Bölüm 2: {result_2}
                    Bölüm 3: {result_3}
                    
                    ZORUNLU DİREKTİF: İlgili bölümlerdeki metodolojik veya mantıksal eksiklikleri tespit ediniz. Kendi uzmanlık alanınıza dayanarak kapsayıcı bir değerlendirme yazınız.""",
                    expected_output="Maddelendirilmiş genel akademik değerlendirme.", agent=agent3
                )
                crew4 = Crew(agents=[agent3], tasks=[task4])
                result_4 = getattr(crew4.kickoff(), 'raw', "Sistem Hatası.")

                # --- EXECUTION STAGE 5 (SYNTHESIS) ---
                st.toast("5. Aşama yürütülüyor (Sentezleyici tüm veriyi işliyor)...")
                president = Agent(role="Sentezleyici Koordinatör", goal="Akademik veriyi sentezleyerek tarafsız sonuca ulaşmak.", backstory="Kıdemli akademik kurul başkanı.", llm=create_llm(president_model, temp=0.1))
                task5 = Task(
                    description=f"""Araştırma Konusu: '{research_topic}'.
                    Tüm oturum verileri:
                    {result_1}
                    {result_2}
                    {result_3}
                    {result_4}
                    
                    ZORUNLU DİREKTİF: Verileri kopyalamadan analiz ediniz. Tartışmanın nihai akademik sentezini 3 maddelik gerekçeli bir sonuç raporu olarak sununuz.""",
                    expected_output="3 maddelik akademik sentez raporu.", agent=president
                )
                crew5 = Crew(agents=[president], tasks=[task5])
                final_result = getattr(crew5.kickoff(), 'raw', "Sistem Hatası.")
                
                # --- OUTPUT RENDERING ---
                st.success("Analiz süreci başarıyla tamamlandı.")
                
                with st.container(border=True):
                    st.markdown("### Analiz Logları ve Çıktılar")
                    
                    st.markdown(f"**1. Uzman Analizi ({agent1.role}):**")
                    st.info(result_1)
                    
                    st.markdown(f"**2. Uzman Eleştirisi ve Soruları ({agent2.role}):**")
                    st.warning(result_2)
                    
                    st.markdown(f"**1. Uzman Savunması ({agent1.role}):**")
                    st.info(result_3)
                    
                    st.markdown(f"**3. Uzman Değerlendirmesi ({agent3.role}):**")
                    st.error(result_4)
                    
                    st.divider()
                    st.markdown("### Gerekçeli Nihai Sentez Raporu")
                    st.success(final_result)

            except Exception as e:
                st.error("Sistem Hatası: Çekirdek işleme sırasında bir istisna oluştu.")
                st.code(traceback.format_exc(), language="python")