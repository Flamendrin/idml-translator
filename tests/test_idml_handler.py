import zipfile
import pytest

from translator.idml_handler import (
    extract_idml,
    ExtractionError,
    repackage_idml,
    copy_unpacked_dir,
)


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


def test_repackage_idml_roundtrip(tmp_path):
    src = tmp_path / "src"
    (src / "Stories").mkdir(parents=True)
    (src / "Stories" / "story.xml").write_text("<Root/>")
    out = tmp_path / "out.idml"
    repackage_idml(src, out)
    assert zipfile.is_zipfile(out)
    with zipfile.ZipFile(out) as zf:
        assert "Stories/story.xml" in zf.namelist()


def test_copy_unpacked_dir_overwrites(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("ok")
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.txt").write_text("old")
    copy_unpacked_dir(src, dest)
    assert (dest / "a.txt").read_text() == "ok"

