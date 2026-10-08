# STEMBeats CI and deployment investigation

Inspection date: October 8, 2026. Base commit:
`442ef6fa7581d2c73de5f301bc98705fea05473d`.

## Confirmed findings

- The application is Flask. The old Django workflow used Python 3.7–3.9,
  installed a nonexistent root `requirements.txt`, and invoked a nonexistent
  `manage.py`. The failed run's logs confirm the Python 3.7 setup error and
  the missing requirements file. No application tests ran.
- `backend/app.py` imports `flask_limiter` and `loguru` at startup, but neither
  was declared in the application's requirements. The feature commit
  `a42510adaf7f6aa4bb7025461cf04d91766e7931` changed only app.py and separator.py.
  A clean installation needs these dependencies; this is a startup defect,
  not a verified diagnosis of the Render deployment error.
- Render's notifications confirm a memory-limit restart and a failed deployment
  of that feature commit. The notifications contain no stack trace, memory
  limit, measured peak, or workload details. The deployment log page requires
  sign-in. The actual build/start failure and the process responsible for the
  memory peak remain unverified.
- There is no committed Render configuration, Dockerfile, Python runtime pin,
  or test suite in the inspected base tree. The README's illustrative tree
  is not an inventory of implemented files.

## This change

Replace Django CI with Flask CI on Python 3.11 and 3.12, use current Node 24
GitHub actions, install `backend/requirements.txt` and FFmpeg, check dependency
consistency and Demucs CLI imports, and run ten smoke tests. Add pinned
Flask-Limiter and Loguru dependencies. No production application behavior,
Render settings, instance size, or paid services are changed.

CI installs CPU Torch/Torchaudio first from the official PyTorch CPU index to
avoid unnecessary CUDA downloads on hosted runners. It then installs the full
application requirements. This CI installation choice does not change Render's
build command. Unconstrained ML dependencies remain a reproducibility risk;
lock a compatible stack only after an end-to-end separation test.

Python 3.11 and 3.12 remain supported upstream. Do not casually add Python 3.13+
to this matrix: pydub 0.25.1 imports the removed standard-library audioop module.

## Memory assessment: risks, not a proven incident cause

| Area | Evidence in the current code | Implication |
| --- | --- | --- |
| Concurrent inference | Each accepted upload starts a daemon thread; each thread starts a separate Demucs subprocess. | Multiple uploads can load multiple models simultaneously. Three requests/day/IP is not a global concurrency bound. |
| Audio size | The limit is 100 MB of uploaded, potentially compressed audio; there is no duration limit. | Decoded PCM and six output tensors can be much larger than the upload. |
| Six-stem inference | `htdemucs_6s` runs in a subprocess. | Its model, tensors, and working memory still consume hosting resources. Actual CPU peak must be measured. |
| MP3 conversion | pydub loads an entire WAV stem, then encodes it. Stems are converted sequentially. | Extra decoded-audio memory exists during export, though it follows inference within each job. Other jobs may overlap. |
| Retention | `jobs` never expires; output directories are never cleaned up. | Metadata accumulates in RAM; outputs accumulate on disk. This is a retention defect, not proof of the observed RAM spike. |
| Worker topology | Jobs and rate limits live in process-local memory. | Multiple Gunicorn workers can disagree about jobs and limits; adding workers also increases potential concurrency. |
| Hosting capacity | Instance RAM and runtime metrics have not been read. | Cannot conclude that the instance is undersized or recommend a paid upgrade from this evidence alone. |

Demucs documents that parallel jobs multiply RAM use, and exposes segment-size
controls. Its GPU-memory figures must not be presented as a measured CPU RAM
requirement for this Render service.

## Copilot continuation

1. Review and merge this CI/startup fix after both Python jobs pass. A merge may
   trigger Render auto-deploy if enabled; inspect that setting before merging.
2. Read the failed deployment's build and runtime log tail. Record the first
   causal error, Python version, root directory, install command, start command,
   FFmpeg availability, and deployed commit. Distinguish install failure,
   import failure, port/health failure, and OOM kill. Do not copy secrets into a PR.
3. Check runtime memory around the reported restart, the running commit at that
   time, instance RAM, Gunicorn worker/thread counts, and simultaneous jobs.
   Do not assume the failed commit was running when the earlier OOM occurred.
4. On an isolated environment, measure peak memory for one short and one
   representative long input, then concurrent requests. Include the web process
   and all audio subprocesses. Verify actual six-stem output, polling/downloads,
   MP3 encoding, and model-download failure behavior.
5. Prepare a separate bounded-inference fix: reject excess jobs with a clear
   busy response, enforce decoded-duration limits, and expire jobs/output files.
   A process-local semaphore only works as a service-wide bound with a single
   web process; a multi-process/multi-instance design needs shared coordination
   and shared job state. Do not introduce a paid queue without approval.
6. Consider FFmpeg streaming conversion and measured Demucs segment settings.
   Preserve six-stem behavior and compare quality/performance before changing
   model settings. Increasing hosting resources requires the owner's approval.

## Sources

- [Failed GitHub Actions run](https://github.com/80Kane/STEMBeats/actions/runs/37710776423)
- [Feature commit](https://github.com/80Kane/STEMBeats/commit/a42510adaf7f6aa4bb7025461cf04d91766e7931)
- [Python support schedule](https://devguide.python.org/versions/)
- [Demucs documentation](https://github.com/facebookresearch/demucs)
- Render memory and deployment notifications supplied by the owner and read
  during this investigation. Private dashboard logs are still needed.
