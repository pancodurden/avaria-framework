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