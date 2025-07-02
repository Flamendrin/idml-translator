# IDML Translator

A simple Flask application for translating IDML (InDesign Markup Language) files using the OpenAI API. Upload one or more `.idml` files, select the source and target languages, and download translated files when ready.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set the environment variables `OPENAI_API_KEY`, and optionally `FLASK_SECRET_KEY`, `APP_PASSWORD` and `OPENAI_MODEL` (default `gpt-4o`).
3. Run the app:
   ```bash
   python app.py
   ```

The web UI includes a drop-down to select the chat model for each translation job.

When IDML files and target languages are selected the page now displays an
estimate of the number of tokens that will be sent to the OpenAI API along with
the approximate price based on the chosen model.  This uses the ``/estimate``
endpoint and ``translator/token_estimator.py`` helper.

## Tests

Run tests with:
```bash
pytest
```
