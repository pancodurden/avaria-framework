import json
import re

def robust_parse_json(raw_text):
    text = re.sub(r'```json\s*', '', raw_text)
    text = re.sub(r'```', '', text)
    
    try:
        data = json.loads(text)
        expert_list = []

        if not data:
            return []

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    data = value
                    break
            if isinstance(data, dict):
                data = [data]

        if not isinstance(data, list):
            return []

        for item in data:
            if not isinstance(item, dict): 
                continue
            role = next((v for k, v in item.items() if k.lower() in ["role", "rol", "unvan", "title"]), "Expert")
            goal = next((v for k, v in item.items() if k.lower() in ["goal", "amac", "hedef", "purpose"]), "Analysis")
            backstory = next((v for k, v in item.items() if k.lower() in ["backstory", "gecmis", "background"]), "Academic Researcher")
            expert_list.append({"role": role, "goal": goal, "backstory": backstory})
            
        return expert_list
        
    except json.JSONDecodeError:
        roles = re.findall(r'"(?:role|rol|unvan|title)"\s*:\s*"([^"]+)"', text, re.I)
        goals = re.findall(r'"(?:goal|amac|hedef|purpose)"\s*:\s*"([^"]+)"', text, re.I)
        backs = re.findall(r'"(?:backstory|gecmis|background)"\s*:\s*"([^"]+)"', text, re.I)
        return [{"role": r, "goal": g, "backstory": b} for r, g, b in zip(roles, goals, backs)]

def safe_output(task_obj):
    if hasattr(task_obj, 'output') and task_obj.output is not None:
        return getattr(task_obj.output, 'raw', str(task_obj.output))
    return "System Warning: The model failed to generate a valid response at this stage."