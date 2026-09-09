"""Optional real-AI provider for Phase 5.

Uses the OpenAI Responses API when OPENAI_API_KEY is configured. If the key or
SDK is unavailable, callers can fall back to the existing local generators.
"""
import json
import os

SYSTEM_PROMPT = """You are an expert resume and job-application assistant.
Return valid JSON only. Never invent employers, degrees, certifications, skills,
achievements, metrics, dates, or experience. You may rewrite or reorganize facts
that appear in the supplied resume. Clearly label suggestions that require the
candidate to verify them."""


def is_configured():
    return bool(os.getenv("OPENAI_API_KEY"))


def generate_json(resume_text, job_description, task):
    if not is_configured():
        return None, "OPENAI_API_KEY is not configured."
    try:
        from openai import OpenAI
        client = OpenAI()
        prompt = f"""TASK: {task}\n\nRESUME:\n{resume_text[:24000]}\n\nJOB DESCRIPTION:\n{job_description[:24000]}\n\nReturn only JSON matching the requested fields."""
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
            instructions=SYSTEM_PROMPT,
            input=prompt,
            text={"format": {"type": "json_object"}},
        )
        raw = getattr(response, "output_text", "")
        return json.loads(raw), None
    except Exception as exc:
        return None, str(exc)
