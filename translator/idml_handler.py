import zipfile
import os
import shutil
from pathlib import Path

def extract_idml(idml_path, output_dir):
    """
    Rozbalí .idml soubor do output_dir
    """
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    with zipfile.ZipFile(idml_path, 'r') as zip_ref:
        zip_ref.extractall(output_dir)

def find_story_files(unpacked_dir):
    """
    Vrátí seznam XML souborů z podsložky 'Stories'
    """
    stories_path = Path(unpacked_dir) / 'Stories'
    return list(stories_path.glob('*.xml'))

def repackage_idml(source_dir, output_idml_path):
    """
    Zabalí zpět do .idml (ZIP) souboru
    """
    with zipfile.ZipFile(output_idml_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for foldername, subfolders, filenames in os.walk(source_dir):
            for filename in filenames:
                filepath = os.path.join(foldername, filename)
                relpath = os.path.relpath(filepath, source_dir)
                zipf.write(filepath, arcname=relpath)

def copy_unpacked_dir(source_dir, target_dir):
    """
    Zkopíruje celý rozbalený adresář (např. pro další jazykovou variantu)
    """
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
