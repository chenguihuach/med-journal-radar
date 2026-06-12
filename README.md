# Med Journal Radar

A local Streamlit app for tracking new articles from top medical journals, displaying bilingual article information, and providing on-demand AI-powered structured interpretation.

## Features

- Fetch latest articles from top medical journals via RSS
- Store article metadata locally in SQLite
- Display English and Chinese titles/abstracts
- Translate article information with DeepSeek API
- Manually trigger AI interpretation for selected articles
- Extract study design, sample size, AI/statistical method, main results, and clinical relevance
- Mark articles as read/starred and add notes
- No automatic full-text scraping and no paywall bypassing

## Supported Journals

- Nature
- Nature Medicine
- The Lancet
- JAMA
- NEJM
- The Lancet Digital Health
- npj Digital Medicine

The journal list is editable in `config/journals.yaml`. Each journal can define RSS feed URLs, a homepage URL, an RSS page URL, or a PubMed fallback query.

## Installation

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS or Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
```

## Configuration

Copy the template file:

```powershell
copy .env.example .env
```

On macOS or Linux:

```bash
cp .env.example .env
```

Then edit `.env` and add your own DeepSeek API key:

```dotenv
DEEPSEEK_API_KEY=
```

Article fetching works without a DeepSeek API key. Translation and AI interpretation require `DEEPSEEK_API_KEY`.

Optional settings:

- `DEEPSEEK_BASE_URL`: DeepSeek-compatible API base URL
- `DEEPSEEK_MODEL`: model name used for translation and interpretation
- `NCBI_API_KEY`: optional NCBI API key for higher PubMed rate limits
- `CROSSREF_MAILTO`: optional contact email sent to Crossref and NCBI services
- `APP_USER_AGENT`: user agent used for public metadata requests

## Run The App

```powershell
streamlit run app.py
```

## Fetch Latest Articles

```powershell
python ingest.py
```

By default, ingestion fetches public metadata and stores it in `data/articles.sqlite`. It does not translate articles automatically unless you pass `--translate`.

## Translate Missing Chinese Information

```powershell
python translate_missing.py
```

You can limit the number of articles:

```powershell
python translate_missing.py --limit 30
```

## How AI Interpretation Works

AI interpretation is only called after you click the interpretation button in the Streamlit app. The request is sent to DeepSeek using the article title, abstract, journal name, article type, publication date, and available metadata.

The interpretation is a structured summary based on metadata and abstracts only. It is not a full-text review, does not replace clinical judgment, and may miss details that are only available in the full article.

## Privacy And Safety

This app stores your local reading state, notes, starred articles, translations, and interpretation results in a local SQLite database at `data/articles.sqlite`. That database is ignored by Git and should not be uploaded to GitHub.

The `.env` file is also ignored by Git. Do not commit your DeepSeek API key, GitHub token, NCBI API key, private email address, logs, cache files, virtual environments, or local database files.

Only `.env.example` is included as a safe configuration template.

## Compliance

Med Journal Radar does not scrape paid full text, bypass paywalls, or automatically download PDFs. It only processes public metadata such as titles, abstracts, DOI, PMID, journal names, publication dates, and article URLs from RSS feeds, PubMed, Crossref, and publisher metadata pages.

Users are responsible for following journal website terms, API usage policies, and institutional access rules.

## Troubleshooting

### Missing API Key

If translation or AI interpretation says the DeepSeek API key is missing, copy `.env.example` to `.env` and set `DEEPSEEK_API_KEY` to your own key. Fetching RSS metadata still works without a key.

### RSS Feed Unavailable

Some publisher feeds may temporarily fail or return no entries. Ingestion records the failure in the local `fetch_logs` table and continues with other journals. Try again later, or edit `config/journals.yaml` to update the feed URL.

### SQLite Database Not Found

The app creates `data/articles.sqlite` automatically when you run `streamlit run app.py`, `python ingest.py`, or `python translate_missing.py`. Make sure the `data/` directory exists; this repository includes `data/.gitkeep` for that purpose.

### UNIQUE Constraint Failed

The ingestion pipeline uses upsert logic based on DOI, URL, and title/journal. If you still see a unique constraint error, it usually means an upstream feed changed identifiers in an unusual way. Re-run ingestion; repeated items should be updated instead of inserted.

### DeepSeek JSON Parsing Failed

DeepSeek responses are expected to be JSON. If parsing fails, the app marks the interpretation as failed and stores the raw response in the local database for debugging. You can retry the interpretation from the app after checking the prompt or model setting.
