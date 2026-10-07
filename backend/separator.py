import os
import sys
import subprocess
import glob
from loguru import logger


class StemSeparator:
    """Runs Demucs htdemucs_6s via CLI — 6 stems, no TorchCodec dependency."""

    STEM_NAMES = ['drums', 'bass', 'guitar', 'piano', 'other', 'vocals']

    def __init__(self, model='htdemucs_6s'):
        self.model_name = model

    def separate(self, input_path, output_dir, progress_callback=None):
        """
        Separate audio into 6 stems using Demucs CLI.
        Returns: {'drums': path, 'bass': path, 'guitar': path,
                  'piano': path, 'other': path, 'vocals': path}
        """
        if progress_callback:
            progress_callback(5)

        logger.info(f"Running Demucs ({self.model_name}) on: {os.path.basename(input_path)}")

        cmd = [
            sys.executable, '-m', 'demucs',
            '-n', self.model_name,
            '--out', output_dir,
            input_path
        ]

        if progress_callback:
            progress_callback(10)

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            err = result.stderr or result.stdout or 'Demucs produced no output'
            logger.error(f"Demucs failed:\n{err[-600:]}")
            raise RuntimeError(f"Demucs error: {err[-400:]}")

        if progress_callback:
            progress_callback(88)

        # Demucs outputs to: output_dir/<model>/<track_name>/<stem>.wav
        search_pattern = os.path.join(output_dir, self.model_name, '**', '*.wav')
        found_files    = glob.glob(search_pattern, recursive=True)
        logger.info(f"Found {len(found_files)} WAV files after separation")

        stems = {}
        for fpath in found_files:
            stem_name = os.path.splitext(os.path.basename(fpath))[0]
            if stem_name in self.STEM_NAMES:
                dest = os.path.join(output_dir, f'{stem_name}.wav')
                os.replace(fpath, dest)
                stems[stem_name] = dest
                logger.success(f"Stem ready: {stem_name}")

        if not stems:
            raise RuntimeError(
                f"Demucs ran but no stems found.\n"
                f"Searched: {search_pattern}\n"
                f"stdout: {result.stdout[-300:]}"
            )

        if progress_callback:
            progress_callback(95)

        return stems
