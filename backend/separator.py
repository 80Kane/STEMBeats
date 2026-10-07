import os


class StemSeparator:
    """Handles stem separation using Spleeter or Demucs."""

    STEM_NAMES = ['drums', 'bass', 'piano', 'vocals']

    def __init__(self, model='spleeter'):
        self.model_name = model
        if model == 'spleeter':
            self._init_spleeter()
        elif model == 'demucs':
            self._init_demucs()
        else:
            raise ValueError(f"Unknown model: {model}. Use 'spleeter' or 'demucs'.")

    def _init_spleeter(self):
        from spleeter.separator import Separator
        # 4stems separates into: drums, bass, piano, vocals
        self._separator = Separator('spleeter:4stems')

    def _init_demucs(self):
        import demucs.api
        self._separator = demucs.api.Separator(model='htdemucs')

    def separate(self, input_path, output_dir, progress_callback=None):
        """
        Separate audio into stems.
        Returns dict: {'drums': path, 'bass': path, 'piano': path, 'vocals': path}
        """
        if self.model_name == 'spleeter':
            return self._separate_spleeter(input_path, output_dir, progress_callback)
        else:
            return self._separate_demucs(input_path, output_dir, progress_callback)

    def _separate_spleeter(self, input_path, output_dir, progress_callback):
        if progress_callback:
            progress_callback(10)

        self._separator.separate_to_file(
            input_path,
            output_dir,
            codec='wav',
            synchronous=True
        )

        if progress_callback:
            progress_callback(85)

        # Spleeter outputs to output_dir/<filename_without_ext>/
        base = os.path.splitext(os.path.basename(input_path))[0]
        # Strip the job_id prefix from the base name
        stem_dir = os.path.join(output_dir, base)

        stems = {}
        for stem in self.STEM_NAMES:
            src = os.path.join(stem_dir, f'{stem}.wav')
            dst = os.path.join(output_dir, f'{stem}.wav')
            if os.path.exists(src):
                os.rename(src, dst)
                stems[stem] = dst

        # Clean up the now-empty spleeter subfolder
        if os.path.exists(stem_dir):
            try:
                os.rmdir(stem_dir)
            except OSError:
                pass

        if progress_callback:
            progress_callback(100)

        return stems

    def _separate_demucs(self, input_path, output_dir, progress_callback):
        import torch
        import torchaudio

        if progress_callback:
            progress_callback(5)

        waveform, sample_rate = torchaudio.load(input_path)

        if progress_callback:
            progress_callback(20)

        _, outputs = self._separator.separate_tensor(waveform, sample_rate)

        stems = {}
        for i, stem in enumerate(self.STEM_NAMES):
            path = os.path.join(output_dir, f'{stem}.wav')
            torchaudio.save(path, outputs[stem], sample_rate)
            stems[stem] = path
            if progress_callback:
                progress_callback(20 + (i + 1) * 20)

        return stems
