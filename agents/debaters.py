from crewai import Agent
from utils.tools import safe_web_search

def create_expert_agent(agent_data, llm_engine):
    hedef = agent_data.get('goal', 'Analiz yapmak.') + " Gerektiğinde en doğru veriyi bulmak için internette araştırma yap."
    hikaye = agent_data.get('backstory', 'Uzman.') + " Asla halüsinasyon görmezsin. Emin olmadığın her bilgiyi 'search_internet' aracıyla doğrularsın."

    return Agent(
        role=agent_data.get('role', 'Uzman Araştırmacı'),
        goal=hedef,
        backstory=hikaye,
        verbose=True,
        allow_delegation=False,
        tools=[safe_web_search],
        llm=llm_engine
    )