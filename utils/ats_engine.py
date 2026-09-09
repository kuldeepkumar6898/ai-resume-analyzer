import re
from collections import Counter
from data.skills import SKILLS
from utils.analyzer import detect_skills

SECTION_ALIASES = {
    'summary': ['summary', 'professional summary', 'profile', 'objective'],
    'experience': ['experience', 'work experience', 'professional experience', 'employment', 'work history'],
    'education': ['education', 'academic background', 'qualifications'],
    'skills': ['skills', 'technical skills', 'core skills', 'competencies'],
    'projects': ['projects', 'project experience'],
    'certifications': ['certification', 'certifications', 'licenses'],
}

COMMON_ACTION_VERBS = {
    'built','developed','created','designed','implemented','managed','led','optimized','improved',
    'automated','analyzed','delivered','launched','increased','reduced','generated','coordinated',
    'engineered','deployed','maintained','developed','configured','tested','migrated','streamlined'
}

STOPWORDS = {
    'the','and','for','with','from','that','this','you','your','are','our','will','have','has','had',
    'into','about','role','job','work','working','using','years','year','experience','candidate','skills',
    'skill','required','preferred','ability','strong','good','knowledge','team','teams','responsibilities',
    'responsibility','including','such','must','should','who','what','when','where','their','they','them',
    'all','any','can','may','per','not','but','also','more','than','within','through','across','support'
}


def _tokens(text):
    return re.findall(r'[a-zA-Z][a-zA-Z0-9+#.-]{2,}', text.lower())


def _keywords(text, limit=40):
    counts = Counter(w for w in _tokens(text) if w not in STOPWORDS and len(w) > 2)
    return [w for w, _ in counts.most_common(limit)]


def _has_contact(text):
    email = bool(re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text))
    phone = bool(re.search(r'(?:\+?\d[\d\s().-]{8,}\d)', text))
    return email, phone


def _section_presence(text):
    low = text.lower()
    result = {}
    for key, aliases in SECTION_ALIASES.items():
        result[key] = any(re.search(r'(?m)^\s*' + re.escape(alias) + r'\s*[:\-]?\s*$', low) for alias in aliases)
        if not result[key]:
            result[key] = any(alias in low for alias in aliases)
    return result


def _formatting_flags(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    flags = []
    if len(lines) < 8:
        flags.append(('critical', 'Very little extractable text was found. ATS parsing may be incomplete.'))
    if re.search(r'\bhttps?://\S+', text):
        flags.append(('info', 'URLs were detected. Keep important contact details in readable text as well.'))
    if '\t' in text:
        flags.append(('warning', 'Tab-heavy formatting can be less reliable across ATS parsers.'))
    if re.search(r'[│┃║]{2,}', text):
        flags.append(('warning', 'Table/column separator characters were detected; verify the ATS text order.'))
    if re.search(r'\b(page|pg)\s+\d+\b', text.lower()):
        flags.append(('info', 'Page-number text was detected; avoid manually typed page numbers.'))
    return flags


def _score_dimensions(text, job_description=''):
    low = text.lower()
    words = text.split()
    sections = _section_presence(text)
    email, phone = _has_contact(text)
    skills = detect_skills(text)
    bullets = [line for line in text.splitlines() if re.match(r'^[-•*▪◦]\s+', line.strip())]
    action_count = sum(1 for line in bullets if any(re.search(r'\b' + re.escape(v) + r'\b', line.lower()) for v in COMMON_ACTION_VERBS))
    quantified = len(re.findall(r'\b\d+(?:\.\d+)?\s*%|\b\$\s?\d+[\d,.]*|\b\d+[\d,.]*\s*(?:users|clients|projects|hours|days|months|years|people|customers)\b', text.lower()))

    content = min(100, 35 + min(25, len(skills) * 2) + (12 if sections['experience'] else 0) + (10 if sections['education'] else 0) + (8 if sections['skills'] else 0) + (5 if sections['projects'] else 0) + (5 if sections['summary'] else 0))
    structure = sum([20 if email else 0, 15 if phone else 0, 20 if sections['experience'] else 0, 15 if sections['education'] else 0, 15 if sections['skills'] else 0, 10 if sections['projects'] else 0, 5 if sections['summary'] else 0])
    length = 100 if 350 <= len(words) <= 900 else (85 if 180 <= len(words) <= 1200 else 60)
    impact = min(100, 45 + min(25, action_count * 7) + min(30, quantified * 10))

    keyword = 0
    keyword_data = {'matched': [], 'missing': [], 'top': []}
    if job_description.strip():
        jd_kw = _keywords(job_description, 35)
        resume_kw = set(_keywords(text, 80))
        matched = [w for w in jd_kw if w in resume_kw]
        missing = [w for w in jd_kw if w not in resume_kw]
        keyword = round(len(matched) / len(jd_kw) * 100) if jd_kw else 0
        keyword_data = {'matched': matched[:20], 'missing': missing[:20], 'top': jd_kw[:20]}
    else:
        keyword = min(100, 50 + min(50, len(skills) * 3))

    overall = round(content * .25 + structure * .25 + length * .15 + impact * .15 + keyword * .20)
    return {
        'overall': max(0, min(100, overall)),
        'content': max(0, min(100, content)),
        'structure': max(0, min(100, structure)),
        'length': max(0, min(100, length)),
        'impact': max(0, min(100, impact)),
        'keyword': max(0, min(100, keyword)),
        'sections': sections,
        'skills': skills,
        'word_count': len(words),
        'bullet_count': len(bullets),
        'action_bullets': action_count,
        'quantified_examples': quantified,
        'keyword_data': keyword_data,
    }


def simulate_ats(text, job_description=''):
    text = text or ''
    result = _score_dimensions(text, job_description)
    sections = result['sections']
    flags = _formatting_flags(text)
    recommendations = []

    if not result['sections']['summary']:
        recommendations.append('Add a concise Professional Summary tailored to the target role.')
    if not result['sections']['experience']:
        recommendations.append('Add an Experience section or clearly label relevant work history.')
    if not result['sections']['skills']:
        recommendations.append('Add a clearly labeled Skills section using standard ATS-friendly terms.')
    if not result['sections']['education']:
        recommendations.append('Add an Education section with degree, institution and dates.')
    if result['word_count'] < 180:
        recommendations.append('The resume appears too short for many professional roles; add relevant evidence, projects or achievements.')
    elif result['word_count'] > 1200:
        recommendations.append('The resume is quite long; remove repetitive or low-value content.')
    if result['bullet_count'] and result['action_bullets'] < max(1, result['bullet_count'] // 2):
        recommendations.append('Start more bullets with strong action verbs such as Built, Led, Implemented or Optimized.')
    if result['quantified_examples'] == 0:
        recommendations.append('Add measurable outcomes where truthful: percentages, time saved, revenue, users, scale or volume.')
    if job_description.strip() and result['keyword_data']['missing']:
        recommendations.append('Review missing job keywords and add them only where they accurately describe your experience.')
    if not recommendations:
        recommendations.append('Your resume has a solid ATS foundation. Keep formatting simple and tailor keywords to each role.')

    # Human-readable parser status
    parser_ready = result['overall'] >= 70 and not any(level == 'critical' for level, _ in flags)
    grade = 'Excellent' if result['overall'] >= 85 else 'Strong' if result['overall'] >= 70 else 'Needs Improvement' if result['overall'] >= 50 else 'High Risk'
    return {
        'ats_score': result['overall'],
        'grade': grade,
        'parser_ready': parser_ready,
        'dimensions': {
            'content': result['content'],
            'structure': result['structure'],
            'length': result['length'],
            'impact': result['impact'],
            'keywords': result['keyword'],
        },
        'word_count': result['word_count'],
        'bullet_count': result['bullet_count'],
        'action_bullets': result['action_bullets'],
        'quantified_examples': result['quantified_examples'],
        'sections': sections,
        'skills': result['skills'],
        'keyword_intelligence': result['keyword_data'],
        'formatting_flags': [{'level': level, 'message': msg} for level, msg in flags],
        'recommendations': recommendations[:8],
    }
