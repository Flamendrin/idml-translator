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

The app tracks how many OpenAI tokens were consumed by the most recent
translation job. This is exposed via the ``/tokens`` endpoint and shown under
the model selector on the main page.

When IDML files and target languages are selected the page now displays an
estimate of the number of tokens that will be sent to the OpenAI API along with
the approximate price based on the chosen model.  This uses the ``/estimate``
endpoint and ``translator/token_estimator.py`` helper.

## Async mode and large jobs

Translations run in a background thread on the server. You can therefore lock
your computer or close the browser tab and the process will keep running as long
as the Flask application stays online.

Setting the environment variable ``USE_ASYNC_TRANSLATE=1`` switches the
background worker to the asynchronous ``async_batch_translate`` implementation
which issues OpenAI requests concurrently.  For large documents you can also
adjust ``MAX_BATCH_TOKENS`` (default ``800``) to control how many tokens are sent
in each API call.  Higher values reduce the number of requests but must remain
within the selected model's context limit.

## Tests and style

Install test dependencies and run style checks with:
```bash
pip install -r requirements.txt
flake8
pytest
```
The included GitHub Actions workflow also runs these commands on every push.
