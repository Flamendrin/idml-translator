from flask import Flask, request, render_template, send_from_directory
import os
from werkzeug.utils import secure_filename

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
from translator.openai_client import batch_translate

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULT_FOLDER'] = 'results'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

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

        if not uploaded_file or not uploaded_file.filename.endswith('.idml'):
            return render_template('index.html', error="❌ Prosím nahraj platný .idml soubor.")

        if source_lang in selected_languages:
            selected_languages.remove(source_lang)

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

        translations_by_lang = batch_translate(all_texts, selected_languages, source_lang)

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

        links = [
            (lang, f'/download/{base_name}-{lang}.idml')
            for lang in selected_languages
        ]
        return render_template(
            'index.html',
            links=links,
            lang_names=LANGUAGE_NAMES
        )

    return render_template('index.html')

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['RESULT_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
