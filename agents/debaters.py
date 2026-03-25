from crewai import Agent

def create_expert_agent(agent_data, llm_engine):
    """
    Initializes and returns a CrewAI Agent dynamically based on the provided configuration.
    """
    return Agent(
        role=agent_data['role'],
        goal=agent_data['goal'],
        backstory=agent_data['backstory'],
        llm=llm_engine
    )