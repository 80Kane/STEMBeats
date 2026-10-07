import os
import uuid
import threading
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from separator import StemSeparator
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE_MB', 50)) * 1024 * 1024
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'aac', 'm4a', 'ogg'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

jobs = {}
separator = StemSeparator(model=os.getenv('SEPARATOR_MODEL', 'spleeter'))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/separate', methods=['POST'])
def separate():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid or unsupported file type'}), 400
    job_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    input_path = os.path.join(UPLOAD_FOLDER, f'{job_id}_{filename}')
    file.save(input_path)
    jobs[job_id] = {'status': 'processing', 'progress': 0, 'filename': filename, 'stems': {}}
    thread = threading.Thread(target=run_separation, args=(job_id, input_path))
    thread.daemon = True
    thread.start()
    return jsonify({'job_id': job_id, 'status': 'processing', 'progress': 0, 'estimated_time': '30-60s'}), 202


def run_separation(job_id, input_path):
    try:
        output_dir = os.path.join(OUTPUT_FOLDER, job_id)
        os.makedirs(output_dir, exist_ok=True)
        def progress_callback(pct):
            jobs[job_id]['progress'] = pct
        stems = separator.separate(input_path, output_dir, progress_callback)
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['progress'] = 100
        jobs[job_id]['stems'] = stems
        os.remove(input_path)
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)


@app.route('/api/status/<job_id>', methods=['GET'])
def status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(jobs[job_id])


@app.route('/api/stems/<job_id>', methods=['GET'])
def get_stems(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    if jobs[job_id]['status'] != 'completed':
        return jsonify({'error': 'Job not yet completed'}), 400
    files = []
    for stem_name, path in jobs[job_id]['stems'].items():
        files.append({'stem': stem_name, 'url': f'/api/download/{job_id}/{stem_name}',
                      'size_mb': round(os.path.getsize(path) / (1024 * 1024), 2)})
    return jsonify({'job_id': job_id, 'stems': files})


@app.route('/api/download/<job_id>/<stem_name>', methods=['GET'])
def download_stem(job_id, stem_name):
    if job_id not in jobs or stem_name not in jobs[job_id]['stems']:
        return jsonify({'error': 'Stem not found'}), 404
    path = jobs[job_id]['stems'][stem_name]
    return send_file(path, as_attachment=True, download_name=f'{stem_name}.wav')


@app.route('/api/cleanup/<job_id>', methods=['DELETE'])
def cleanup(job_id):
    import shutil
    stem_dir = os.path.join(OUTPUT_FOLDER, job_id)
    if os.path.exists(stem_dir):
        shutil.rmtree(stem_dir)
    if job_id in jobs:
        del jobs[job_id]
    return jsonify({'message': 'Cleaned up successfully'})


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'model': separator.model_name})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
