from crewai import Agent

def create_judge_agent(llm_engine):
    return Agent(
        role="Sentezleyici Koordinatör",
        goal="Akademik veriyi sentezleyerek tarafsız sonuca ulaşmak.",
        backstory="Kıdemli akademik kurul başkanı.",
        llm=llm_engine
    )

def create_security_council(llm_engine):
    roles = [
        {
            "role": "Mantık Analisti", 
            "goal": "Sentezdeki mantıksal çelişkileri ve argümantasyon hatalarını tespit etmek.", 
            "backstory": "Safsata ve argümantasyon analizi konusunda uzman kıdemli araştırmacı."
        },
        {
            "role": "Veri Doğrulama Denetçisi", 
            "goal": "Yapay zeka halüsinasyonlarını ve desteksiz iddiaları tespit etmek.", 
            "backstory": "Yalnızca ampirik kanıta dayalı verileri kabul eden, şüpheci veri doğrulama uzmanı."
        },
        {
            "role": "Karşıt Argüman Uzmanı", 
            "goal": "Sentezin tam tersi senaryoları zorlayarak metnin dayanıklılığını test etmek.", 
            "backstory": "Mevcut teorileri sarsmayı ve alternatif hipotezleri savunan analist."
        },
        {
            "role": "Etik Denetmen", 
            "goal": "Kararın toplumsal ve ahlaki uygunluğunu, olası yan etkilerini denetlemek.", 
            "backstory": "İnsan hakları ve uygulamalı etik profesörü."
        },
        {
            "role": "Nihai Karar Mercii", 
            "goal": "Tüm itirazları değerlendirip ilk sentezi doğrulanmış nihai bir rapora dönüştürmek.", 
            "backstory": "Yalnızca filtrelenmiş ve mantıksal süzgeçten geçmiş gerçeklere inanan baş denetçi."
        }
    ]
    
    return [
        Agent(
            role=r["role"],
            goal=r["goal"],
            backstory=r["backstory"],
            llm=llm_engine
        )
        for r in roles
    ]