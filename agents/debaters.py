from crewai import Agent

PERSONALITIES = {
    "akademik": "Akademik ve nesnel bir üslup kullan. Her iddiayı kaynaklarla destekle. Metodolojik ve sistematik yaklaş.",
    "sinik": "Sinik ve şüpheci bir tutum sergile. İddiaları sorgula, iyimser varsayımları çürüt. Her şeyin arka planını araştır.",
    "iyimser": "Yapıcı ve çözüm odaklı yaklaş. Fırsatlara ve olumlu senaryolara odaklan. Uzlaşı arayan bir tavır takın.",
    "sert": "Sert ve doğrudan bir üslup kullan. Taviz verme, karşı argümanları agresif olarak çürüt. Keskin ve iddialı ol.",
    "pragmatik": "Pratik ve sonuç odaklı düşün. Teorik tartışmalar yerine uygulanabilir çözümler sun. Gerçekçi ol.",
}

def create_expert_agent(agent_data, llm_engine, personality="akademik", tools=None):
    p_note = PERSONALITIES.get(personality, PERSONALITIES["akademik"])
    hedef = agent_data.get('goal', 'Analiz yapmak.') + f" {p_note}"
    hikaye = agent_data.get('backstory', 'Uzman.') + " Verilen araştırma verilerini kullanarak güçlü, kanıta dayalı argümanlar üretirsin."
    return Agent(
        role=agent_data.get('role', 'Uzman Araştırmacı'),
        goal=hedef,
        backstory=hikaye,
        verbose=True,
        allow_delegation=False,
        tools=tools or [],
        llm=llm_engine
    )
