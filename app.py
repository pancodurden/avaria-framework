import streamlit as st
import requests
import traceback
import os
import json
from datetime import datetime
from crewai import Task, Crew

from services.llm_client import get_ollama_models, create_llm
from utils.stateless_loop import robust_parse_json
from agents.debaters import create_expert_agent
from agents.judge import create_judge_agent, create_security_council

st.set_page_config(page_title="Avaria Multi-Agent Framework", layout="wide")

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("assets/style.css")

if "agent_list" not in st.session_state:
    st.session_state.agent_list = []

st.markdown("<h2>Avaria Dynamic Multi-Agent Framework v2.2</h2>", unsafe_allow_html=True)
st.markdown("---")

available_models = get_ollama_models()
if not available_models:
    st.error("Ollama servisine ulaşılamadı.")
    st.stop()

st.markdown("#### 1. Sistem Mimarı")
col1, col2 = st.columns([1, 2])
with col1:
    arch_model = st.selectbox("Mimar Model:", available_models)
with col2:
    research_topic = st.text_input("Araştırma Konusu:", "Yapay zeka yargıçlar ve etik 2026")

if st.button("Uzman Komitesini Başlat"):
    with st.spinner("Uzmanlar oluşturuluyor..."):
        prompt = f"You are a strict JSON generator. Topic: '{research_topic}'. Create exactly 3 distinct academic experts."
        try:
            response = requests.post("http://localhost:11434/api/generate", json={"model": arch_model, "prompt": prompt, "stream": False, "format": "json"}, timeout=120)
            extracted_experts = robust_parse_json(response.json().get('response', ''))
            st.session_state.agent_list = extracted_experts[:3]
            st.rerun()
        except Exception as e: 
            st.error(f"Hata: {e}")

if st.session_state.agent_list:
    cols = st.columns(3)
    selected_configs = {}
    for i, col in enumerate(cols):
        with col:
            st.markdown(f"**{st.session_state.agent_list[i]['role']}**")
            m = st.selectbox(f"Model {i+1}:", available_models, key=f"m{i}")
            selected_configs[i] = {"model": m, "data": st.session_state.agent_list[i]}

    st.divider()
    president_model = st.selectbox("Sentezleyici:", available_models, key="m_pres")
    court_model = st.selectbox("Yüksek Mahkeme:", available_models, key="m_court")

    if st.button("Sistemi Başlat", use_container_width=True):
        with st.spinner("Avaria Araştırma Yapıyor... (Terminali Kontrol Et!)"):
            try:
                llm1 = create_llm(selected_configs[0]['model'])
                llm2 = create_llm(selected_configs[1]['model'])
                llm3 = create_llm(selected_configs[2]['model'])
                llm_p = create_llm(president_model, temp=0.1)
                llm_c = create_llm(court_model, temp=0.0)

                agent1 = create_expert_agent(selected_configs[0]['data'], llm1)
                agent2 = create_expert_agent(selected_configs[1]['data'], llm2)
                agent3 = create_expert_agent(selected_configs[2]['data'], llm3)
                president = create_judge_agent(llm_p)
                council = create_security_council(llm_c)

                t1 = Task(
                    description=f"Topic: '{research_topic}'. MANDATORY: You MUST use the 'search_internet' tool to find real data. Write a short thesis with facts.", 
                    agent=agent1, expected_output="Fact-based thesis."
                )
                r1 = getattr(Crew(agents=[agent1], tasks=[t1]).kickoff(), 'raw', "Hata.")
                
                mem = {"tarih": str(datetime.now()), "konu": research_topic, "agent_1": r1}
                with open("avaria_memory.json", "w", encoding="utf-8") as f: 
                    json.dump(mem, f, indent=4)
                st.toast("Ajan 1 verisi JSON'a işlendi.")

                t2 = Task(
                    description=f"Read: '{r1}'. MANDATORY: Use 'search_internet' to find counter-facts. Do NOT repeat the text. Just criticize with new evidence.", 
                    agent=agent2, expected_output="Fact-based criticism."
                )
                r2 = getattr(Crew(agents=[agent2], tasks=[t2]).kickoff(), 'raw', "Hata.")
                
                mem["agent_2"] = r2
                with open("avaria_memory.json", "w", encoding="utf-8") as f: 
                    json.dump(mem, f, indent=4)
                st.toast("Ajan 2 verisi JSON'a işlendi.")

                agent1_rev = create_expert_agent(selected_configs[0]['data'], llm1)
                t3 = Task(description=f"Refute this: '{r2}'. Use your expertise to defend your initial points with new logic.", agent=agent1_rev, expected_output="Final defense.")
                r3 = getattr(Crew(agents=[agent1_rev], tasks=[t3]).kickoff(), 'raw', "Hata.")

                t4 = Task(description=f"Analyze who won the debate: \n1: {r1}\n2: {r2}\n3: {r3}. DO NOT COPY TEXT.", agent=agent3, expected_output="Logical verdict.")
                r4 = getattr(Crew(agents=[agent3], tasks=[t4]).kickoff(), 'raw', "Hata.")

                t5 = Task(description=f"Create first synthesis from: {r1}, {r2}, {r3}, {r4}", agent=president, expected_output="Initial synthesis.")
                sentez = getattr(Crew(agents=[president], tasks=[t5]).kickoff(), 'raw', "Hata.")

                st.toast("Yüksek Mahkeme inceliyor...")
                t_supreme = Task(description=f"Sentez: {sentez}. Check ethics and logic. Give the FINAL SEALED VERDICT in Turkish.", agent=council[4], expected_output="Sealed Verdict.")
                muhurlu = getattr(Crew(agents=council, tasks=[t_supreme]).kickoff(), 'raw', "Hata.")

                st.markdown("### İşlem Kayıtları")
                with st.expander("Ham Tartışma"): 
                    st.write(f"R1: {r1}\n\nR2: {r2}\n\nR3: {r3}")
                st.info(sentez)
                st.success(f"## NİHAİ KARAR\n{muhurlu}")

            except Exception as e: 
                st.error(f"Sistem Hatası: {e}")
                st.code(traceback.format_exc())