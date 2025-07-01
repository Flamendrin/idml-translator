import io
import os
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault("OPENAI_API_KEY", "test")
import app as app_module
app = app_module.app


def test_index_non_idml_file_shows_error_message():
    client = app.test_client()
    data = {
        'idml_file': (io.BytesIO(b'dummy'), 'test.txt')
    }
    response = client.post('/', data=data, content_type='multipart/form-data')
    assert "❌ Prosím nahraj platný .idml soubor." in response.get_data(as_text=True)


def test_translation_job_progress(monkeypatch):
    progress_values = []

    def fake_batch(texts, langs, src, prompt):
        time.sleep(0.05)
        return {lang: ["x" for _ in texts] for lang in langs}

    monkeypatch.setattr(app_module, "batch_translate", fake_batch)

    client = app.test_client()
    resp = client.post(
        "/start-job",
        json={"texts": ["a", "b"], "languages": ["en"], "source_lang": "cs", "prompt": "p"},
    )
    job_id = resp.get_json()["job_id"]
    while True:
        r = client.get(f"/progress/{job_id}")
        p = r.get_json()["progress"]
        progress_values.append(p)
        if p == 100:
            break
        time.sleep(0.02)
    assert progress_values[0] <= progress_values[-1]
    assert progress_values[-1] == 100
    assert sorted(progress_values) == progress_values


def test_prompt_passed_to_batch_translate(monkeypatch):
    captured = {}

    def fake_batch(texts, langs, src, prompt):
        captured["prompt"] = prompt
        return {lang: ["x" for _ in texts] for lang in langs}

    monkeypatch.setattr(app_module, "batch_translate", fake_batch)

    client = app.test_client()
    resp = client.post(
        "/start-job",
        json={"texts": ["hello"], "languages": ["en"], "source_lang": "cs", "prompt": "Custom"},
    )
    job_id = resp.get_json()["job_id"]
    while True:
        if client.get(f"/progress/{job_id}").get_json()["progress"] == 100:
            break
        time.sleep(0.02)
    assert captured.get("prompt") == "Custom"
