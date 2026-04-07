from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Iterable

import certifi
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Fix SSL issues on Windows / Python 3.9
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ.pop("REQUESTS_CA_BUNDLE", None)
os.environ.pop("CURL_CA_BUNDLE", None)

APP_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=APP_DIR / ".env", override=True)

from gemini_service import GeminiService
from job_fetchers import dedupe_jobs, fetch_adzuna_jobs, fetch_greenhouse_board, fetch_lever_postings
from resume_utils import extract_resume_text

st.set_page_config(
    page_title="Chami's Job Matcher",
    page_icon="📍",
    layout="wide",
)

st.title("Chami's Job Matcher")
st.caption("Fetch live jobs from legal APIs, rank them with Gemini, and generate tailored application packets.")

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "").strip()
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "").strip()

COLUMNS = [
    "title",
    "company",
    "location",
    "source",
    "url",
    "description",
    "score",
    "reason",
    "missing_keywords",
]

if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "jobs_df" not in st.session_state:
    st.session_state.jobs_df = pd.DataFrame(columns=COLUMNS)
if "ranked_df" not in st.session_state:
    st.session_state.ranked_df = pd.DataFrame(columns=COLUMNS)
if "fetch_status" not in st.session_state:
    st.session_state.fetch_status = ""
if "application_packet" not in st.session_state:
    st.session_state.application_packet = ""


def _unique_keep_order(values: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        value = (value or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def build_adzuna_search_plan(query: str, location: str) -> list[tuple[str, str]]:
    # Broad first, then location fallbacks.
    query_variants = _unique_keep_order(
        [
            query,
            "python",
            "data",
            "machine learning",
            "software engineer",
            "data scientist",
        ]
    )

    location_variants = _unique_keep_order(
        [
            location,
            "Vancouver",
            "Vancouver, BC",
            "British Columbia",
            "British Columbia, Canada",
            "Canada",
        ]
    )

    return [(q, loc) for q in query_variants for loc in location_variants]


def load_jobs_from_sources(
    query: str,
    location: str,
    days_old: int,
    distance_km: int,
    greenhouse_boards: str,
    lever_slugs: str,
) -> pd.DataFrame:
    jobs = []
    adzuna_hits = 0
    search_plan = build_adzuna_search_plan(query, location)

    if ADZUNA_APP_ID and ADZUNA_APP_KEY:
        st.sidebar.caption(
            f"Adzuna search plan: {len(search_plan)} combinations "
            "(broad query + Vancouver fallbacks)"
        )

        for q, loc in search_plan:
            try:
                fetched = fetch_adzuna_jobs(
                    app_id=ADZUNA_APP_ID,
                    app_key=ADZUNA_APP_KEY,
                    query=q,
                    location=loc,
                    max_days_old=days_old,
                    distance_km=distance_km,
                    results_per_page=50,
                    pages=2,
                )
                if fetched:
                    jobs.extend(fetched)
                    adzuna_hits += len(fetched)

                if len(jobs) >= 150:
                    break
            except Exception as exc:
                st.warning(f"Adzuna search failed for '{q}' in '{loc}': {exc}")
    else:
        st.warning("Adzuna keys are missing, so live job fetch is disabled.")

    for board in [x.strip() for x in greenhouse_boards.split(",") if x.strip()]:
        try:
            jobs.extend(fetch_greenhouse_board(board, location_filter=location))
        except Exception as exc:
            st.warning(f"Greenhouse board '{board}' failed: {exc}")

    for slug in [x.strip() for x in lever_slugs.split(",") if x.strip()]:
        try:
            jobs.extend(fetch_lever_postings(slug, location_filter=location))
        except Exception as exc:
            st.warning(f"Lever company '{slug}' failed: {exc}")

    jobs = dedupe_jobs(jobs)

    if not jobs:
        st.info(
            "No jobs returned yet. Broaden the query, increase the radius, or set Max days old to 30."
        )
    else:
        st.success(f"Loaded {len(jobs)} jobs ({adzuna_hits} from Adzuna before dedupe).")

    return pd.DataFrame(jobs)


with st.sidebar:
    st.header("Config")
    st.write("Gemini key:", "✅ loaded" if API_KEY else "❌ missing")
    st.write("Adzuna key:", "✅ loaded" if (ADZUNA_APP_ID and ADZUNA_APP_KEY) else "❌ missing")
    st.caption(
        "This app uses official job-board/public API endpoints. "
        "LinkedIn/Indeed/Glassdoor public scraping is intentionally not used."
    )

    resume_file = st.file_uploader("Upload resume", type=["pdf", "docx", "txt", "md"])
    if resume_file is not None:
        try:
            st.session_state.resume_text = extract_resume_text(resume_file)
        except Exception as exc:
            st.error(f"Failed to read resume: {exc}")

    query = st.text_input("Job keywords", value="python")
    location = st.text_input("Location", value="Vancouver, BC, Canada")
    days_old = st.slider("Max days old", 1, 30, 30)
    distance_km = st.slider("Search radius (km)", 1, 100, 50)
    greenhouse_boards = st.text_input("Greenhouse board tokens (comma-separated, optional)", value="")
    lever_slugs = st.text_input("Lever company slugs (comma-separated, optional)", value="")

    fetch_btn = st.button("Fetch live jobs", use_container_width=True)
    rank_btn = st.button("Rank with Gemini", use_container_width=True)
    clear_btn = st.button("Clear results", use_container_width=True)

    if clear_btn:
        st.session_state.jobs_df = pd.DataFrame(columns=COLUMNS)
        st.session_state.ranked_df = pd.DataFrame(columns=COLUMNS)
        st.session_state.fetch_status = ""
        st.session_state.application_packet = ""
        st.rerun()

    st.subheader("Tips")
    st.markdown(
        """
- Start broad: `python`, `data`, `software engineer`
- Keep radius high for Vancouver: 50 km works better than 5 km
- Use `Max days old = 30` to avoid zero-result fetches
"""
    )

resume_text = st.session_state.resume_text.strip()

left, right = st.columns([1.45, 1])

with left:
    st.subheader("Resume")
    if resume_text:
        st.text_area("Extracted resume text", resume_text, height=240)
    else:
        st.info("Upload your resume to begin.")

    st.subheader("Live jobs")
    if fetch_btn:
        with st.spinner("Fetching live jobs..."):
            jobs_df = load_jobs_from_sources(
                query=query,
                location=location,
                days_old=days_old,
                distance_km=distance_km,
                greenhouse_boards=greenhouse_boards,
                lever_slugs=lever_slugs,
            )
        st.session_state.jobs_df = jobs_df
        st.session_state.ranked_df = pd.DataFrame(columns=COLUMNS)
        st.session_state.application_packet = ""
        st.session_state.fetch_status = f"Loaded {len(jobs_df)} jobs at {datetime.now().strftime('%H:%M:%S')}"
        st.rerun()

    if st.session_state.fetch_status:
        st.success(st.session_state.fetch_status)

    jobs_df = st.session_state.jobs_df
    if not jobs_df.empty:
        show_cols = ["title", "company", "location", "source", "url"]
        show_cols = [c for c in show_cols if c in jobs_df.columns]
        st.dataframe(jobs_df[show_cols], use_container_width=True, hide_index=True)
        st.download_button(
            "Download fetched jobs as CSV",
            data=jobs_df.to_csv(index=False).encode("utf-8"),
            file_name="fetched_jobs.csv",
            mime="text/csv",
        )
    else:
        st.info("No live jobs loaded yet.")

with right:
    st.subheader("Gemini ranking")

    if rank_btn:
        if not resume_text:
            st.error("Upload a resume first.")
        elif st.session_state.jobs_df.empty:
            st.error("Fetch jobs first.")
        elif not API_KEY:
            st.error("Set GEMINI_API_KEY in .env.")
        else:
            with st.spinner("Ranking jobs with Gemini..."):
                service = GeminiService(api_key=API_KEY, model=MODEL)
                ranked = service.rank_jobs(
                    resume_text,
                    st.session_state.jobs_df.to_dict(orient="records"),
                    location=location,
                )
                st.session_state.ranked_df = pd.DataFrame(ranked)
                st.session_state.application_packet = ""
            st.rerun()

    ranked_df = st.session_state.ranked_df
    if not ranked_df.empty:
        display_cols = ["score", "title", "company", "location", "source", "reason"]
        display_cols = [c for c in display_cols if c in ranked_df.columns]
        st.dataframe(ranked_df[display_cols], use_container_width=True, hide_index=True)

        selected_index = st.selectbox(
            "Select a job",
            options=list(ranked_df.index),
            format_func=lambda idx: f"{ranked_df.loc[idx, 'title']} — {ranked_df.loc[idx, 'company']} ({ranked_df.loc[idx, 'score']})",
        )

        if st.button("Generate application packet", use_container_width=True):
            if not API_KEY:
                st.error("Set GEMINI_API_KEY in .env.")
            else:
                service = GeminiService(api_key=API_KEY, model=MODEL)
                st.session_state.application_packet = service.generate_application_packet(
                    resume_text,
                    ranked_df.loc[selected_index].to_dict(),
                )
                st.rerun()

        if st.session_state.application_packet:
            st.text_area("Application packet", st.session_state.application_packet, height=320)
            st.download_button(
                "Download packet",
                data=st.session_state.application_packet.encode("utf-8"),
                file_name="application_packet.md",
                mime="text/markdown",
            )
    else:
        st.info("Rank results will appear here.")