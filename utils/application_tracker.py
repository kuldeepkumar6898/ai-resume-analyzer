from datetime import date

STATUSES = ["Saved", "Applied", "Screening", "Interview", "Offer", "Rejected", "Withdrawn"]


def normalize_application(data):
    data = data or {}
    status = data.get("status") or "Saved"
    if status not in STATUSES:
        status = "Saved"
    return {
        "company": str(data.get("company") or "").strip()[:120],
        "role": str(data.get("role") or "").strip()[:160],
        "location": str(data.get("location") or "").strip()[:120],
        "job_url": str(data.get("job_url") or "").strip()[:500],
        "salary": str(data.get("salary") or "").strip()[:120],
        "status": status,
        "applied_date": str(data.get("applied_date") or "").strip()[:20],
        "interview_date": str(data.get("interview_date") or "").strip()[:20],
        "contact_name": str(data.get("contact_name") or "").strip()[:120],
        "contact_email": str(data.get("contact_email") or "").strip()[:180],
        "notes": str(data.get("notes") or "").strip()[:4000],
        "resume_id": data.get("resume_id") if str(data.get("resume_id") or "").isdigit() else None,
    }


def status_order():
    return STATUSES
