# Chami-s-Job_Matcher


A Windows-friendly Streamlit app that:

- uploads a resume,
- fetches live job postings from legal sources,
- ranks them with Gemini,
- generates a tailored application packet.

## Supported live sources

- **Adzuna**: search jobs by keywords and location using the official API. Adzuna's docs say the API is RESTful, requires `app_id` and `app_key`, and supports search by keywords and locations.
- **Greenhouse job boards**: public GET endpoints for a company's board jobs without authentication.
- **Lever public posting feeds**: public career/postings feeds for companies that use Lever.

This project intentionally does **not** scrape or auto-apply on LinkedIn, Indeed, or Glassdoor. Their documented APIs are partner/employer-facing, not a general public job-seeker search/auto-apply interface.

## 1. Create `.env`

Copy `.env.example` to `.env` and fill in:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
ADZUNA_APP_ID=your_adzuna_app_id_here
ADZUNA_APP_KEY=your_adzuna_app_key_here
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Run

```bash
streamlit run app.py
```

## 4. Use

1. Upload your resume.
2. Enter a job query such as `data scientist machine learning python`.
3. Keep the location as `Vancouver, BC, Canada` or change it.
4. Click **Fetch live jobs**.
5. Click **Rank with Gemini**.
6. Select a job and generate an application packet.

## Optional public board inputs

- Greenhouse: enter board tokens like `companyname`.
- Lever: enter company slugs like `companyname`.

## Project files

- `app.py`
- `gemini_service.py`
- `job_fetchers.py`
- `resume_utils.py`
- `requirements.txt`
- `.env.example`
