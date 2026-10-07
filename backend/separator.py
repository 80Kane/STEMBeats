import os
import sys
import subprocess
import glob


class StemSeparator:
    """Runs Demucs via CLI subprocess — avoids TorchCodec/torchaudio issues on Python 3.14."""

    STEM_NAMES = ['drums', 'bass', 'other', 'vocals']

    def __init__(self, model='demucs'):
        self.model_name = model  # ignored — always uses htdemucs via CLI

    def separate(self, input_path, output_dir, progress_callback=None):
        """
        Separate audio using the Demucs CLI.
        Returns dict: {'drums': path, 'bass': path, 'other': path, 'vocals': path}
        """
        if progress_callback:
            progress_callback(5)

        # Run: python -m demucs -n htdemucs --out output_dir input_path
        cmd = [
            sys.executable, '-m', 'demucs',
            '-n', 'htdemucs_6s',
            '--out', output_dir,
            input_path
        ]

        if progress_callback:
            progress_callback(10)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or 'Demucs failed with no output'
            raise RuntimeError(f"Demucs error: {error_msg[-500:]}")

        if progress_callback:
            progress_callback(90)

        # Demucs outputs to: output_dir/htdemucs/<track_name>/<stem>.wav
        stems = {}
        search_pattern = os.path.join(output_dir, 'htdemucs', '**', '*.wav')
        found_files = glob.glob(search_pattern, recursive=True)

        for fpath in found_files:
            stem_name = os.path.splitext(os.path.basename(fpath))[0]  # e.g. "drums"
            if stem_name in self.STEM_NAMES:
                # Copy to output_dir root for easy access
                dest = os.path.join(output_dir, f'{stem_name}.wav')
                os.replace(fpath, dest)
                stems[stem_name] = dest

        if not stems:
            raise RuntimeError(
                "Demucs ran but produced no output files. "
                f"Searched: {search_pattern}\n"
                f"Demucs stdout: {result.stdout[-300:]}"
            )

        if progress_callback:
            progress_callback(100)

        return stems
