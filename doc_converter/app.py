import os
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
from datetime import datetime
import scripts.convert_to_txt as converter

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'input_docs')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), 'output_txt')
ALLOWED_EXTENSIONS = {'.txt', '.md', '.pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported file type'}), 400
    filename = secure_filename(file.filename)
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(upload_path)
    # Call conversion logic
    try:
        converter.convert_file(upload_path, app.config['OUTPUT_FOLDER'])
    except Exception as e:
        return jsonify({'error': f'Conversion failed: {e}'}), 500
    return jsonify({'success': True})

@app.route('/files')
def files():
    uploaded = []
    for fname in os.listdir(app.config['UPLOAD_FOLDER']):
        if allowed_file(fname):
            fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            uploaded.append({
                'name': fname,
                'time': datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M')
            })
    converted = []
    for fname in os.listdir(app.config['OUTPUT_FOLDER']):
        if fname.endswith('.txt'):
            fpath = os.path.join(app.config['OUTPUT_FOLDER'], fname)
            converted.append({
                'name': fname,
                'time': datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M')
            })
    return jsonify({'uploaded': sorted(uploaded, key=lambda x: x['time'], reverse=True),
                    'converted': sorted(converted, key=lambda x: x['time'], reverse=True)})

@app.route('/view/<filename>')
def view_file(filename):
    safe_name = secure_filename(filename)
    fpath = os.path.join(app.config['OUTPUT_FOLDER'], safe_name)
    if not os.path.exists(fpath):
        abort(404)
    with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read(10000)  # Limit preview size
    return content

@app.route('/download/<filename>')
def download_file(filename):
    safe_name = secure_filename(filename)
    return send_from_directory(app.config['OUTPUT_FOLDER'], safe_name, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
