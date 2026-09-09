import re
from utils.analyzer import detect_skills


def _first_name(resume_text):
    lines = [x.strip() for x in resume_text.splitlines() if x.strip()]
    for line in lines[:5]:
        if '@' not in line and len(line.split()) in (2, 3) and not re.search(r'\d|resume|curriculum', line, re.I):
            return line.split()[0]
    return 'Hiring Manager'


def _role(jd):
    patterns = [r'(?:position|role|title)\s*[:\-]?\s*([A-Za-z][A-Za-z /&+.-]{2,60})', r'([A-Za-z][A-Za-z /&+.-]{2,50})\s+(?:developer|engineer|analyst|designer|manager|specialist|consultant)']
    for p in patterns:
        m = re.search(p, jd, re.I)
        if m:
            return m.group(1).strip(' .:-')
    return 'the position'


def _company(jd):
    m = re.search(r'(?:at|join|company|organization)\s+([A-Z][A-Za-z0-9& .-]{2,50})', jd)
    return m.group(1).strip(' .,:') if m else 'your organization'


def generate_cover_letter(resume_text, job_description, tone='professional'):
    skills = detect_skills(resume_text)
    target = detect_skills(job_description)
    matched = [s for s in target if s in skills][:5]
    role = _role(job_description)
    company = _company(job_description)
    first = _first_name(resume_text)
    focus = ', '.join(matched) or ', '.join(skills[:4]) or 'relevant technical and professional skills'
    tone_line = {'professional':'professional and results-focused', 'confident':'confident and impact-focused', 'friendly':'warm, concise, and professional'}.get(tone, 'professional and results-focused')
    body = [
        'Dear Hiring Manager,',
        '',
        f'I am excited to apply for {role} at {company}. My background includes {focus}, and I am interested in bringing these skills to a team where I can contribute practical, measurable results.',
        '',
        f'In my experience, I have worked with {focus}. I would welcome the opportunity to apply that experience to the priorities described in the job posting, while continuing to learn and contribute to the team.',
        '',
        f'I would be glad to discuss how my background could support {company}. Thank you for considering my application.',
        '',
        'Sincerely,',
        first,
    ]
    return {'cover_letter': '\n'.join(body), 'tone': tone_line, 'matched_skills': matched, 'truthfulness_note': 'Review and personalize this draft. Do not claim achievements, tools, employers, or experience that are not true.'}


def generate_application_email(resume_text, job_description):
    first = _first_name(resume_text)
    role = _role(job_description)
    company = _company(job_description)
    skills = detect_skills(resume_text)
    focus = ', '.join(skills[:4]) or 'relevant skills'
    subject = f'Application for {role} — {first}'
    body = f"Hello Hiring Team,\n\nI am writing to apply for {role} at {company}. My background includes {focus}, and I believe my experience could be a strong fit for the role.\n\nPlease find my resume attached for your consideration. I would appreciate the opportunity to discuss how I can contribute to your team.\n\nThank you,\n{first}"
    return {'subject': subject, 'email': body}


def generate_linkedin_optimizer(resume_text, job_description):
    skills = detect_skills(resume_text)
    target = detect_skills(job_description)
    missing = [s for s in target if s not in skills]
    keywords = target[:10]
    headline = f"Professional | {', '.join(skills[:3]) or 'Technology & Business'} | Results-Focused"
    about = (f"Results-oriented professional with experience in {', '.join(skills[:6]) or 'relevant professional skills'}. "
             f"Interested in opportunities where I can apply practical expertise, collaborate with teams, and deliver measurable outcomes. "
             f"For target roles, emphasize genuine experience with {', '.join(keywords[:5]) or 'the role requirements' }.")
    return {'headline': headline, 'about': about, 'keywords': keywords, 'missing_skills': missing[:8], 'tips': [
        'Use the target role title naturally in your headline and About section when it accurately describes your goal.',
        'Add quantified achievements to Experience instead of generic responsibilities.',
        'Keep skills aligned with the job description only when you genuinely possess them.',
        'Feature 2–4 relevant projects with outcomes and technologies used.'
    ]}
