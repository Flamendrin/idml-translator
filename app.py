from flask import (
    Flask,
    request,
    render_template,
    send_from_directory,
    redirect,
    url_for,
    session,
    jsonify,
)
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
from translator.openai_client import (
    batch_translate,
    DEFAULT_PROMPT,
    get_remaining_credit,
)
from translator.token_estimator import (
    count_tokens,
    estimate_cost,
    MODEL_RATES,
    estimate_total_tokens,
)
import shutil
import time
import threading
import tempfile

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "devsecret")
PASSWORD = os.environ.get("APP_PASSWORD", "banana")
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULT_FOLDER'] = 'results'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

# Track progress for background jobs
JOB_PROGRESS: dict[str, dict] = {}

# Tokens consumed by the most recent translation job
LAST_TOKENS_USED = 0

# Automatically remove old uploaded and result files
MAX_FILE_AGE = 60 * 60  # seconds
_CLEANUP_INTERVAL = 60 * 60


def _cleanup_old_files(path: str) -> None:
    """Remove files older than ``MAX_FILE_AGE`` from ``path``."""

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
    """Periodically purge old files and job metadata."""

    while True:
        _cleanup_old_files(app.config['UPLOAD_FOLDER'])
        _cleanup_old_files(app.config['RESULT_FOLDER'])
        _cleanup_old_jobs()
        time.sleep(_CLEANUP_INTERVAL)


threading.Thread(target=_cleanup_worker, daemon=True).start()


@app.template_filter('datetimeformat')
def datetimeformat(value: float) -> str:
    """Format a timestamp for display."""
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(value))


@app.before_request
def _require_login():
    if app.config.get("TESTING"):
        return
    if request.endpoint in {"login", "static"}:
        return
    if session.get("logged_in"):
        return
    return redirect(url_for("login"))

try:
    import pycountry  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pycountry = None

LANGUAGE_NAMES = {
    'cs': 'Czech',
    'sk': 'Slovak',
    'pl': 'Polish',
    'en': 'English',
    'de': 'German',
    'hu': 'Hungarian',
}
if pycountry:
    LANGUAGE_NAMES.update(
        {
            lang.alpha_2: lang.name
            for lang in pycountry.languages
            if hasattr(lang, "alpha_2")
        }
    )


def _run_translation_job(
    job_id: str,
    files: list[tuple[str, str]],
    selected_languages: list[str],
    source_lang: str,
    system_prompt: str | None,
    model: str,
) -> None:
    """Background worker that translates uploaded files."""
    links: list[tuple[str, str, str]] = []  # (lang, url, filename)
    total_steps = 0
    for file_path, _ in files:
        extract_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'unpacked_original')
        extract_idml(file_path, extract_dir)
        total_steps += len(find_story_files(extract_dir))

    steps_done = 0

    global LAST_TOKENS_USED
    tokens_used = 0

    def _add_tokens(count: int) -> None:
        nonlocal tokens_used
        tokens_used += count

    for file_path, base_name in files:
        extract_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'unpacked_original')
        extract_idml(file_path, extract_dir)

        story_files = find_story_files(extract_dir)

        all_contents = []
        all_texts = []
        for story_path in story_files:
            tree = load_story_xml(story_path)
            contents = extract_content_elements(tree)
            all_contents.append((story_path, tree, contents))
            for _, text, _ in contents:
                all_texts.append(text)

        def _progress(pct: int) -> None:
            JOB_PROGRESS[job_id]["progress"] = int(pct * 0.9)

        translations_by_lang = batch_translate(
            all_texts,
            selected_languages,
            source_lang,
            system_prompt,
            progress_callback=_progress,
            tokens_callback=_add_tokens,
            model=model,
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
            links.append((lang, f'/download/{output_file}', output_file))

        steps_done += len(story_files)
        JOB_PROGRESS[job_id]["progress"] = int((steps_done / max(1, total_steps)) * 100)

    JOB_PROGRESS[job_id]["progress"] = 100
    JOB_PROGRESS[job_id]["links"] = links
    JOB_PROGRESS[job_id]["expires_at"] = JOB_PROGRESS[job_id]["timestamp"] + MAX_FILE_AGE
    JOB_PROGRESS[job_id]["tokens"] = tokens_used
    LAST_TOKENS_USED = tokens_used


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        error = 'Nesprávné heslo.'
    return render_template('login.html', error=error)

@app.route('/', methods=['GET', 'POST'])
def index():
    completed_jobs = [
        {
            "id": jid,
            "links": info.get("links", []),
            "timestamp": info.get("timestamp", 0),
        }
        for jid, info in JOB_PROGRESS.items()
        if info.get("progress") == 100
    ]
    completed_jobs.sort(key=lambda j: j["timestamp"], reverse=True)
    if request.method == 'POST':
        uploaded_files = request.files.getlist('idml_files')
        selected_languages = request.form.getlist('languages')
        source_lang = request.form.get('source_lang')
        system_prompt = request.form.get('prompt', '').strip() or None
        selected_model = request.form.get('model', DEFAULT_MODEL)

        if not uploaded_files or any(not f.filename.endswith('.idml') for f in uploaded_files):
            return render_template('index.html', error="❌ Prosím nahraj platný .idml soubor.", selected_model=selected_model)

        if source_lang in selected_languages:
            selected_languages.remove(source_lang)

        job_id = str(uuid.uuid4())
        JOB_PROGRESS[job_id] = {"timestamp": time.time(), "progress": 0, "prompt": system_prompt or DEFAULT_PROMPT}

        file_info = []
        for uploaded_file in uploaded_files:
            filename = secure_filename(uploaded_file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            uploaded_file.save(file_path)
            base_name = os.path.splitext(filename)[0]
            file_info.append((file_path, base_name))

        thread = threading.Thread(
            target=_run_translation_job,
            args=(job_id, file_info, selected_languages, source_lang, system_prompt, selected_model),
            daemon=True,
        )
        thread.start()

        return render_template(
            'index.html',
            job_id=job_id,
            prompt_text=system_prompt or DEFAULT_PROMPT,
            completed_jobs=completed_jobs,
            lang_names=LANGUAGE_NAMES,
            selected_model=selected_model,
        )

    job_id = request.args.get('job')
    if job_id:
        info = JOB_PROGRESS.get(job_id)
        if info and info.get('progress') < 100:
            return render_template(
                'index.html',
                job_id=job_id,
                prompt_text=info.get('prompt', DEFAULT_PROMPT),
                completed_jobs=completed_jobs,
                lang_names=LANGUAGE_NAMES,
                selected_model=DEFAULT_MODEL,
            )

    return render_template(
        'index.html',
        prompt_text=DEFAULT_PROMPT,
        completed_jobs=completed_jobs,
        lang_names=LANGUAGE_NAMES,
        selected_model=DEFAULT_MODEL,
    )

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['RESULT_FOLDER'], filename, as_attachment=True)


@app.route('/estimate', methods=['POST'])
def estimate():
    """Return a rough token and cost estimate for uploaded files."""
    uploaded_files = request.files.getlist('idml_files')
    selected_languages = request.form.getlist('languages')
    model = request.form.get('model', DEFAULT_MODEL)

    if not uploaded_files or any(not f.filename.endswith('.idml') for f in uploaded_files):
        return jsonify({'error': 'invalid file'}), 400

    texts: list[str] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for uploaded_file in uploaded_files:
            fname = secure_filename(uploaded_file.filename)
            idml_path = os.path.join(tmpdir, fname)
            uploaded_file.save(idml_path)
            extract_dir = os.path.join(tmpdir, 'extract')
            extract_idml(idml_path, extract_dir)
            for story_path in find_story_files(extract_dir):
                tree = load_story_xml(story_path)
                contents = extract_content_elements(tree)
                for _, txt, _ in contents:
                    texts.append(txt)

    texts = list(dict.fromkeys(texts))
    tokens = estimate_total_tokens(texts, model, len(selected_languages))
    cost = estimate_cost(tokens, model)
    return jsonify({'tokens': tokens, 'cost': round(cost, 4)})


@app.route('/credit')
def credit():
    """Return remaining credit for the configured API key."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return jsonify({'credit': None, 'error': 'unavailable'})
    value = get_remaining_credit()
    if value is None:
        return jsonify({'credit': None, 'error': 'unavailable'})
    return jsonify({'credit': value})


@app.route('/tokens')
def tokens():
    """Return number of tokens used in the most recent translation job."""
    return jsonify({'tokens': LAST_TOKENS_USED})


@app.route('/progress/<job_id>')
def progress(job_id: str):
    """Return progress information for a running job."""
    info = JOB_PROGRESS.get(job_id)
    if not info:
        return jsonify({'progress': 100, 'links': []})
    return jsonify({'progress': info.get('progress', 0), 'links': info.get('links'), 'expires_at': info.get('expires_at')})


@app.route('/translations')
def translations():
    """Return metadata about completed translation jobs."""
    completed_jobs = [
        {
            "id": jid,
            "links": info.get("links", []),
            "timestamp": info.get("timestamp", 0),
        }
        for jid, info in JOB_PROGRESS.items()
        if info.get("progress") == 100
    ]
    completed_jobs.sort(key=lambda j: j["timestamp"], reverse=True)
    return jsonify(completed_jobs)


@app.route('/remove/<job_id>', methods=['POST'])
def remove_job(job_id: str):
    """Delete result files associated with a finished job."""
    info = JOB_PROGRESS.pop(job_id, None)
    if info and info.get('links'):
        for _, _, fname in info['links']:
            path = os.path.join(app.config['RESULT_FOLDER'], fname)
            with contextlib.suppress(FileNotFoundError):
                os.remove(path)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
