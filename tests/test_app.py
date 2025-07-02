import io
import os
import sys
import zipfile
import threading

from translator import token_estimator
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault("OPENAI_API_KEY", "test")
import app as app_module
from app import app, JOB_PROGRESS, _cleanup_old_jobs, MAX_FILE_AGE
app.config['TESTING'] = True
import time


def test_index_non_idml_file_shows_error_message():
    client = app.test_client()
    data = {
        'idml_files': [(io.BytesIO(b'dummy'), 'test.txt')]
    }
    response = client.post('/', data=data, content_type='multipart/form-data')
    assert "❌ Prosím nahraj platný .idml soubor." in response.get_data(as_text=True)


def test_cleanup_old_jobs_removes_stale_entries():
    JOB_PROGRESS.clear()
    JOB_PROGRESS['old'] = {'timestamp': time.time() - (MAX_FILE_AGE + 1), 'progress': 0}
    JOB_PROGRESS['new'] = {'timestamp': time.time(), 'progress': 0}

    _cleanup_old_jobs()

    assert 'old' not in JOB_PROGRESS
    assert 'new' in JOB_PROGRESS


def test_index_template_has_autoscroll_script():
    path = os.path.join('templates', 'index.html')
    with open(path, encoding='utf-8') as f:
        html = f.read()
    assert 'scrollIntoView' in html


def test_translations_endpoint_returns_json():
    JOB_PROGRESS.clear()
    JOB_PROGRESS['job'] = {
        'progress': 100,
        'timestamp': 1,
        'links': [('cs', '/download/file.idml', 'file.idml')],
    }
    client = app.test_client()
    response = client.get('/translations')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert data[0]['id'] == 'job'


def _create_idml(path: str) -> None:
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('mimetype', '')
        zf.writestr('Stories/story.xml', '<Root><Content>Hello</Content></Root>')


def test_index_passes_selected_model(monkeypatch, tmp_path):
    called = {}

    def fake_run(job_id, files, langs, src, prompt, model):
        called['model'] = model

    class DummyThread:
        def __init__(self, target, args=(), daemon=None):
            self.target = target
            self.args = args
        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(app_module, '_run_translation_job', fake_run)
    monkeypatch.setattr(threading, 'Thread', DummyThread)

    idml_path = tmp_path / 't.idml'
    _create_idml(idml_path)

    client = app.test_client()
    data = {
        'idml_files': [(open(idml_path, 'rb'), 't.idml')],
        'languages': 'cs',
        'source_lang': 'en',
        'model': 'gpt-3.5-turbo',
    }
    client.post('/', data=data, content_type='multipart/form-data')
    assert called.get('model') == 'gpt-3.5-turbo'


def test_estimate_route(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, 'count_tokens', lambda texts, model: 1000)
    idml_path = tmp_path / 'e.idml'
    _create_idml(idml_path)
    client = app.test_client()
    data = {
        'idml_files': [(open(idml_path, 'rb'), 'e.idml')],
        'languages': ['cs', 'de'],
        'model': 'gpt-4o',
    }
    resp = client.post('/estimate', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    result = resp.get_json()
    expected = round(token_estimator.estimate_cost(1000, 'gpt-4o', 2), 4)
    assert result == {'tokens': 1000, 'cost': expected}
