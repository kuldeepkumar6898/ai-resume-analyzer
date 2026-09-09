import re
from data.skills import SKILLS

def detect_skills(text):
    low = text.lower()
    found = []
    for skill in SKILLS:
        if skill.lower() in low:
            found.append(skill)
    return sorted(set(found))

def analyze_resume(text, job_description=""):
    low = text.lower()
    sections = {
        "Contact": bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text) and re.search(r"\+?\d[\d\s().-]{8,}", text)),
        "Summary": any(x in low for x in ["summary", "profile", "objective"]),
        "Experience": any(x in low for x in ["experience", "work history", "employment"]),
        "Education": "education" in low,
        "Skills": "skills" in low,
        "Projects": "projects" in low,
        "Certifications": "certification" in low or "certifications" in low
    }
    skills = detect_skills(text)
    words = len(text.split())
    score = 35
    score += min(20, len(skills) * 2)
    score += 10 if sections["Experience"] else 0
    score += 8 if sections["Education"] else 0
    score += 7 if sections["Skills"] else 0
    score += 5 if sections["Contact"] else 0
    score += 5 if sections["Projects"] else 0
    score = min(100, score)

    jd_match = None
    if job_description.strip():
        jd_skills = detect_skills(job_description)
        matched = [s for s in jd_skills if s in skills]
        missing = [s for s in jd_skills if s not in skills]
        jd_match = {
            "job_skills": jd_skills,
            "matched": matched,
            "missing": missing,
            "percentage": round(len(matched)/len(jd_skills)*100) if jd_skills else 0
        }

    return {
        "ats_score": score,
        "skills": skills,
        "sections": sections,
        "word_count": words,
        "job_match": jd_match,
        "recommendations": [
            "Add measurable achievements with numbers or percentages.",
            "Use a concise professional summary tailored to the target role.",
            "Keep skills aligned with the job description without adding skills you do not actually have.",
            "Use consistent headings, dates and bullet formatting."
        ]
    }
