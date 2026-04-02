"""
Avaria — Akıllı Donanım Analizörü
GPU VRAM, RAM ve Ollama modellerini tespit edip uygun model önerir.
"""

import os
import subprocess
import platform
import requests
import psutil


def detect_gpu() -> dict:
    """nvidia-smi ile GPU bilgilerini tespit eder."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return {"available": False, "name": None, "vram_mb": 0}

        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        name = parts[0]
        vram_mb = int(parts[1]) if len(parts) > 1 else 0

        return {"available": True, "name": name, "vram_mb": vram_mb}
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return {"available": False, "name": None, "vram_mb": 0}


def detect_ram() -> dict:
    """Sistem RAM bilgisini döndürür."""
    mem = psutil.virtual_memory()
    total_gb = round(mem.total / (1024 ** 3), 1)
    return {"total_gb": total_gb, "available_gb": round(mem.available / (1024 ** 3), 1)}


def get_ollama_models() -> list[str]:
    """Ollama'da yüklü modelleri çeker."""
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        resp = requests.get(f"{host}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return []


def recommend_models(vram_mb: int) -> list[str]:
    """VRAM miktarına göre önerilen modelleri döndürür."""
    vram_gb = vram_mb / 1024

    if vram_mb == 0 or vram_gb < 6:
        # CPU-only veya düşük VRAM
        return ["llama3.2:3b", "qwen2.5:3b"]
    elif vram_gb < 10:
        return ["llama3.1:8b", "mistral:7b"]
    elif vram_gb < 16:
        return ["llama3.1:8b", "gemma2:9b"]
    else:
        return ["gemma2:27b", "mixtral:8x7b"]


def analyze_hardware() -> dict:
    """Tam donanım analizi yapar ve sonuçları döndürür."""
    gpu = detect_gpu()
    ram = detect_ram()
    installed_models = get_ollama_models()
    recommended = recommend_models(gpu["vram_mb"])

    # Önerilen modellerden hangisi zaten yüklü?
    ready = [m for m in recommended if m in installed_models]
    pull_needed = [m for m in recommended if m not in installed_models]

    vram_gb = round(gpu["vram_mb"] / 1024, 1) if gpu["vram_mb"] > 0 else 0

    return {
        "gpu": {
            "available": gpu["available"],
            "name": gpu["name"],
            "vram_gb": vram_gb
        },
        "ram": ram,
        "platform": platform.system(),
        "installed_models": installed_models,
        "recommended_models": recommended,
        "ready_models": ready,
        "pull_required": len(pull_needed) > 0,
        "models_to_pull": pull_needed
    }
