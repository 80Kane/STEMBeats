import os
import uuid
import threading
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Serve frontend from ../frontend/index.html
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
STEMS_FOLDER = os.path.join(os.path.dirname(__file__), 'stems')
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'm4a', 'ogg', 'aac'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STEMS_FOLDER, exist_ok=True)

# Job tracking
jobs = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def run_separation(job_id, input_path, output_dir):
    """Run stem separation in a background thread using Demucs."""
    try:
        jobs[job_id]['status'] = 'processing'
        jobs[job_id]['progress'] = 5

        from separator import StemSeparator
        separator = StemSeparator(model='demucs')

        def progress_callback(pct):
            jobs[job_id]['progress'] = pct

        stems = separator.separate(input_path, output_dir, progress_callback)

        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['progress'] = 100
        jobs[job_id]['stems'] = stems

    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)


# ── Serve the frontend ──────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_file(os.path.join(FRONTEND_DIR, 'index.html'))


# ── Health check ────────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'model': 'demucs'})


# ── Upload & separate ───────────────────────────────────────────────────────
@app.route('/api/separate', methods=['POST'])
def separate():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not supported. Use: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    job_id = str(uuid.uuid4())
    filename = secure_filename(f"{job_id}_{file.filename}")
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    output_dir = os.path.join(STEMS_FOLDER, job_id)

    os.makedirs(output_dir, exist_ok=True)
    file.save(input_path)

    jobs[job_id] = {
        'status': 'queued',
        'progress': 0,
        'stems': {},
        'error': None
    }

    thread = threading.Thread(target=run_separation, args=(job_id, input_path, output_dir))
    thread.daemon = True
    thread.start()

    return jsonify({'job_id': job_id})


# ── Job status ──────────────────────────────────────────────────────────────
@app.route('/api/status/<job_id>', methods=['GET'])
def status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]
    return jsonify({
        'job_id': job_id,
        'status': job['status'],
        'progress': job['progress'],
        'error': job.get('error')
    })


# ── Stem URLs ───────────────────────────────────────────────────────────────
@app.route('/api/stems/<job_id>', methods=['GET'])
def get_stems(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]
    if job['status'] != 'completed':
        return jsonify({'error': 'Job not completed yet'}), 400

    stem_urls = {
        stem: f'/api/download/{job_id}/{stem}'
        for stem in job['stems']
    }
    return jsonify({'stems': stem_urls})


# ── Download a stem ─────────────────────────────────────────────────────────
@app.route('/api/download/<job_id>/<stem_name>', methods=['GET'])
def download_stem(job_id, stem_name):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]
    if stem_name not in job.get('stems', {}):
        return jsonify({'error': f'Stem "{stem_name}" not found'}), 404

    stem_path = job['stems'][stem_name]
    if not os.path.exists(stem_path):
        return jsonify({'error': 'Stem file missing'}), 404

    return send_file(stem_path, as_attachment=True, download_name=f'{stem_name}.wav')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n✅ STEMBeats backend running!")
    print(f"   Open your browser to: http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=False)
