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
        'idml_file': (io.BytesIO(b'dummy'), 'test.txt')
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
