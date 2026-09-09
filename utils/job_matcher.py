import re
from collections import Counter
from data.skills import SKILLS
from utils.analyzer import detect_skills

STOPWORDS = {
    'the','and','for','with','from','that','this','you','your','are','our','will','have','has','had','into','about',
    'role','job','work','working','using','years','year','experience','candidate','skills','skill','required','preferred',
    'ability','strong','good','knowledge','team','teams','responsibilities','responsibility','including','such','must'
}

def keyword_tokens(text):
    words = re.findall(r'[a-zA-Z][a-zA-Z0-9+#.-]{2,}', text.lower())
    return [w for w in words if w not in STOPWORDS]

def analyze_job_match(resume_text, job_description):
    resume_skills = detect_skills(resume_text)
    job_skills = detect_skills(job_description)
    matched = [s for s in job_skills if s in resume_skills]
    missing = [s for s in job_skills if s not in resume_skills]

    resume_tokens = Counter(keyword_tokens(resume_text))
    jd_tokens = Counter(keyword_tokens(job_description))
    important = [w for w, c in jd_tokens.most_common(30) if c >= 1]
    matched_keywords = [w for w in important if resume_tokens[w] > 0]
    missing_keywords = [w for w in important if resume_tokens[w] == 0]
    keyword_score = round(len(matched_keywords) / len(important) * 100) if important else 0
    skill_score = round(len(matched) / len(job_skills) * 100) if job_skills else 0
    overall = round(skill_score * 0.65 + keyword_score * 0.35) if (job_skills or important) else 0

    return {
        'overall_match': overall,
        'skill_match': skill_score,
        'keyword_match': keyword_score,
        'resume_skills': resume_skills,
        'job_skills': job_skills,
        'matched_skills': matched,
        'missing_skills': missing,
        'matched_keywords': matched_keywords[:20],
        'missing_keywords': missing_keywords[:20],
        'top_keywords': important[:20],
        'recommendations': build_recommendations(missing, missing_keywords, overall)
    }

def build_recommendations(missing_skills, missing_keywords, overall):
    tips = []
    if overall < 50:
        tips.append('Tailor the resume strongly to the target job before applying.')
    elif overall < 75:
        tips.append('Improve keyword alignment and add evidence for relevant skills.')
    else:
        tips.append('Your resume is well aligned; focus on measurable achievements and clarity.')
    if missing_skills:
        tips.append('Only add missing skills if you genuinely have the experience; otherwise learn them and demonstrate them through projects.')
    if missing_keywords:
        tips.append('Naturally use important job-description terms in relevant summary, experience, or project bullets.')
    tips.append('Prefer quantified outcomes such as percentages, time saved, revenue, users, or project scale.')
    return tips
