from __future__ import annotations

import json
import os
import re
from typing import Dict, List

from google import genai
from google.genai import types


def _extract_json(text: str):
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty model output")
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("Could not parse JSON from model output")


class GeminiService:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        api_key = (api_key or "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing.")
        self.client = genai.Client(api_key=api_key)
        self.model = model or "gemini-2.5-flash"

    def rank_jobs(self, resume_text: str, jobs: List[Dict[str, str]], location: str = "Vancouver, BC, Canada") -> List[Dict[str, str]]:
        if not jobs:
            return []

        compact_jobs = []
        for i, job in enumerate(jobs[:30], start=1):
            compact_jobs.append(
                {
                    "id": i,
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "location": job.get("location", ""),
                    "source": job.get("source", ""),
                    "url": job.get("url", ""),
                    "description": (job.get("description", "")[:1800]),
                }
            )

        prompt = {
            "task": "Rank job postings against the resume for fit in Vancouver, BC area.",
            "resume": resume_text[:12000],
            "jobs": compact_jobs,
            "rules": [
                "Return JSON only.",
                "Use scores from 0 to 100.",
                "Prefer semantic fit over exact keyword overlap.",
                "Keep reasons short and practical.",
            ],
            "output_schema": {
                "ranked_jobs": [
                    {
                        "id": 1,
                        "score": 92,
                        "reason": "Strong fit: Python, ML, and deployment experience align.",
                        "missing_keywords": ["AWS", "MLOps"],
                    }
                ]
            },
        }

        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=2048,
            response_mime_type="application/json",
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=json.dumps(prompt, ensure_ascii=False),
            config=config,
        )
        raw = getattr(response, "text", "") or str(response)
        data = _extract_json(raw)
        ranked = data.get("ranked_jobs", []) or []
        by_id = {item["id"]: item for item in compact_jobs}

        merged = []
        for row in ranked:
            jid = row.get("id")
            base = by_id.get(jid)
            if not base:
                continue
            merged.append({
                **base,
                "score": int(row.get("score", 0)),
                "reason": row.get("reason", ""),
                "missing_keywords": ", ".join(row.get("missing_keywords", []) or []),
            })

        merged.sort(key=lambda x: x.get("score", 0), reverse=True)
        return merged

    def generate_application_packet(self, resume_text: str, job: Dict[str, str]) -> str:
        prompt = f"""
You are helping tailor a job application packet.
Return clear, concise markdown with these sections:
- Job summary
- Why this is a fit
- Resume strengths to emphasize
- Cover letter opening paragraph
- 5 interview talking points

Resume:
{resume_text[:12000]}

Job:
Title: {job.get('title','')}
Company: {job.get('company','')}
Location: {job.get('location','')}
Description: {job.get('description','')[:5000]}
""".strip()
        config = types.GenerateContentConfig(
            temperature=0.4,
            max_output_tokens=2048,
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        text = getattr(response, "text", None)
        return text if text else str(response)
