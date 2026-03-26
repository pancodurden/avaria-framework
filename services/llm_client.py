import os
import requests
from crewai import LLM

os.environ["OPENAI_API_KEY"] = "NA"

def get_ollama_models():
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        return [model['name'] for model in response.json()['models']]
    except requests.exceptions.RequestException: 
        return []

def create_llm(model_name, temp=0.7):
    return LLM(
        model=f"ollama/{model_name}", 
        base_url="http://localhost:11434", 
        temperature=temp, 
        timeout=3600
    )