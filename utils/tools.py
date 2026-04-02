import os
import subprocess
import tempfile

from ddgs import DDGS
from crewai.tools import tool


@tool("search_internet")
def safe_web_search(query: str) -> str:
    """İnternette güncel bilgi, haber ve veri aramak için bu aracı kullan."""
    max_results = 3
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return "Bu konu hakkında internette güncel bir bilgi bulunamadı."

        formatted_results = "İnternet Araştırma Sonuçları:\n\n"
        for i, res in enumerate(results, 1):
            formatted_results += f"--- Kaynak {i} ---\n"
            formatted_results += f"Başlık: {res.get('title', 'Başlık Yok')}\n"
            formatted_results += f"Özet: {res.get('body', 'Özet Yok')}\n"
            formatted_results += f"Link: {res.get('href', 'Link Yok')}\n\n"

        return formatted_results

    except Exception as e:
        return f"Araştırma sırasında bir hata oluştu: {str(e)}"


# ── Güvenli dizin: tool'ların dosya okuma/yazma yapabileceği sandbox ──
_SANDBOX_DIR = os.path.join(tempfile.gettempdir(), "avaria_sandbox")
os.makedirs(_SANDBOX_DIR, exist_ok=True)


def _safe_path(filename: str) -> str:
    """Dosya yolunu sandbox içine kısıtlar. Dizin geçişini engeller."""
    base = os.path.basename(filename)  # ../../../etc/passwd → passwd
    return os.path.join(_SANDBOX_DIR, base)


@tool("kod_calistir")
def kod_calistir(code: str) -> str:
    """Python kodu çalıştırır ve stdout/stderr çıktısını döndürür. Timeout: 30 saniye.
    Kullanım: Hesaplama yapmak, veri işlemek veya bir fikri test etmek için Python kodu yaz ve çalıştır.
    Girdi: Çalıştırılacak Python kodu (string).
    """
    tmp_file = os.path.join(_SANDBOX_DIR, "_run.py")
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(code)

        result = subprocess.run(
            ["python", tmp_file],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=_SANDBOX_DIR
        )

        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout.strip()}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr.strip()}\n"
        if result.returncode != 0:
            output += f"\n[Çıkış kodu: {result.returncode}]"

        return output.strip() if output.strip() else "Kod başarıyla çalıştı (çıktı yok)."

    except subprocess.TimeoutExpired:
        return "HATA: Kod 30 saniye içinde tamamlanamadı (timeout)."
    except Exception as e:
        return f"HATA: Kod çalıştırılamadı: {e}"
    finally:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)


@tool("dosya_oku")
def dosya_oku(filename: str) -> str:
    """Sandbox içindeki bir dosyanın içeriğini okur.
    Kullanım: Daha önce yazılmış bir dosyanın içeriğini kontrol etmek için kullan.
    Girdi: Dosya adı (sadece isim, yol değil).
    """
    path = _safe_path(filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > 5000:
            return content[:5000] + f"\n\n... [Dosya {len(content)} karakter, ilk 5000 gösterildi]"
        return content if content else "(Dosya boş)"
    except FileNotFoundError:
        return f"HATA: '{filename}' dosyası bulunamadı. Sandbox dizini: {_SANDBOX_DIR}"
    except Exception as e:
        return f"HATA: Dosya okunamadı: {e}"


@tool("dosya_yaz")
def dosya_yaz(filename: str, content: str) -> str:
    """Sandbox içine bir dosya yazar (üzerine yazar).
    Kullanım: Kod, veri veya rapor dosyası oluşturmak için kullan.
    Girdi: filename — dosya adı, content — yazılacak içerik.
    """
    path = _safe_path(filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"'{filename}' başarıyla yazıldı. ({len(content)} karakter, konum: {path})"
    except Exception as e:
        return f"HATA: Dosya yazılamadı: {e}"


@tool("terminal_calistir")
def terminal_calistir(command: str) -> str:
    """Shell komutu çalıştırır ve çıktısını döndürür. Timeout: 60 saniye.
    Kullanım: pip install, git status, ls gibi terminal komutları çalıştırmak için kullan.
    Girdi: Çalıştırılacak shell komutu (string).
    GÜVENLİK: rm -rf, format, del gibi tehlikeli komutlar engellenir.
    """
    # Tehlikeli komutları engelle
    _BLOCKED = ['rm -rf /', 'format ', 'del /f', 'mkfs', ':(){', 'shutdown', 'reboot',
                'dd if=', 'chmod -R 777 /', 'wget', 'curl -o', '> /dev/sd']
    cmd_lower = command.lower().strip()
    for blocked in _BLOCKED:
        if blocked in cmd_lower:
            return f"HATA: Güvenlik nedeniyle '{blocked}' içeren komutlar engellenmiştir."

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=_SANDBOX_DIR
        )

        output = ""
        if result.stdout:
            output += result.stdout.strip() + "\n"
        if result.stderr:
            output += f"STDERR: {result.stderr.strip()}\n"
        if result.returncode != 0:
            output += f"[Çıkış kodu: {result.returncode}]"

        # Çıktı çok uzunsa kes
        if len(output) > 3000:
            output = output[:3000] + "\n... [çıktı kesildi]"

        return output.strip() if output.strip() else "Komut başarıyla çalıştı (çıktı yok)."

    except subprocess.TimeoutExpired:
        return "HATA: Komut 60 saniye içinde tamamlanamadı (timeout)."
    except Exception as e:
        return f"HATA: Komut çalıştırılamadı: {e}"


# ── Tool listesi (dışarıdan import için) ──
AGENT_TOOLS = [kod_calistir, dosya_oku, dosya_yaz, terminal_calistir]
