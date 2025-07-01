from flask import Flask, request, render_template, send_from_directory
import os
from werkzeug.utils import secure_filename
import contextlib
import uuid

from translator.idml_handler import (
    extract_idml,
    find_story_files,
    repackage_idml,
    copy_unpacked_dir
)
from translator.text_extractor import (
    load_story_xml,
    extract_content_elements,
    update_content_elements,
    save_story_xml
)
from translator.openai_client import batch_translate, DEFAULT_PROMPT
import shutil
import time
import threading

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULT_FOLDER'] = 'results'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

# Track progress for background jobs
JOB_PROGRESS: dict[str, dict] = {}

# Automatically remove old uploaded and result files
MAX_FILE_AGE = 60 * 60  # seconds
_CLEANUP_INTERVAL = 60 * 60


def _cleanup_old_files(path: str) -> None:
    now = time.time()
    for name in os.listdir(path):
        file_path = os.path.join(path, name)
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            continue
        if now - mtime > MAX_FILE_AGE:
            if os.path.isdir(file_path):
                shutil.rmtree(file_path, ignore_errors=True)
            else:
                with contextlib.suppress(FileNotFoundError):
                    os.remove(file_path)


def _cleanup_old_jobs() -> None:
    """Remove stale entries from JOB_PROGRESS."""
    now = time.time()
    stale = [job for job, info in JOB_PROGRESS.items() if now - info.get('timestamp', now) > MAX_FILE_AGE]
    for job in stale:
        JOB_PROGRESS.pop(job, None)


def _cleanup_worker() -> None:
    while True:
        _cleanup_old_files(app.config['UPLOAD_FOLDER'])
        _cleanup_old_files(app.config['RESULT_FOLDER'])
        _cleanup_old_jobs()
        time.sleep(_CLEANUP_INTERVAL)


threading.Thread(target=_cleanup_worker, daemon=True).start()

LANGUAGE_NAMES = {
    'cs': 'Čeština',
    'sk': 'Slovenština',
    'pl': 'Polština',
    'en': 'Angličtina',
    'de': 'Němčina',
    'hu': 'Maďarština'
}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        uploaded_file = request.files.get('idml_file')
        selected_languages = request.form.getlist('languages')
        source_lang = request.form.get('source_lang')
        system_prompt = request.form.get('prompt', '').strip() or None

        if not uploaded_file or not uploaded_file.filename.endswith('.idml'):
            return render_template('index.html', error="❌ Prosím nahraj platný .idml soubor.")

        if source_lang in selected_languages:
            selected_languages.remove(source_lang)

        job_id = str(uuid.uuid4())
        JOB_PROGRESS[job_id] = {"timestamp": time.time(), "progress": 0}

        filename = secure_filename(uploaded_file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        uploaded_file.save(file_path)

        base_name = os.path.splitext(filename)[0]
        extract_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'unpacked_original')
        extract_idml(file_path, extract_dir)

        story_files = find_story_files(extract_dir)

        all_contents = []
        all_texts = []
        for story_path in story_files:
            tree = load_story_xml(story_path)
            contents = extract_content_elements(tree)
            all_contents.append((story_path, tree, contents))
            for _, text in contents:
                all_texts.append(text)

        translations_by_lang = batch_translate(
            all_texts,
            selected_languages,
            source_lang,
            system_prompt,
        )

        for lang in selected_languages:
            lang_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'unpacked_{lang}')
            copy_unpacked_dir(extract_dir, lang_dir)

            index = 0
            for story_path, _, contents in all_contents:
                rel_path = os.path.relpath(story_path, extract_dir)
                new_story_path = os.path.join(lang_dir, rel_path)

                tree = load_story_xml(new_story_path)
                local_contents = extract_content_elements(tree)

                translations = translations_by_lang[lang][index : index + len(local_contents)]
                update_content_elements(local_contents, translations)
                save_story_xml(tree, new_story_path)

                index += len(local_contents)

            output_file = f"{base_name}-{lang}.idml"
            output_path = os.path.join(app.config['RESULT_FOLDER'], output_file)
            repackage_idml(lang_dir, output_path)

        JOB_PROGRESS[job_id]["progress"] = 100

        links = [
            (lang, f'/download/{base_name}-{lang}.idml')
            for lang in selected_languages
        ]
        return render_template(
            'index.html',
            links=links,
            lang_names=LANGUAGE_NAMES,
            prompt_text=system_prompt or DEFAULT_PROMPT
        )

    return render_template('index.html', prompt_text=DEFAULT_PROMPT)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['RESULT_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
