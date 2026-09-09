import re
from data.skills import SKILLS
from utils.analyzer import detect_skills

def rewrite_bullet(line):
    original = line.strip()
    if not original:
        return ""
    replacements = [
        (r"^responsible for\s+", "Managed "),
        (r"^worked on\s+", "Developed "),
        (r"^helped with\s+", "Supported "),
        (r"^did\s+", "Executed "),
        (r"^made\s+", "Created "),
        (r"^used\s+", "Leveraged "),
        (r"^handled\s+", "Coordinated "),
    ]
    out = original
    for pattern, replacement in replacements:
        out = re.sub(pattern, replacement, out, flags=re.I)
    if out == original and len(original.split()) >= 5:
        out = original[0].upper() + original[1:]
    return out

def rewrite_resume(resume_text, jd=""):
    skills = detect_skills(resume_text)
    jd_skills = detect_skills(jd)
    missing = [s for s in jd_skills if s not in skills]

    name = "Professional Candidate"
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", resume_text)
    if email:
        pass

    summary = (
        f"Results-oriented professional with experience in {', '.join(skills[:6]) or 'technology and business'} "
        "with a focus on delivering practical solutions, improving processes, and contributing to team goals. "
        "Adapt this summary to your actual experience and target role."
    )

    lines = [x.strip("•- \t") for x in resume_text.splitlines() if x.strip()]
    bullets = [rewrite_bullet(x) for x in lines if len(x.split()) >= 5][:8]

    return {
        "professional_summary": summary,
        "improved_bullets": bullets,
        "keyword_advice": missing[:15],
        "note": "Review every AI-generated suggestion and keep only statements that are truthful to your real experience."
    }

def analyze_skill_gap(resume_text, jd=""):
    current = detect_skills(resume_text)
    target = detect_skills(jd)
    if not target:
        target = ["Communication", "Excel", "SQL", "Python", "Git", "Project Management"]

    missing = [x for x in target if x not in current]
    readiness = round((len(target) - len(missing)) / len(target) * 100) if target else 0

    roadmap = []
    for skill in missing[:8]:
        roadmap.append({
            "skill": skill,
            "priority": "High" if skill in target[:4] else "Medium",
            "action": f"Learn {skill}, complete a small project, and add a truthful project/skill entry to your resume."
        })

    return {
        "current_skills": current,
        "target_skills": target,
        "missing_skills": missing,
        "readiness": readiness,
        "roadmap": roadmap
    }


def optimize_resume_for_job(resume_text, job_description):
    """Generate truthful, job-specific optimization suggestions without inventing experience."""
    current_skills = detect_skills(resume_text)
    target_skills = detect_skills(job_description)
    missing_skills = [s for s in target_skills if s not in current_skills]

    # Extract useful phrases from the job description while avoiding generic words.
    stop = {
        'the','and','for','with','from','that','this','you','your','are','our','will','have','has','into','about',
        'role','job','work','working','using','years','year','experience','candidate','skills','skill','required',
        'preferred','ability','strong','good','knowledge','team','teams','responsibilities','responsibility','including',
        'such','must','should','looking','join','company','position','provide','including','develop','development'
    }
    phrases = re.findall(r'[A-Za-z][A-Za-z0-9+#./-]{2,}', job_description.lower())
    seen = set()
    keywords = []
    for word in phrases:
        if word not in stop and word not in seen:
            seen.add(word)
            keywords.append(word)
        if len(keywords) >= 18:
            break

    # Keep suggestions grounded in the candidate's existing content.
    summary_skills = current_skills[:6]
    focus = ', '.join(summary_skills) or 'relevant technical and professional skills'
    target = ', '.join(target_skills[:5]) or 'the target role requirements'
    optimized_summary = (
        f"Results-oriented professional with experience in {focus}, focused on applying practical skills "
        f"to deliver measurable results and collaborate effectively. For this role, emphasize evidence related to {target}. "
        "Customize this draft to match your real experience and achievements."
    )

    lines = [x.strip('•- \t') for x in resume_text.splitlines() if x.strip()]
    source_bullets = [rewrite_bullet(x) for x in lines if len(x.split()) >= 6][:8]
    optimized_bullets = []
    for bullet in source_bullets:
        if any(k.lower() in bullet.lower() for k in keywords[:8]):
            optimized_bullets.append(bullet)
        else:
            optimized_bullets.append(bullet + " — add a measurable outcome and relevant job keyword where truthful.")
    if not optimized_bullets:
        optimized_bullets = [
            "Describe a relevant achievement using an action + task + measurable result format.",
            "Add tools, technologies, or methods from the job description only when you genuinely used them."
        ]

    section_advice = {
        'Summary': 'Keep the summary to 2–4 lines and place the most relevant skills near the beginning.',
        'Experience': 'Rewrite bullets around action, scope, tools, and measurable outcomes; prioritize the most relevant work.',
        'Skills': 'Move genuinely relevant job skills higher and remove outdated or unrelated items.',
        'Projects': 'Highlight projects that demonstrate the target role requirements and include technologies used.',
        'Education': 'Keep the most relevant qualification prominent; add coursework only when it strengthens the match.',
        'Certifications': 'Prioritize certifications directly related to the target role.'
    }

    return {
        'optimization_score': round((len(current_skills) / max(len(target_skills), len(current_skills), 1)) * 100) if target_skills else 70,
        'optimized_summary': optimized_summary,
        'optimized_bullets': optimized_bullets[:8],
        'priority_keywords': keywords[:15],
        'missing_skills': missing_skills[:15],
        'section_advice': section_advice,
        'truthfulness_note': 'Do not add a skill, responsibility, metric, employer, qualification, or achievement unless it is true and supported by your real experience.'
    }
