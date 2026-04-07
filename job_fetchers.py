from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import requests


@dataclass
class JobItem:
    title: str
    company: str
    location: str
    source: str
    url: str
    description: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "source": self.source,
            "url": self.url,
            "description": self.description,
        }


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return html.unescape(str(value)).strip()


def _first_nonempty(*values: object) -> str:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _location_matches(candidate: str, filter_text: Optional[str]) -> bool:
    if not filter_text:
        return True

    candidate = _clean_text(candidate).lower()
    filter_text = _clean_text(filter_text).lower()

    if not candidate:
        return False

    # Check broad chunks such as Vancouver / BC / Canada
    chunks = [c.strip() for c in re.split(r"[,\-/|]+", filter_text) if c.strip()]
    if filter_text in candidate:
        return True
    return any(chunk in candidate for chunk in chunks)


def fetch_adzuna_jobs(
    *,
    app_id: str,
    app_key: str,
    query: str,
    location: str = "Vancouver, BC, Canada",
    distance_km: int = 25,
    max_days_old: int = 14,
    results_per_page: int = 50,
    pages: int = 2,
) -> List[Dict[str, str]]:
    """Fetch jobs from Adzuna's official job search API.

    This version intentionally avoids extra restrictive filters such as
    full_time/permanent so the search returns a broader Vancouver set.
    """
    if not app_id or not app_key:
        return []

    base = "https://api.adzuna.com/v1/api/jobs/ca/search"
    headers = {"Accept": "application/json"}
    all_items: List[Dict[str, str]] = []

    for page in range(1, pages + 1):
        url = f"{base}/{page}"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": query,
            "where": location,
            "distance": int(distance_km),
            "max_days_old": int(max_days_old),
            "results_per_page": int(results_per_page),
            "sort_by": "date",
            "salary_include_unknown": "1",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("results", []) or []:
            location_obj = item.get("location") or {}
            all_items.append(
                JobItem(
                    title=_first_nonempty(item.get("title")),
                    company=_first_nonempty(
                        (item.get("company") or {}).get("display_name"),
                        item.get("company"),
                    ),
                    location=_first_nonempty(location_obj.get("display_name"), location),
                    source="Adzuna",
                    url=_first_nonempty(item.get("redirect_url"), item.get("adref")),
                    description=_first_nonempty(item.get("description")),
                ).to_dict()
            )

    return all_items


def fetch_greenhouse_board(board_token: str, *, location_filter: Optional[str] = None) -> List[Dict[str, str]]:
    """Fetch jobs from a public Greenhouse board."""
    token = _clean_text(board_token)
    if not token:
        return []

    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    items: List[Dict[str, str]] = []
    for job in data.get("jobs", []) or []:
        loc = _first_nonempty((job.get("location") or {}).get("name"), location_filter or "")
        content = _first_nonempty(job.get("content"))
        if location_filter and not _location_matches(loc or content, location_filter):
            continue

        items.append(
            JobItem(
                title=_first_nonempty(job.get("title")),
                company=_first_nonempty(token),
                location=loc,
                source="Greenhouse",
                url=_first_nonempty(job.get("absolute_url")),
                description=content,
            ).to_dict()
        )
    return items


def fetch_lever_postings(company_slug: str, *, location_filter: Optional[str] = None) -> List[Dict[str, str]]:
    """Fetch public Lever postings for a company slug."""
    slug = _clean_text(company_slug)
    if not slug:
        return []

    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    items: List[Dict[str, str]] = []

    if isinstance(data, dict):
        payload = data.get("postings") or data.get("jobs") or []
    else:
        payload = data

    for job in payload or []:
        categories = job.get("categories") or {}
        loc = _first_nonempty(categories.get("location"), location_filter or "")
        content = _first_nonempty(
            job.get("descriptionPlain") or job.get("description") or job.get("text")
        )

        if location_filter and not _location_matches(loc or content, location_filter):
            continue

        items.append(
            JobItem(
                title=_first_nonempty(job.get("text"), job.get("title")),
                company=_first_nonempty(slug),
                location=loc,
                source="Lever",
                url=_first_nonempty(job.get("hostedUrl"), job.get("applyUrl"), job.get("url")),
                description=content,
            ).to_dict()
        )
    return items


def dedupe_jobs(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    deduped: List[Dict[str, str]] = []

    for row in rows:
        key = (
            _clean_text(row.get("title")).lower(),
            _clean_text(row.get("company")).lower(),
            _clean_text(row.get("location")).lower(),
            _clean_text(row.get("url")).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            {
                "title": _clean_text(row.get("title")),
                "company": _clean_text(row.get("company")),
                "location": _clean_text(row.get("location")),
                "source": _clean_text(row.get("source")),
                "url": _clean_text(row.get("url")),
                "description": _clean_text(row.get("description")),
            }
        )

    return deduped