# AI packages

ROS1 Noetic packages for the robot's AI. Design: `spec/` (local only). Python 3.8 compatible.

| Path | Content |
|---|---|
| `ai_common/` | Config (YAML + `AI_*` env vars), pydantic schemas, JSON logging |
| `ai_follow/` | Follow-me: largest-bbox person → (x, y) for `/person_tracker/pose` (core only; ROS node later) |
| `ai_perception/` | Frame sources (video file replay, USB camera); Hailo runner later |
| `eval/asr/` | ASR scoring (WER/CER) for the Vietnamese domain test set |
| `eval/results/` | Benchmark / eval reports (`<date>_<name>.md`) |

Each package: `src/<pkg>/` (logic, no `rospy` in `core/`), `config/`, `tests/`.

## Dev setup (macOS)

```bash
cd catkin_ws/src/ai
uv venv --python 3.8 .venv          # same Python as the Noetic container
uv pip install --python .venv/bin/python -r requirements-dev.txt
cp .env.example .env                # never commit .env
```

## Commands

```bash
.venv/bin/pytest -q --cov                      # unit + contract tests, fails under 80% coverage
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Test file names must be unique across packages (pytest default import mode).

## ASR scoring

Manifest format: [eval/asr/manifest.example.csv](eval/asr/manifest.example.csv)
(`noise` = free label, e.g. `quiet` / `noisy`; audio and the real manifest stay under `$AI_DATA_DIR`).
Each model's output: CSV `id,text`.

```bash
.venv/bin/python eval/asr/score.py --manifest $AI_DATA_DIR/asr/manifest.csv \
  --hyp whisper_base=out/whisper_base.csv --hyp phowhisper_base=out/phowhisper_base.csv \
  --out eval/results/$(date +%F)_asr_laptop.md
```
