import streamlit as st
import requests
import traceback
import os
from crewai import Task, Crew

# --- CUSTOM MODULE IMPORTS ---
from services.llm_client import get_ollama_models, create_llm
from utils.stateless_loop import robust_parse_json
from agents.debaters import create_expert_agent
from agents.judge import create_judge_agent, create_security_council

# --- STREAMLIT PAGE CONFIGURATION ---
st.set_page_config(page_title="Avaria Multi-Agent Framework", layout="wide")

# --- UI STYLING INITIALIZATION ---
def load_css(file_name):
    """Loads external CSS for advanced UI styling."""
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"CSS file not found: {file_name}")

load_css("assets/style.css")

# --- SESSION STATE MANAGEMENT ---
if "agent_list" not in st.session_state:
    st.session_state.agent_list = []

# --- APPLICATION HEADER ---
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
    research_topic = st.text_input("Araştırma Konusu:", "Yapay zeka insanlığın sonunu mu getirecek?")

if st.button("Uzman Komitesini Başlat"):
    with st.spinner("Sistem Mimarı uzman profillerini oluşturuyor..."):
        prompt = f"""You are a strict JSON generator. Topic: '{research_topic}'. Create exactly 3 distinct academic experts."""
        try:
            response = requests.post("http://localhost:11434/api/generate", json={"model": arch_model, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.1}}, timeout=120)
            raw_text = response.json().get('response', '')
            extracted_experts = robust_parse_json(raw_text)
            
            # --- FALLBACK MECHANISM FOR JSON DECODING FAILURES ---
            default_experts = [
                {"role": "Sistem Kuramcısı", "goal": "Konuyu sistem dinamikleri içinde değerlendirmek.", "backstory": "Profesör."}, 
                {"role": "Mantık Analisti", "goal": "Argümanları sorgulamak.", "backstory": "Uzman."}, 
                {"role": "Etik Felsefeci", "goal": "Ahlaki boyutları incelemek.", "backstory": "Profesör."}
            ]
            
            while len(extracted_experts) < 3: 
                extracted_experts.append(default_experts[len(extracted_experts)])
                
            st.session_state.agent_list = extracted_experts[:3]
            st.success("Uzman komitesi başarıyla tanımlandı.")
            st.rerun()
            
        except Exception as e: 
            st.error(f"API Hatası: {e}")

# --- PHASE 2: MODEL ASSIGNMENT & EXECUTION ---
if st.session_state.agent_list and len(st.session_state.agent_list) >= 3:
    st.markdown("---")
    st.markdown(f"#### 2. Model Atamaları ve Analiz Süreci\n**Bağlam:** {research_topic}")
    
    with st.container(border=True):
        selected_configs = {}
        cols = st.columns(3)
        for i, col in enumerate(cols):
            with col:
                st.markdown(f"**Uzman {i+1}:** {st.session_state.agent_list[i]['role']}")
                model_name = st.selectbox(f"Uzman {i+1} Modeli:", available_models, key=f"m{i}")
                selected_configs[i] = {"model": model_name, "data": st.session_state.agent_list[i]}
        
        st.divider()
        
        st.markdown("#### 3. Sentez ve Nihai Karar Heyeti")
        col_pres, col_court = st.columns(2)
        
        with col_pres:
            st.markdown("**Sentezleyici (Koordinatör):**")
            president_model = st.selectbox("Sentezleyici Modeli:", available_models, key="m_president")
            
        with col_court:
            st.markdown("**Yüksek Mahkeme (Güvenlik Heyeti):**")
            court_model = st.selectbox("Yüksek Mahkeme Modeli:", available_models, key="m_court")

    if st.button("Sistemi Başlat (Yüksek Mahkeme Dahil)", use_container_width=True):
        with st.spinner("Avaria Çekirdek Sistemi işliyor... Yüksek Mahkeme denetimi sebebiyle işlem süresi uzayabilir."):
            try:
                # --- LLM ENGINE INITIALIZATION ---
                llm1 = create_llm(selected_configs[0]['model'])
                llm2 = create_llm(selected_configs[1]['model'])
                llm3 = create_llm(selected_configs[2]['model'])
                llm_pres = create_llm(president_model, temp=0.1)
                llm_court = create_llm(court_model, temp=0.0)

                # --- AGENT INITIALIZATION ---
                agent1 = create_expert_agent(selected_configs[0]['data'], llm1)
                agent2 = create_expert_agent(selected_configs[1]['data'], llm2)
                agent3 = create_expert_agent(selected_configs[2]['data'], llm3)
                president = create_judge_agent(llm_pres)
                council = create_security_council(llm_court)

                # --- CORE EXECUTION FLOW (STATELESS ARCHITECTURE) ---
                # Added strict rules to prevent repetition loops in smaller models (e.g., 8B parameters)
                
                t1 = Task(description=f"Konu: '{research_topic}'. Akademik ve orijinal bir tez sun. KISA, NET ve MADDELER HALİNDE olsun.", agent=agent1, expected_output="Orijinal Tez.")
                r1 = getattr(Crew(agents=[agent1], tasks=[t1]).kickoff(), 'raw', "Hata.")
                
                t2 = Task(description=f"Şunu eleştir:\n'{r1}'\n\nKESİNLİKLE KURAL: Önceki metni kopyalama! Sadece itirazlarını ve yeni sorularını yaz.", agent=agent2, expected_output="Doğrudan Eleştiri.")
                r2 = getattr(Crew(agents=[agent2], tasks=[t2]).kickoff(), 'raw', "Hata.")
                
                # Re-instantiate Expert 1 to reset context and prevent context drift
                agent1_rev = create_expert_agent(selected_configs[0]['data'], llm1)
                t3 = Task(description=f"Şu eleştiriye cevap ver:\n'{r2}'\n\nKESİNLİKLE KURAL: Önceki argümanlarını tekrar etme, sadece bu yeni eleştiriye karşı yeni kanıtlar sun.", agent=agent1_rev, expected_output="Yeni Savunma.")
                r3 = getattr(Crew(agents=[agent1_rev], tasks=[t3]).kickoff(), 'raw', "Hata.")
                
                t4 = Task(description=f"Analizi değerlendir:\n{r1}\n{r2}\n{r3}\n\nKESİNLİKLE KURAL: Metinleri özetleme veya tekrar etme! Sadece tartışmanın kalitesini ve kimin haklı olduğunu yorumla.", agent=agent3, expected_output="Orijinal Değerlendirme.")
                r4 = getattr(Crew(agents=[agent3], tasks=[t4]).kickoff(), 'raw', "Hata.")
                
                t5 = Task(description=f"Tüm verileri analiz edip ilk sentezi yaz:\n{r1}\n{r2}\n{r3}\n{r4}", agent=president, expected_output="İlk sentez.")
                ilk_sentez = getattr(Crew(agents=[president], tasks=[t5]).kickoff(), 'raw', "Hata.")

                # --- PHASE 6: RED TEAMING / SECURITY COUNCIL EXECUTION ---
                st.toast("6. Aşama: Yüksek Mahkeme Güvenlik Denetimi Başlatılıyor...")
                
                t_logic = Task(description=f"Sentezdeki mantık hatalarını bul:\n{ilk_sentez}", agent=council[0], expected_output="Mantık Eleştirisi.")
                t_fact = Task(description=f"Sentezdeki halüsinasyon verileri tespit et:\n{ilk_sentez}", agent=council[1], expected_output="Veri Eleştirisi.")
                t_devil = Task(description=f"Raporun ana fikrini çürütmeye çalış:\n{ilk_sentez}", agent=council[2], expected_output="Karşıt Argüman.")
                t_ethic = Task(description=f"Raporun etik tehlikelerini yaz:\n{ilk_sentez}", agent=council[3], expected_output="Etik İtiraz.")
                
                t_supreme = Task(description=f"İlk Sentez: {ilk_sentez}\nKonsey itirazlarını dinle, yalanları ve hataları temizle, arındırılmış 'MÜHÜRLÜ NİHAİ KARAR'ı yayınla.", agent=council[4], expected_output="Mühürlü Nihai Karar.")

                supreme_court_crew = Crew(agents=council, tasks=[t_logic, t_fact, t_devil, t_ethic, t_supreme])
                muhurlu_karar = getattr(supreme_court_crew.kickoff(), 'raw', "Hata.")
                
                # --- OUTPUT RENDERING ---
                st.success("Yüksek Mahkeme denetimi başarıyla tamamlandı.")
                with st.container(border=True):
                    st.markdown("###  İlk Aşama (Geliştirici Logları)")
                    with st.expander("Ham Tartışma Verilerini Göster"):
                        st.write(f"**Uzman:** {r1}\n\n**Eleştiri:** {r2}\n\n**Savunma:** {r3}\n\n**Değerlendirme:** {r4}")
                    st.info(ilk_sentez)
                    
                    st.divider()
                    st.markdown(f"## ⚖️ YÜKSEK MAHKEME: MÜHÜRLÜ NİHAİ KARAR \n**(Denetleyen Model: {court_model})**")
                    st.success(muhurlu_karar)

            except Exception as e:
                st.error("Sistem Hatası: İşlem sırasında kritik bir sorun oluştu.")
                st.code(traceback.format_exc(), language="python")