"""Smoke tests: real Flask/limiter/FFmpeg, mocked expensive Demucs inference."""

import io
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import app as application
from separator import StemSeparator


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.uploads = self.root / 'uploads'
        self.outputs = self.root / 'stems'
        self.uploads.mkdir()
        self.outputs.mkdir()
        folders = patch.multiple(application, UPLOAD_FOLDER=str(self.uploads),
                                 STEMS_FOLDER=str(self.outputs))
        folders.start()
        self.addCleanup(folders.stop)
        application.app.config['TESTING'] = True
        application.jobs.clear()
        application.limiter.reset()
        self.client = application.app.test_client()

    def test_health(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json,
                         {'status': 'ok', 'model': 'htdemucs_6s', 'stems': 6})

    def test_frontend_is_served(self):
        with self.client.get('/') as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'STEMBeats', response.data)

    def test_missing_file(self):
        self.assertEqual(self.client.post('/api/separate').status_code, 400)

    def test_unsupported_file(self):
        response = self.client.post('/api/separate',
                                    data={'file': (io.BytesIO(b'hello'), 'x.txt')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(application.jobs, {})

    def test_unknown_job_routes(self):
        for route in ('status/missing', 'stems/missing', 'download/missing/vocals'):
            with self.subTest(route=route):
                self.assertEqual(self.client.get('/api/' + route).status_code, 404)

    def test_rate_limit_returns_json(self):
        for _ in range(3):
            self.assertEqual(self.client.post('/api/separate').status_code, 400)
        response = self.client.post('/api/separate')
        self.assertEqual(response.status_code, 429)
        self.assertIn('error', response.json)

    def test_upload_queues_worker(self):
        with patch.object(application.threading, 'Thread') as thread:
            response = self.client.post('/api/separate',
                data={'file': (io.BytesIO(b'test audio'), 'track.wav')})
        self.assertEqual(response.status_code, 200)
        job_id = response.json['job_id']
        thread.return_value.start.assert_called_once()
        self.assertEqual(thread.call_args.kwargs['target'], application.run_separation)
        self.assertEqual(thread.call_args.kwargs['args'][0], job_id)
        self.assertEqual(self.client.get('/api/status/' + job_id).json['status'], 'queued')
        self.assertEqual(self.client.get('/api/stems/' + job_id).status_code, 400)
        self.assertEqual(len(list(self.uploads.iterdir())), 1)

    def test_worker_failure_sets_status_and_cleans_upload(self):
        source = self.uploads / 'track.wav'
        source.write_bytes(b'audio')
        application.jobs['test'] = {'status': 'queued', 'stems': {}}
        with patch.object(StemSeparator, 'separate', side_effect=RuntimeError('failed')):
            application.run_separation('test', str(source), str(self.outputs))
        self.assertEqual(application.jobs['test']['status'], 'failed')
        self.assertEqual(application.jobs['test']['error'], 'failed')
        self.assertFalse(source.exists())

    def test_worker_completion_and_download(self):
        source = self.uploads / 'track.wav'
        source.write_bytes(b'audio')
        stem = self.outputs / 'vocals.mp3'
        stem.write_bytes(b'encoded audio')
        application.jobs['test'] = {'status': 'queued', 'stems': {}}
        with patch.object(StemSeparator, 'separate', return_value={'vocals': str(stem)}), \
             patch.object(application, 'convert_to_mp3', return_value=str(stem)):
            application.run_separation('test', str(source), str(self.outputs))
        self.assertEqual(application.jobs['test']['status'], 'completed')
        self.assertFalse(source.exists())
        self.assertEqual(self.client.get('/api/stems/test').json,
                         {'stems': {'vocals': '/api/download/test/vocals'}})
        with self.client.get('/api/download/test/vocals') as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b'encoded audio')

    def test_real_mp3_export(self):
        source = self.outputs / 'silence.wav'
        with wave.open(str(source), 'wb') as wav:
            wav.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\0\0' * 4410)
        result = Path(application.convert_to_mp3(str(source)))
        self.assertEqual(result.suffix, '.mp3')
        self.assertGreater(result.stat().st_size, 0)
        self.assertFalse(source.exists())


if __name__ == '__main__':
    unittest.main()
