# Example Workflow

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and add your own DeepSeek API key if you want translation or AI interpretation.
4. Run `python ingest.py` to fetch public article metadata.
5. Run `streamlit run app.py` to browse, read, star, annotate, translate, and interpret selected articles.

The local SQLite database is created automatically at `data/articles.sqlite` and is intentionally ignored by Git.
