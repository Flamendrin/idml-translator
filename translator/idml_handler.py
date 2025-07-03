"""Utility helpers for working with IDML archives."""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path


class ExtractionError(Exception):
    """Raised when an invalid archive tries to escape extraction directory."""


def _safe_extract(zip_ref: zipfile.ZipFile, output_dir: str) -> None:
    """Extract ``zip_ref`` into ``output_dir`` preventing directory traversal."""
    for member in zip_ref.namelist():
        member_path = os.path.join(output_dir, member)
        abs_target = os.path.realpath(member_path)
        if not abs_target.startswith(os.path.realpath(output_dir)):
            raise ExtractionError(member)
        zip_ref.extract(member, output_dir)


def extract_idml(idml_path: str, output_dir: str) -> None:
    """Extract an IDML file into ``output_dir`` ensuring a clean directory."""
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    with zipfile.ZipFile(idml_path, "r") as zip_ref:
        _safe_extract(zip_ref, output_dir)


def find_story_files(unpacked_dir: str | Path) -> list[Path]:
    """Return the list of ``.xml`` story files contained in ``unpacked_dir``."""

    stories_path = Path(unpacked_dir) / "Stories"
    return list(stories_path.glob("*.xml"))


def repackage_idml(source_dir: str | Path, output_idml_path: str | Path) -> None:
    """Create a new IDML archive from ``source_dir``."""

    with zipfile.ZipFile(output_idml_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for foldername, _subfolders, filenames in os.walk(source_dir):
            for filename in filenames:
                filepath = os.path.join(foldername, filename)
                relpath = os.path.relpath(filepath, source_dir)
                zipf.write(filepath, arcname=relpath)


def copy_unpacked_dir(source_dir: str | Path, target_dir: str | Path) -> None:
    """Copy an unpacked IDML directory to ``target_dir``."""

    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
