import sys
import os
import io
import zipfile
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from translator import token_estimator  # noqa: E402
os.environ.setdefault("OPENAI_API_KEY", "test")
import app as app_module  # noqa: E402
from app import app, JOB_PROGRESS, _cleanup_old_jobs, MAX_FILE_AGE  # noqa: E402
app.config['TESTING'] = True


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


def _create_idml_duplicate(path: str) -> None:
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('mimetype', '')
        zf.writestr(
            'Stories/story.xml',
            '<Root><Content>Hi</Content><Content>Hi</Content></Root>'
        )


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
    monkeypatch.setattr(app_module, 'estimate_total_tokens', lambda texts, model, languages: 1000)
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
    expected = round(token_estimator.estimate_cost(1000, 'gpt-4o'), 4)
    assert result == {'tokens': 1000, 'cost': expected}


def test_estimate_deduplicates_texts(monkeypatch, tmp_path):
    captured = {}

    def fake_est(texts, model, languages):
        captured['texts'] = texts
        return len(texts)

    monkeypatch.setattr(app_module, 'estimate_total_tokens', fake_est)

    idml_path = tmp_path / 'dup.idml'
    _create_idml_duplicate(idml_path)

    client = app.test_client()
    data = {
        'idml_files': [(open(idml_path, 'rb'), 'dup.idml')],
        'languages': ['cs'],
        'model': 'gpt-4o',
    }
    resp = client.post('/estimate', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    result = resp.get_json()
    expected = round(token_estimator.estimate_cost(len(captured['texts']), 'gpt-4o'), 4)
    assert captured['texts'] == ['Hi']
    assert result == {'tokens': len(captured['texts']), 'cost': expected}


def test_tokens_route_returns_last_value(monkeypatch):
    app_module.LAST_TOKENS_USED = 123
    client = app.test_client()
    resp = client.get('/tokens')
    assert resp.status_code == 200

    assert resp.get_json() == {'tokens': 123}


def test_run_translation_job_async(monkeypatch, tmp_path):
    called = {}

    async def fake_async(texts, langs, src, prompt, progress_callback=None, tokens_callback=None, max_tokens=800, delay=None, model='gpt-4o'):
        called['async'] = True
        called['max'] = max_tokens
        return {lang: ['x'] * len(texts) for lang in langs}

    def fake_batch(*args, **kwargs):
        called['batch'] = True
        return {lang: ['x'] * len(args[0]) for lang in args[1]}

    monkeypatch.setattr(app_module, 'extract_idml', lambda src, dst: None)
    monkeypatch.setattr(app_module, 'find_story_files', lambda d: [tmp_path / 's.xml'])
    monkeypatch.setattr(app_module, 'load_story_xml', lambda p: None)
    monkeypatch.setattr(app_module, 'extract_content_elements', lambda tree: [(None, 't', [])])
    monkeypatch.setattr(app_module, 'update_content_elements', lambda c, t: None)
    monkeypatch.setattr(app_module, 'save_story_xml', lambda tree, p: None)
    monkeypatch.setattr(app_module, 'copy_unpacked_dir', lambda s, d: None)
    monkeypatch.setattr(app_module, 'repackage_idml', lambda s, d: None)
    monkeypatch.setattr(app_module, 'async_batch_translate', fake_async)
    monkeypatch.setattr(app_module, 'batch_translate', fake_batch)

    monkeypatch.setenv('USE_ASYNC_TRANSLATE', '1')
    monkeypatch.setenv('MAX_BATCH_TOKENS', '50')
    app_module.USE_ASYNC = True
    app_module.MAX_BATCH_TOKENS = 50

    job_id = 'j'
    JOB_PROGRESS[job_id] = {'timestamp': time.time(), 'progress': 0}
    app_module._run_translation_job(job_id, [(str(tmp_path / 'f.idml'), 'f')], ['cs'], 'en', None, 'gpt-3.5-turbo')

    assert called.get('async') is True
    assert called.get('max') == 50
    assert 'batch' not in called
