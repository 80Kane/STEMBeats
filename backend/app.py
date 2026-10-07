import os
import uuid
import threading
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from loguru import logger

# Serve frontend from ../frontend/index.html
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

# ── Rate limiter — 3 separations per day per IP (free tier) ─────────────────
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
STEMS_FOLDER  = os.path.join(os.path.dirname(__file__), 'stems')
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'm4a', 'ogg', 'aac'}
MAX_FILE_MB = 100

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STEMS_FOLDER,  exist_ok=True)

jobs = {}  # in-memory job store


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def convert_to_mp3(wav_path):
    """Convert a WAV stem to MP3 (320kbps) — 10x smaller download."""
    try:
        from pydub import AudioSegment
        mp3_path = wav_path.replace('.wav', '.mp3')
        AudioSegment.from_wav(wav_path).export(mp3_path, format='mp3', bitrate='320k')
        os.remove(wav_path)
        logger.success(f"MP3 ✓  {os.path.basename(mp3_path)}")
        return mp3_path
    except Exception as e:
        logger.warning(f"MP3 conversion failed — keeping WAV: {e}")
        return wav_path


def run_separation(job_id, input_path, output_dir):
    """Background thread — run Demucs, convert to MP3, store results."""
    try:
        jobs[job_id]['status'] = 'processing'
        jobs[job_id]['progress'] = 5
        logger.info(f"[{job_id[:8]}] Starting separation …")

        from separator import StemSeparator
        stems = StemSeparator().separate(
            input_path,
            output_dir,
            progress_callback=lambda pct: jobs[job_id].update({'progress': pct})
        )

        logger.info(f"[{job_id[:8]}] Converting {len(stems)} stems to MP3 …")
        mp3_stems = {name: convert_to_mp3(path) for name, path in stems.items()}

        jobs[job_id].update({'status': 'completed', 'progress': 100, 'stems': mp3_stems})
        logger.success(f"[{job_id[:8]}] Done — {list(mp3_stems.keys())}")

    except Exception as e:
        jobs[job_id].update({'status': 'failed', 'error': str(e)})
        logger.error(f"[{job_id[:8]}] FAILED: {e}")
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_file(os.path.join(FRONTEND_DIR, 'index.html'))


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'model': 'htdemucs_6s', 'stems': 6})


@app.route('/api/separate', methods=['POST'])
@limiter.limit("3 per day")           # Free tier: 3 separations / day / IP
def separate():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': f'Unsupported format. Use: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    # File-size guard
    file.seek(0, 2); size_mb = file.tell() / 1_048_576; file.seek(0)
    if size_mb > MAX_FILE_MB:
        return jsonify({'error': f'File too large ({size_mb:.1f} MB). Max is {MAX_FILE_MB} MB.'}), 400

    job_id   = str(uuid.uuid4())
    filename = secure_filename(f"{job_id}_{file.filename}")
    in_path  = os.path.join(UPLOAD_FOLDER, filename)
    out_dir  = os.path.join(STEMS_FOLDER, job_id)

    os.makedirs(out_dir, exist_ok=True)
    file.save(in_path)
    logger.info(f"[{job_id[:8]}] Uploaded '{file.filename}' ({size_mb:.1f} MB)")

    jobs[job_id] = {'status': 'queued', 'progress': 0, 'stems': {}, 'error': None}

    t = threading.Thread(target=run_separation, args=(job_id, in_path, out_dir), daemon=True)
    t.start()

    return jsonify({'job_id': job_id})


@app.errorhandler(429)
def rate_limit_handler(e):
    return jsonify({
        'error': '🚫 Daily limit reached. Free tier: 3 separations/day. Upgrade to Pro for unlimited access.'
    }), 429


@app.route('/api/status/<job_id>')
def status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    j = jobs[job_id]
    return jsonify({'job_id': job_id, 'status': j['status'],
                    'progress': j['progress'], 'error': j.get('error')})


@app.route('/api/stems/<job_id>')
def get_stems(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    j = jobs[job_id]
    if j['status'] != 'completed':
        return jsonify({'error': 'Not completed yet'}), 400
    return jsonify({'stems': {s: f'/api/download/{job_id}/{s}' for s in j['stems']}})


@app.route('/api/download/<job_id>/<stem_name>')
def download_stem(job_id, stem_name):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    j = jobs[job_id]
    if stem_name not in j.get('stems', {}):
        return jsonify({'error': f'Stem "{stem_name}" not found'}), 404
    path = j['stems'][stem_name]
    if not os.path.exists(path):
        return jsonify({'error': 'File missing'}), 404
    ext = os.path.splitext(path)[1]
    return send_file(path, as_attachment=True, download_name=f'{stem_name}{ext}')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"\n✅ STEMBeats running  →  http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=False)
