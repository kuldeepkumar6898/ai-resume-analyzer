import re
from copy import deepcopy
from datetime import datetime


def clean(value):
    return (value or '').strip()


def split_lines(value):
    return [x.strip().lstrip('•- ').strip() for x in clean(value).splitlines() if x.strip()]


def parse_name(text):
    lines = [x.strip() for x in clean(text).splitlines() if x.strip()]
    return lines[0] if lines and len(lines[0].split()) <= 6 else ''


def local_generate(resume, job_description):
    """Safe local generator used when the real AI provider is unavailable.
    It only rearranges/rewrites facts already present in the supplied resume.
    """
    resume = deepcopy(resume or {})
    jd = clean(job_description)
    jd_words = set(re.findall(r'[a-zA-Z][a-zA-Z0-9+#.-]{2,}', jd.lower()))
    skills = [s.strip() for s in clean(resume.get('skills')).split(',') if s.strip()]
    skill_l = {s.lower(): s for s in skills}
    priority = [skill_l[w] for w in sorted(jd_words) if w in skill_l][:12]

    summary = clean(resume.get('summary'))
    if not summary:
        summary = 'Professional candidate with experience and skills relevant to the target role.'
    if priority:
        summary = summary.rstrip('.') + '. Focus areas: ' + ', '.join(priority[:6]) + '.'

    bullets = []
    for key in ('experience', 'projects'):
        for line in split_lines(resume.get(key)):
            bullets.append(line)
    # Preserve factual bullets; add only a light action-oriented prefix where absent.
    improved = []
    action_words = ('led ', 'built ', 'developed ', 'managed ', 'created ', 'implemented ', 'designed ', 'analyzed ', 'optimized ', 'delivered ')
    for line in bullets[:12]:
        if line.lower().startswith(action_words):
            improved.append(line)
        else:
            improved.append('Delivered: ' + line)

    missing = []
    for token in sorted(jd_words):
        if token in {'the','and','with','for','from','that','this','your','you','our','are','will','role','job','work','years','using','required','skills'}:
            continue
        if token not in resume_text_lower(resume):
            missing.append(token)
        if len(missing) >= 10:
            break

    return {
        'version_title': (parse_name(resume.get('name')) or 'Resume') + (' — ' + priority[0] if priority else ' — Job Targeted'),
        'target_role': priority[0] if priority else 'Target Role',
        'professional_summary': summary,
        'improved_bullets': improved,
        'priority_keywords': priority,
        'missing_keywords': missing,
        'truthfulness_note': 'Local mode only restructures and lightly rewrites information already present. Verify every statement before applying it.'
    }


def resume_text_lower(resume):
    if isinstance(resume, dict):
        return ' '.join(clean(resume.get(k)) for k in ('name','summary','skills','experience','projects','education','certifications')).lower()
    return clean(resume).lower()


def apply_generation(resume, generated):
    data = deepcopy(resume or {})
    if generated.get('professional_summary'):
        data['summary'] = generated['professional_summary']
    bullets = generated.get('improved_bullets') or []
    if bullets:
        # Keep experience and projects separate when possible by filling experience first.
        exp = split_lines(data.get('experience'))
        proj = split_lines(data.get('projects'))
        if exp:
            data['experience'] = '\n'.join(bullets[:len(exp)])
            rest = bullets[len(exp):]
            if rest:
                data['projects'] = '\n'.join(rest[:max(1, len(proj))])
        else:
            data['experience'] = '\n'.join(bullets[:8])
    data['target_role'] = clean(generated.get('target_role'))
    data['priority_keywords'] = generated.get('priority_keywords', [])
    data['missing_keywords'] = generated.get('missing_keywords', [])
    return data
