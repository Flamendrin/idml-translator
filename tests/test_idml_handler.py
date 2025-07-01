import zipfile
import pytest

from translator.idml_handler import extract_idml, ExtractionError


def create_zip(files, path):
    with zipfile.ZipFile(path, 'w') as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def test_extract_idml_extracts_files(tmp_path):
    zip_path = tmp_path / "test.idml"
    create_zip({"test.txt": "content"}, zip_path)

    output_dir = tmp_path / "out"
    extract_idml(zip_path, output_dir)

    assert (output_dir / "test.txt").read_text() == "content"


def test_extract_idml_prevents_path_traversal(tmp_path):
    zip_path = tmp_path / "evil.idml"
    create_zip({"../evil.txt": "bad"}, zip_path)

    with pytest.raises(ExtractionError):
        extract_idml(zip_path, tmp_path / "out")

