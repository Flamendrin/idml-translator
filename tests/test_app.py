import io
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault("OPENAI_API_KEY", "test")
from app import app


def test_index_non_idml_file_shows_error_message():
    client = app.test_client()
    data = {
        'idml_file': (io.BytesIO(b'dummy'), 'test.txt')
    }
    response = client.post('/', data=data, content_type='multipart/form-data')
    assert "❌ Prosím nahraj platný .idml soubor." in response.get_data(as_text=True)
