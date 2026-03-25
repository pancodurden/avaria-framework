import os
import requests
from crewai import LLM

# Bypass OpenAI API key requirement for local Ollama execution
os.environ["OPENAI_API_KEY"] = "NA"

def get_ollama_models():
    """
    Fetches the list of available local models from the Ollama API.
    Returns an empty list if the service is unreachable.
    """
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        return [model['name'] for model in response.json()['models']]
    except requests.exceptions.RequestException: 
        return []

def create_llm(model_name, temp=0.7):
    """
    Instantiates an isolated, stateless LLM engine for an agent.
    """
    return LLM(
        model=f"ollama/{model_name}", 
        base_url="http://localhost:11434", 
        temperature=temp, 
        timeout=3600
    )