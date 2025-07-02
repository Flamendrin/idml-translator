# IDML Translator

A simple Flask application for translating IDML (InDesign Markup Language) files using the OpenAI API. Upload one or more `.idml` files, select the source and target languages, and download translated files when ready.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set the environment variables `OPENAI_API_KEY`, and optionally `FLASK_SECRET_KEY`, `APP_PASSWORD` and `OPENAI_MODEL` (default `gpt-4`).
3. Run the app:
   ```bash
   python app.py
   ```

The web UI includes a drop-down to select the chat model for each translation job.

## Tests

Run tests with:
```bash
pytest
```
