from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from pathlib import Path
from utils.extractor import extract_text
from utils.analyzer import analyze_resume
from utils.ai_features import rewrite_resume, analyze_skill_gap, optimize_resume_for_job
from utils.resume_builder import build_docx, build_pdf
from utils.job_matcher import analyze_job_match
from utils.ats_engine import simulate_ats
from utils.application_assistant import generate_cover_letter, generate_application_email, generate_linkedin_optimizer
from utils.ai_provider import generate_json, is_configured
from utils.resume_versions import local_generate
from utils.application_tracker import normalize_application, STATUSES
from utils.database import init_db, create_user, authenticate, save_resume, list_resumes, get_resume, delete_resume, create_resume_version, list_resume_versions, update_resume_version_meta, create_application, list_applications, get_application, update_application, delete_application, application_stats, admin_stats, admin_analytics, list_users, set_user_status, set_user_role, log_activity, log_ai_usage

import os, time, csv, io, secrets, logging, uuid
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') or secrets.token_hex(32)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', str(10 * 1024 * 1024)))
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() in {'1','true','yes','on'}
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=int(os.getenv('SESSION_LIFETIME_HOURS', '12')))
app.config['TRUSTED_HOSTS'] = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '').split(',') if h.strip()] or None
app.config['MAX_FORM_MEMORY_SIZE'] = int(os.getenv('MAX_FORM_MEMORY_SIZE', str(2 * 1024 * 1024)))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

logging.basicConfig(level=getattr(logging, os.getenv('LOG_LEVEL','INFO').upper(), logging.INFO), format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger('resume_studio')

# Optional rate limiting. Redis is recommended for multi-worker production deployments.
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address, app=app, default_limits=[os.getenv('RATE_LIMIT_DEFAULT', '300 per hour')], storage_uri=os.getenv('RATE_LIMIT_STORAGE_URI', 'memory://'))
except Exception:
    limiter = None

UNSAFE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
CSRF_EXEMPT_PATHS = {'/login', '/register'}

@app.before_request
def production_request_guards():
    # Same-origin protection for browser state-changing requests. Login/register are ordinary forms.
    if request.method in UNSAFE_METHODS and request.path not in CSRF_EXEMPT_PATHS:
        origin = request.headers.get('Origin')
        referer = request.headers.get('Referer')
        host = request.host_url.rstrip('/')
        if origin and origin.rstrip('/') != host:
            return jsonify({'error': 'Cross-origin request blocked.'}), 403
        if not origin and referer and not referer.startswith(host + '/'):
            return jsonify({'error': 'Cross-origin request blocked.'}), 403
    if request.endpoint and request.endpoint not in {'static', 'health', 'ready'}:
        request.environ['request_started_at'] = time.perf_counter()

@app.after_request
def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    if app.config.get('SESSION_COOKIE_SECURE'):
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return response

@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({'error': 'Uploaded data is too large. Maximum allowed size is 10 MB.'}), 413

@app.errorhandler(500)
def internal_error(error):
    logger.exception('Unhandled server error: %s', error)
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error.'}), 500
    return render_template('auth.html', mode='login', error='Something went wrong. Please try again.'), 500

init_db()
# Optional first-run admin provisioning. Set ADMIN_EMAIL and ADMIN_PASSWORD before starting the app.
from utils.database import get_conn, USE_POSTGRES
if os.getenv('ADMIN_EMAIL') and os.getenv('ADMIN_PASSWORD'):
    with get_conn() as _conn:
        _email = os.getenv('ADMIN_EMAIL').strip().lower()
        _row = _conn.execute('SELECT id FROM users WHERE email=?', (_email,)).fetchone()
        if not _row:
            _ph = __import__('werkzeug.security', fromlist=['generate_password_hash']).generate_password_hash(os.getenv('ADMIN_PASSWORD'))
            _conn.execute('INSERT INTO users(name,email,password_hash,role,is_active) VALUES(?,?,?,?,1)', (os.getenv('ADMIN_NAME','Administrator'), _email, _ph, 'admin'))
            _conn.commit()
        else:
            _conn.execute("UPDATE users SET role='admin', is_active=1 WHERE email=?", (_email,)); _conn.commit()
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
EXPORT_DIR = BASE_DIR / "exports"
UPLOAD_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

ALLOWED = {"pdf", "docx", "txt"}

def current_user():
    return session.get('user')


def track_ai(feature, provider, success=True, started=None):
    user = current_user()
    if not user:
        return
    duration = int((time.perf_counter() - started) * 1000) if started else 0
    log_ai_usage(user['id'], feature, provider, success, duration)


def login_required(view):
    from functools import wraps
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user(): return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        confirm = request.form.get('confirm_password','')
        if not name or not email or len(password) < 6:
            error = 'Name, valid email and password of at least 6 characters are required.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif create_user(name, email, password) is None:
            error = 'An account with this email already exists.'
        else:
            user = authenticate(email, password)
            session['user'] = {'id': user['id'], 'name': user['name'], 'email': user['email'], 'role': user.get('role','user')}
            return redirect(url_for('index'))
    return render_template('auth.html', mode='register', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user(): return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        user = authenticate(request.form.get('email',''), request.form.get('password',''))
        if not user:
            error = 'Invalid email or password.'
        else:
            session['user'] = {'id': user['id'], 'name': user['name'], 'email': user['email'], 'role': user.get('role','user')}
            log_activity(user['id'], 'login', 'Successful login')
            return redirect(url_for('index'))
    return render_template('auth.html', mode='login', error=error)

def admin_required(view):
    from functools import wraps
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or user.get('role') != 'admin':
            return redirect(url_for('index'))
        return view(*args, **kwargs)
    return wrapped

@app.get('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin.html', user=current_user(), stats=admin_stats(), users=list_users())

@app.get('/api/admin/stats')
@admin_required
def api_admin_stats():
    return jsonify(admin_stats())

@app.get('/api/admin/analytics')
@admin_required
def api_admin_analytics():
    days = request.args.get('days', 30, type=int)
    return jsonify(admin_analytics(days))

@app.get('/api/admin/analytics.csv')
@admin_required
def api_admin_analytics_csv():
    days = request.args.get('days', 30, type=int)
    data = admin_analytics(days)
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(['Section','Metric','Value'])
    for key, value in data['ai'].items(): writer.writerow(['AI Summary', key, value])
    writer.writerow(['AI Summary','active_ai_users',data['active_ai_users']])
    for row in data['features']: writer.writerow(['Feature', row['feature'], row['count']])
    for row in data['providers']: writer.writerow(['Provider', row['provider'], row['count']])
    for row in data['daily_ai']: writer.writerow(['Daily AI', row['day'], row['calls']])
    return (out.getvalue(), 200, {'Content-Type':'text/csv; charset=utf-8','Content-Disposition':f'attachment; filename=resume_studio_analytics_{days}d.csv'})

@app.patch('/api/admin/users/<int:user_id>')
@admin_required
def api_admin_user(user_id):
    data=request.get_json(silent=True) or {}
    target=current_user()['id']
    if user_id == target and data.get('is_active') is False:
        return jsonify({'error':'You cannot deactivate your own admin account.'}),400
    ok=True
    if 'is_active' in data: ok=set_user_status(user_id, bool(data['is_active'])) and ok
    if 'role' in data: ok=set_user_role(user_id, data['role']) and ok
    if not ok: return jsonify({'error':'User not found.'}),404
    log_activity(target, 'admin_user_update', f'Updated user {user_id}')
    return jsonify({'success':True})

@app.get('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.get('/history')
@login_required
def history():
    return render_template('history.html', user=current_user(), resumes=list_resumes(current_user()['id']))

@app.post('/api/resumes')
@login_required
def api_save_resume():
    data = request.get_json(silent=True) or {}
    title = data.get('title') or data.get('resume', {}).get('name') or 'My Resume'
    resume_id = data.get('id')
    rid = save_resume(current_user()['id'], title, data.get('resume', {}), resume_id)
    if rid: log_activity(current_user()['id'], 'resume_saved', title)
    if not rid: return jsonify({'error':'Resume not found or you do not have permission.'}), 404
    return jsonify({'success': True, 'id': rid, 'message': 'Resume saved successfully.'})

@app.get('/api/resumes/<int:resume_id>')
@login_required
def api_get_resume(resume_id):
    r = get_resume(current_user()['id'], resume_id)
    if not r: return jsonify({'error':'Resume not found.'}), 404
    return jsonify(r)

@app.delete('/api/resumes/<int:resume_id>')
@login_required
def api_delete_resume(resume_id):
    if not delete_resume(current_user()['id'], resume_id): return jsonify({'error':'Resume not found.'}), 404
    log_activity(current_user()['id'], 'resume_deleted', str(resume_id))
    return jsonify({'success': True})

@app.get("/applications")
@login_required
def applications():
    return render_template("applications.html", user=current_user(), stats=application_stats(current_user()["id"]), statuses=STATUSES, applications=list_applications(current_user()["id"]))

@app.get("/api/applications")
@login_required
def api_applications():
    status=request.args.get("status")
    return jsonify({"applications": list_applications(current_user()["id"], status if status in STATUSES else None), "stats": application_stats(current_user()["id"]), "statuses": STATUSES})

@app.post("/api/applications")
@login_required
def api_create_application():
    data=normalize_application(request.get_json(silent=True) or {})
    if not data["company"] and not data["role"]:
        return jsonify({"error":"Company or job title is required."}),400
    rid=create_application(current_user()["id"], data)
    log_activity(current_user()['id'], 'application_created', f'{data.get("company","")} / {data.get("role","")}')
    return jsonify({"success":True,"id":rid,"application":get_application(current_user()["id"],rid)})

@app.get("/api/applications/<int:application_id>")
@login_required
def api_get_application(application_id):
    item=get_application(current_user()["id"],application_id)
    return jsonify(item) if item else (jsonify({"error":"Application not found."}),404)

@app.patch("/api/applications/<int:application_id>")
@login_required
def api_update_application(application_id):
    data=normalize_application(request.get_json(silent=True) or {})
    if not data["company"] and not data["role"]:
        return jsonify({"error":"Company or job title is required."}),400
    ok=update_application(current_user()["id"],application_id,data)
    return jsonify({"success":True,"application":get_application(current_user()["id"],application_id)}) if ok else (jsonify({"error":"Application not found."}),404)

@app.delete("/api/applications/<int:application_id>")
@login_required
def api_delete_application(application_id):
    ok=delete_application(current_user()["id"],application_id)
    return jsonify({"success":True}) if ok else (jsonify({"error":"Application not found."}),404)

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    result = None
    error = None
    if request.method == "POST":
        file = request.files.get("resume")
        if not file or not file.filename:
            error = "Please select a resume file."
        else:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED:
                error = "Only PDF, DOCX and TXT files are supported."
            else:
                original_name = secure_filename(file.filename)
                filename = f"{uuid.uuid4().hex}_{original_name}"
                path = UPLOAD_DIR / filename
                file.save(path)
                try:
                    # Lightweight file signature checks before parsing.
                    head = path.read_bytes()[:8]
                    if ext == 'pdf' and not head.startswith(b'%PDF'):
                        raise ValueError('The uploaded file is not a valid PDF.')
                    if ext == 'docx' and not head.startswith(b'PK'):
                        raise ValueError('The uploaded file is not a valid DOCX.')
                    text = extract_text(path)
                    result = analyze_resume(text, "")
                    result["resume_text"] = text
                except Exception as e:
                    error = f"Could not read the resume: {e}"
                finally:
                    try:
                        path.unlink(missing_ok=True)
                    except Exception:
                        logger.warning('Could not remove temporary upload %s', path)
    return render_template("index.html", result=result, error=error)

@app.get("/api/resume-versions")
@login_required
def api_resume_versions():
    parent_id = request.args.get("parent_id", type=int)
    return jsonify({"versions": list_resume_versions(current_user()["id"], parent_id)})

@app.post("/api/resume-versions")
@login_required
def api_create_resume_version():
    data = request.get_json(silent=True) or {}
    resume = data.get("resume") or {}
    rid = create_resume_version(current_user()["id"], data.get("title") or "Job Targeted Resume", resume, data.get("parent_id"), data.get("target_role") or resume.get("target_role") or "", data.get("job_description") or "", data.get("version_label") or "Job Version")
    return jsonify({"success": True, "id": rid, "message": "Resume version created."})

@app.post("/api/resume-versions/<int:resume_id>/duplicate")
@login_required
def api_duplicate_resume_version(resume_id):
    source = get_resume(current_user()["id"], resume_id)
    if not source: return jsonify({"error":"Resume version not found."}), 404
    rid = create_resume_version(current_user()["id"], (source["title"] + " Copy")[:120], source["data"], source.get("parent_id") or source["id"], source.get("target_role", ""), source.get("job_description", ""), "Duplicate")
    return jsonify({"success":True,"id":rid,"message":"Resume version duplicated."})

@app.patch("/api/resume-versions/<int:resume_id>")
@login_required
def api_update_resume_version_meta(resume_id):
    data=request.get_json(silent=True) or {}
    ok=update_resume_version_meta(current_user()["id"], resume_id, data.get("title"), data.get("target_role"), data.get("job_description"), data.get("version_label"))
    return jsonify({"success":True}) if ok else (jsonify({"error":"Resume version not found."}),404)

@app.post("/api/ai-build-resume")
@login_required
def api_ai_build_resume():
    started=time.perf_counter()
    data=request.get_json(silent=True) or {}
    resume=data.get("resume") or {}
    jd=(data.get("job_description") or "").strip()
    if not jd: return jsonify({"error":"Job description is required."}),400
    task="Create a job-targeted resume plan. Return JSON with version_title, target_role, professional_summary, improved_bullets, priority_keywords, missing_keywords, truthfulness_note. Never invent employers, degrees, certifications, skills, dates, metrics or achievements; only use facts in the resume."
    resume_text="\n".join(str(resume.get(k,"")) for k in ("name","summary","skills","experience","projects","education","certifications"))
    if is_configured():
        result, error=generate_json(resume_text,jd,task)
        if result is not None:
            result["source"]="real_ai"
            track_ai('AI Resume Builder', 'openai', True, started)
            return jsonify(result)
    result=local_generate(resume,jd)
    track_ai('AI Resume Builder', 'local', True, started)
    result["source"]="local_fallback"
    return jsonify(result)

@app.get("/api/ai-status")
def api_ai_status():
    return jsonify({"configured": is_configured(), "provider": "OpenAI Responses API" if is_configured() else "Local fallback"})

@app.post("/api/ai-optimize")
def api_ai_optimize():
    started=time.perf_counter()
    data = request.get_json(silent=True) or {}
    resume_text = data.get("resume_text", "")
    job_description = data.get("job_description", "")
    if not resume_text.strip() or not job_description.strip():
        return jsonify({"error": "Resume text and job description are required."}), 400
    task = """Analyze the resume for this job. Return an object with: ats_summary (string), professional_summary (string), improved_bullets (array of strings), priority_keywords (array of strings), missing_skills (array of strings), interview_focus (array of strings), and truthfulness_note (string). Only use facts from the resume; do not invent facts."""
    result, error = generate_json(resume_text, job_description, task)
    if result is None:
        track_ai('AI Optimizer', 'openai', False, started)
        return jsonify({"error": "Real AI is not configured or failed.", "detail": error, "fallback_available": True}), 503
    track_ai('AI Optimizer', 'openai', True, started)
    return jsonify(result)

@app.post("/api/rewrite")
def api_rewrite():
    started=time.perf_counter()
    data = request.get_json(silent=True) or {}
    result = rewrite_resume(data.get("resume_text", ""), data.get("job_description", ""))
    track_ai('Resume Rewriter', 'local', True, started)
    return jsonify(result)

@app.post("/api/skill-gap")
def api_skill_gap():
    started=time.perf_counter()
    data = request.get_json(silent=True) or {}
    result = analyze_skill_gap(data.get("resume_text", ""), data.get("job_description", ""))
    track_ai('Skill Gap Analyzer', 'local', True, started)
    return jsonify(result)


@app.post("/api/job-match")
def api_job_match():
    started=time.perf_counter()
    data = request.get_json(silent=True) or {}
    resume_text = data.get("resume_text", "")
    job_description = data.get("job_description", "")
    if not resume_text.strip() or not job_description.strip():
        return jsonify({"error": "Resume text and job description are required."}), 400
    result = analyze_job_match(resume_text, job_description)
    track_ai('Job Match', 'local', True, started)
    return jsonify(result)

@app.post("/api/optimize")
def api_optimize():
    started=time.perf_counter()
    data = request.get_json(silent=True) or {}
    resume_text = data.get("resume_text", "")
    job_description = data.get("job_description", "")
    if not resume_text.strip() or not job_description.strip():
        return jsonify({"error": "Resume text and job description are required."}), 400
    result = optimize_resume_for_job(resume_text, job_description)
    track_ai('Resume Optimization', 'local', True, started)
    return jsonify(result)

@app.post("/api/cover-letter")
def api_cover_letter():
    started=time.perf_counter()
    data = request.get_json(silent=True) or {}
    resume_text, jd = data.get("resume_text", ""), data.get("job_description", "")
    if not resume_text.strip() or not jd.strip():
        return jsonify({"error": "Resume text and job description are required."}), 400
    result = generate_cover_letter(resume_text, jd, data.get("tone", "professional"))
    track_ai('Cover Letter', 'local', True, started)
    return jsonify(result)

@app.post("/api/application-email")
def api_application_email():
    started=time.perf_counter()
    data = request.get_json(silent=True) or {}
    resume_text, jd = data.get("resume_text", ""), data.get("job_description", "")
    if not resume_text.strip() or not jd.strip():
        return jsonify({"error": "Resume text and job description are required."}), 400
    result = generate_application_email(resume_text, jd)
    track_ai('Application Email', 'local', True, started)
    return jsonify(result)

@app.post("/api/linkedin-optimize")
def api_linkedin_optimize():
    started=time.perf_counter()
    data = request.get_json(silent=True) or {}
    resume_text, jd = data.get("resume_text", ""), data.get("job_description", "")
    if not resume_text.strip() or not jd.strip():
        return jsonify({"error": "Resume text and job description are required."}), 400
    result = generate_linkedin_optimizer(resume_text, jd)
    track_ai('LinkedIn Optimizer', 'local', True, started)
    return jsonify(result)

@app.post("/api/export")
@login_required
def api_export():
    data = request.get_json(silent=True) or {}
    resume = data.get("resume", {})
    fmt = data.get("format", "pdf").lower()
    if fmt not in {"pdf", "docx"}:
        return jsonify({"error": "Unsupported export format"}), 400

    name = secure_filename(resume.get("name", "my_resume")) or "my_resume"
    output = EXPORT_DIR / f"u{current_user()['id']}_{uuid.uuid4().hex}_{name}_resume.{fmt}"

    try:
        if fmt == "pdf":
            build_pdf(resume, output)
        else:
            build_docx(resume, output)
        return jsonify({"download_url": f"/download/{output.name}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/download/<filename>")
@login_required
def download(filename):
    path = EXPORT_DIR / secure_filename(filename)
    if not path.exists():
        return "File not found", 404
    return send_file(path, as_attachment=True)

@app.get("/health")
def health():
    return jsonify({"status": "ok", "phase": 6, "module": "production-security-deployment", "ai_configured": is_configured(), "environment": os.getenv('APP_ENV','development')})

@app.get("/ready")
def ready():
    try:
        with get_conn() as conn:
            conn.execute('SELECT 1').fetchone()
        return jsonify({"status": "ready", "database": "ok"})
    except Exception:
        logger.exception('Readiness check failed')
        return jsonify({"status": "not_ready", "database": "error"}), 503

if __name__ == "__main__":
    debug = os.getenv('FLASK_DEBUG','false').lower() in {'1','true','yes','on'} and os.getenv('APP_ENV','development') != 'production'
    app.run(host=os.getenv('HOST','127.0.0.1'), port=int(os.getenv('PORT','5000')), debug=debug)
