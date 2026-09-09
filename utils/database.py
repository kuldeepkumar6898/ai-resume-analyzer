import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

import os

DB_PATH = Path(os.getenv('RESUME_DB_PATH', str(Path(__file__).resolve().parent.parent / 'resume_studio.db'))).expanduser()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=15000')
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        for ddl in [
            "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'",
            "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
        ]:
            try: conn.execute(ddl)
            except sqlite3.OperationalError: pass
        conn.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, action TEXT NOT NULL, details TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_logs(created_at)')
        conn.execute("""CREATE TABLE IF NOT EXISTS ai_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, feature TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'local', success INTEGER NOT NULL DEFAULT 1,
            duration_ms INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )""")
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ai_usage_created ON ai_usage(created_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ai_usage_feature ON ai_usage(feature)')
        conn.execute('''CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )''')
        # Phase 5 Module 4 metadata for job-specific resume versions.
        for ddl in [
            "ALTER TABLE resumes ADD COLUMN parent_id INTEGER",
            "ALTER TABLE resumes ADD COLUMN target_role TEXT DEFAULT ''",
            "ALTER TABLE resumes ADD COLUMN job_description TEXT DEFAULT ''",
            "ALTER TABLE resumes ADD COLUMN version_label TEXT DEFAULT 'Version 1'"
        ]:
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass
        conn.execute("""CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            company TEXT NOT NULL DEFAULT '', role TEXT NOT NULL DEFAULT '', location TEXT DEFAULT '',
            job_url TEXT DEFAULT '', salary TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Saved',
            applied_date TEXT DEFAULT '', interview_date TEXT DEFAULT '', contact_name TEXT DEFAULT '',
            contact_email TEXT DEFAULT '', notes TEXT DEFAULT '', resume_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        conn.execute('CREATE INDEX IF NOT EXISTS idx_applications_user_status ON applications(user_id,status)')
        conn.commit()

def create_user(name, email, password):
    try:
        with get_conn() as conn:
            cur = conn.execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',
                               (name.strip(), email.strip().lower(), generate_password_hash(password)))
            conn.commit()
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None

def authenticate(email, password):
    with get_conn() as conn:
        user = conn.execute('SELECT * FROM users WHERE email=? AND is_active=1', (email.strip().lower(),)).fetchone()
    if user and check_password_hash(user['password_hash'], password):
        return dict(user)
    return None

def log_activity(user_id, action, details=''):
    with get_conn() as conn:
        conn.execute('INSERT INTO activity_logs(user_id,action,details) VALUES(?,?,?)', (user_id, action, details[:500]))
        conn.commit()

def admin_stats():
    with get_conn() as conn:
        users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        active_users = conn.execute('SELECT COUNT(*) FROM users WHERE is_active=1').fetchone()[0]
        resumes = conn.execute('SELECT COUNT(*) FROM resumes').fetchone()[0]
        applications = conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0]
        interviews = conn.execute("SELECT COUNT(*) FROM applications WHERE status='Interview'").fetchone()[0]
        offers = conn.execute("SELECT COUNT(*) FROM applications WHERE status='Offer'").fetchone()[0]
        recent_users = conn.execute('SELECT id,name,email,role,is_active,created_at FROM users ORDER BY created_at DESC LIMIT 8').fetchall()
        app_counts = conn.execute('SELECT status,COUNT(*) count FROM applications GROUP BY status ORDER BY count DESC').fetchall()
        activity = conn.execute('''SELECT a.id,a.action,a.details,a.created_at,u.name,u.email FROM activity_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.created_at DESC,a.id DESC LIMIT 12''').fetchall()
    return {'users':users,'active_users':active_users,'resumes':resumes,'applications':applications,'interviews':interviews,'offers':offers,
            'recent_users':[dict(x) for x in recent_users], 'application_counts':{x['status']:x['count'] for x in app_counts},
            'activity':[dict(x) for x in activity]}

def list_users():
    with get_conn() as conn:
        return [dict(x) for x in conn.execute('SELECT id,name,email,role,is_active,created_at FROM users ORDER BY created_at DESC').fetchall()]

def set_user_status(user_id, active):
    with get_conn() as conn:
        cur=conn.execute('UPDATE users SET is_active=? WHERE id=?', (1 if active else 0,user_id))
        conn.commit(); return cur.rowcount>0

def set_user_role(user_id, role):
    role = role if role in ('user','admin') else 'user'
    with get_conn() as conn:
        cur=conn.execute('UPDATE users SET role=? WHERE id=?', (role,user_id))
        conn.commit(); return cur.rowcount>0

def save_resume(user_id, title, data, resume_id=None):
    import json
    payload = json.dumps(data, ensure_ascii=False)
    with get_conn() as conn:
        if resume_id:
            cur = conn.execute('UPDATE resumes SET title=?, data=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?',
                               (title.strip() or 'My Resume', payload, resume_id, user_id))
            if cur.rowcount == 0:
                return None
            rid = resume_id
        else:
            cur = conn.execute('INSERT INTO resumes(user_id,title,data) VALUES(?,?,?)',
                               (user_id, title.strip() or 'My Resume', payload))
            rid = cur.lastrowid
        conn.commit()
        return rid

def list_resumes(user_id):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute('SELECT id,title,created_at,updated_at FROM resumes WHERE user_id=? ORDER BY updated_at DESC', (user_id,)).fetchall()]

def get_resume(user_id, resume_id):
    import json
    with get_conn() as conn:
        r = conn.execute('SELECT * FROM resumes WHERE id=? AND user_id=?', (resume_id, user_id)).fetchone()
    if not r:
        return None
    item = dict(r)
    item['data'] = json.loads(item['data'])
    return item

def delete_resume(user_id, resume_id):
    with get_conn() as conn:
        cur = conn.execute('DELETE FROM resumes WHERE id=? AND user_id=?', (resume_id, user_id))
        conn.commit()
        return cur.rowcount > 0


def create_resume_version(user_id, title, data, parent_id=None, target_role='', job_description='', version_label='Version 1'):
    import json
    payload = json.dumps(data, ensure_ascii=False)
    with get_conn() as conn:
        cur = conn.execute(
            'INSERT INTO resumes(user_id,title,data,parent_id,target_role,job_description,version_label) VALUES(?,?,?,?,?,?,?)',
            (user_id, title.strip() or 'My Resume', payload, parent_id, target_role.strip(), job_description, version_label.strip() or 'Version 1')
        )
        conn.commit()
        return cur.lastrowid

def list_resume_versions(user_id, parent_id=None):
    with get_conn() as conn:
        if parent_id is None:
            rows = conn.execute('SELECT id,title,target_role,version_label,parent_id,created_at,updated_at FROM resumes WHERE user_id=? ORDER BY updated_at DESC', (user_id,)).fetchall()
        else:
            rows = conn.execute('SELECT id,title,target_role,version_label,parent_id,created_at,updated_at FROM resumes WHERE user_id=? AND (id=? OR parent_id=?) ORDER BY updated_at DESC', (user_id,parent_id,parent_id)).fetchall()
        return [dict(r) for r in rows]

def update_resume_version_meta(user_id, resume_id, title=None, target_role=None, job_description=None, version_label=None):
    fields=[]; values=[]
    for col,val in [('title',title),('target_role',target_role),('job_description',job_description),('version_label',version_label)]:
        if val is not None:
            fields.append(col+'=?'); values.append(val)
    if not fields: return False
    values += [resume_id,user_id]
    with get_conn() as conn:
        cur=conn.execute('UPDATE resumes SET '+', '.join(fields)+', updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?', values)
        conn.commit(); return cur.rowcount>0



def create_application(user_id, data):
    with get_conn() as conn:
        cur = conn.execute("""INSERT INTO applications
            (user_id,company,role,location,job_url,salary,status,applied_date,interview_date,contact_name,contact_email,notes,resume_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            user_id, data.get('company',''), data.get('role',''), data.get('location',''), data.get('job_url',''),
            data.get('salary',''), data.get('status','Saved'), data.get('applied_date',''), data.get('interview_date',''),
            data.get('contact_name',''), data.get('contact_email',''), data.get('notes',''), data.get('resume_id')
        ))
        conn.commit()
        return cur.lastrowid


def list_applications(user_id, status=None):
    with get_conn() as conn:
        if status:
            rows = conn.execute('SELECT * FROM applications WHERE user_id=? AND status=? ORDER BY updated_at DESC, id DESC', (user_id,status)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM applications WHERE user_id=? ORDER BY updated_at DESC, id DESC', (user_id,)).fetchall()
        return [dict(r) for r in rows]


def get_application(user_id, application_id):
    with get_conn() as conn:
        r = conn.execute('SELECT * FROM applications WHERE id=? AND user_id=?', (application_id,user_id)).fetchone()
    return dict(r) if r else None


def update_application(user_id, application_id, data):
    fields=['company','role','location','job_url','salary','status','applied_date','interview_date','contact_name','contact_email','notes','resume_id']
    values=[data.get(k,'') for k in fields]
    with get_conn() as conn:
        cur=conn.execute('UPDATE applications SET '+','.join(f'{f}=?' for f in fields)+',updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?', values+[application_id,user_id])
        conn.commit()
        return cur.rowcount > 0


def delete_application(user_id, application_id):
    with get_conn() as conn:
        cur=conn.execute('DELETE FROM applications WHERE id=? AND user_id=?',(application_id,user_id))
        conn.commit()
        return cur.rowcount > 0


def application_stats(user_id):
    with get_conn() as conn:
        rows=conn.execute('SELECT status, COUNT(*) AS count FROM applications WHERE user_id=? GROUP BY status',(user_id,)).fetchall()
        counts={r['status']:r['count'] for r in rows}
    return {'total':sum(counts.values()), 'active':sum(counts.get(x,0) for x in ('Applied','Screening','Interview')), 'interviews':counts.get('Interview',0), 'offers':counts.get('Offer',0), 'rejected':counts.get('Rejected',0), 'counts':counts}


def log_ai_usage(user_id, feature, provider='local', success=True, duration_ms=0):
    with get_conn() as conn:
        conn.execute('INSERT INTO ai_usage(user_id,feature,provider,success,duration_ms) VALUES(?,?,?,?,?)',
                     (user_id, feature[:80], provider[:40], 1 if success else 0, max(0, int(duration_ms or 0))))
        conn.commit()

def admin_analytics(days=30):
    days = max(1, min(int(days or 30), 365))
    with get_conn() as conn:
        summary = conn.execute("""SELECT COUNT(*) total_calls,
            COALESCE(SUM(CASE WHEN success=1 THEN 1 ELSE 0 END),0) successful_calls,
            COALESCE(SUM(CASE WHEN success=0 THEN 1 ELSE 0 END),0) failed_calls,
            COALESCE(AVG(duration_ms),0) avg_duration_ms
            FROM ai_usage WHERE created_at >= datetime('now', ?)""", (f'-{days} days',)).fetchone()
        features = conn.execute("""SELECT feature, COUNT(*) count, SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) successful, AVG(duration_ms) avg_duration_ms FROM ai_usage WHERE created_at >= datetime('now', ?) GROUP BY feature ORDER BY count DESC""", (f'-{days} days',)).fetchall()
        providers = conn.execute("""SELECT provider, COUNT(*) count FROM ai_usage WHERE created_at >= datetime('now', ?) GROUP BY provider ORDER BY count DESC""", (f'-{days} days',)).fetchall()
        daily = conn.execute("""SELECT date(created_at) day, COUNT(*) calls, SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) successful FROM ai_usage WHERE created_at >= datetime('now', ?) GROUP BY date(created_at) ORDER BY day ASC""", (f'-{days} days',)).fetchall()
        active = conn.execute("""SELECT COUNT(DISTINCT user_id) FROM ai_usage WHERE user_id IS NOT NULL AND created_at >= datetime('now', ?)""", (f'-{days} days',)).fetchone()[0]
        top_users = conn.execute("""SELECT u.id,u.name,u.email,COUNT(a.id) calls FROM ai_usage a LEFT JOIN users u ON u.id=a.user_id WHERE a.created_at >= datetime('now', ?) GROUP BY a.user_id ORDER BY calls DESC LIMIT 10""", (f'-{days} days',)).fetchall()
        registrations = conn.execute("""SELECT date(created_at) day, COUNT(*) count FROM users WHERE created_at >= datetime('now', ?) GROUP BY date(created_at) ORDER BY day ASC""", (f'-{days} days',)).fetchall()
        resumes = conn.execute("""SELECT date(created_at) day, COUNT(*) count FROM resumes WHERE created_at >= datetime('now', ?) GROUP BY date(created_at) ORDER BY day ASC""", (f'-{days} days',)).fetchall()
        applications = conn.execute("""SELECT date(created_at) day, COUNT(*) count FROM applications WHERE created_at >= datetime('now', ?) GROUP BY date(created_at) ORDER BY day ASC""", (f'-{days} days',)).fetchall()
    return {'days':days, 'ai':dict(summary), 'active_ai_users':active, 'features':[dict(x) for x in features], 'providers':[dict(x) for x in providers], 'daily_ai':[dict(x) for x in daily], 'top_ai_users':[dict(x) for x in top_users], 'registrations':[dict(x) for x in registrations], 'resumes':[dict(x) for x in resumes], 'applications':[dict(x) for x in applications]}
