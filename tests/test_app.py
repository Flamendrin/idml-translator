import io
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault("OPENAI_API_KEY", "test")
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
