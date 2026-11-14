# CLAUDE.md

Instructions for coding agents (CLAUDE and others) working in this repository.

## Project

Hospital assistant robot ("Robot Y Tế"): delivers medicine/items in 3 trays, reminds patients on schedule, talks by voice, detects falls and fire, follows a nurse, returns to charge. Mecanum base, ROS1 Noetic, Raspberry Pi 5 + AI HAT+ (Hailo-8L).

**The user owns the AI part.** Unless told otherwise, work only on AI code and AI docs.

## Read first (every session)

All docs live in [spec/docs/](spec/docs/) — start at [spec/docs/README.md](spec/docs/README.md). Minimum before any task:

1. [spec/docs/decisions.md](spec/docs/decisions.md) — locked decisions and open questions. **Never act against a locked decision.**
2. [spec/AI_PLAN.md](spec/AI_PLAN.md) — plan, milestones, checklist (current progress).
3. [spec/docs/architecture.md](spec/docs/architecture.md) — hardware, module map, invariants.

Then, depending on the task:
- Touching topics, msgs, WebSocket protocol, backend payloads → [spec/docs/interfaces.md](spec/docs/interfaces.md)
- Writing code → [spec/docs/convention.md](spec/docs/convention.md) and [spec/docs/testing.md](spec/docs/testing.md)
- Need the reasoning or detailed pipeline for a module → [spec/AI_PROPOSAL.md](spec/AI_PROPOSAL.md)
- Product requirements → [spec/docs/product_spec.md](spec/docs/product_spec.md) (Markdown copy of `spec/ROBOT Y TẾ.docx`; do not edit the `.docx`)

If docs conflict, follow the precedence order in [spec/docs/README.md](spec/docs/README.md#nguồn-sự-thật-khi-các-file-mâu-thuẫn) (`decisions.md` wins).

## Repository map

This repo (`nurse-ai`) holds **only the AI part**. The rest of the robot (ROS navigation, firmware) lives in the team repo `fw`, expected to be cloned as a sibling folder (`../fw`). Doc links into `../fw/...` only resolve with that layout.

| Path | What | Owner | Agent may edit? |
|---|---|---|---|
| `catkin_ws/src/ai/`, `catkin_ws/src/ai_msgs/` | AI code (`ai_common`, `ai_perception`, `eval/` exist; dev venv + commands in `catkin_ws/src/ai/README.md`) | AI (user) | **Yes** |
| `spec/` | Proposal, plan, docs | AI (user) | Yes — keep in sync (see below) |
| `catkin_ws/src/vendor/moving_server_msgs/` | Vendored copy of the ROS team's action/msg definitions (see `VENDORED.md` there) | ROS team | **No** — only re-sync from `../fw` |

In the sibling repo `../fw` (read only — reference for contracts, `git pull` to see updates):

| Path | What | Owner |
|---|---|---|
| `pi_ws/src/robot_system/` | `moving_server`, `moving_server_msgs`, `cmd_vel_mux`, `localize_manager` | ROS team |
| `pi_ws/src/nox/` | Bringup, nav configs, ESP32 sensor node | ROS team |
| `pi_ws/src/reflector_detector/`, `pi_ws/src/xv_11_laser_driver/` | Docking reflector detection, lidar driver | ROS team |
| `src/`, `calib_motor/`, `arduino/` | ESP32/Arduino firmware, motor calibration | Firmware team |

Never edit `../fw`. When it changes a contract the AI depends on (`moving_server_msgs`, `/person_tracker/pose` handling, `/esp32/sensor_data` layout, mux priorities), report it to the user and update `spec/docs/interfaces.md` / `architecture.md`. If `moving_server_msgs` changed, re-copy it byte-identical (ROS1 checks message md5) and update `VENDORED.md`.

## Hard rules

These come from [spec/docs/decisions.md](spec/docs/decisions.md) and [spec/docs/architecture.md](spec/docs/architecture.md#5-bất-biến-invariant--không-được-phá):

- **No new hardware** in any design or suggestion (D-001).
- **All AI models run on the Hailo-8L.** Only three CPU exceptions: Piper TTS, the Whisper decoder, and **MediaPipe Pose for fall confirmation** (only on the crop of a suspected-fall person, frame-limited). Do not add any other CPU inference (no ONNX-on-CPU fallback) (D-003, D-015).
- Custom models are compiled to `.hef` with the Hailo Dataflow Compiler on Google Colab, outside the robot (D-005).
- Follow-me = follow the person with the **largest bounding box**. Do not add ReID, markers, or Kalman tracking (D-006).
- AI **never publishes `cmd_vel`**. Motion only via the `moving_server` action and `/person_tracker/pose` (D-007).
- LLM via the **OpenAI SDK** only; model name from env var `LLM_MODEL`. No LangChain, no Spring AI (D-008).
- No images, video, or audio leave the robot; text sent to the LLM must have patient data masked (D-014).
- Fall/fire detection is never fully disabled at runtime; under load only lower FPS.
- Emergency voice intents go straight to an alert, never wait on the LLM.
- No hardcoded thresholds, URLs, or secrets — YAML + env var, documented in `.env.example`.

If a task seems to require breaking one of these, stop and ask the user instead.

## How to work

1. **Locate the task in [spec/AI_PLAN.md](spec/AI_PLAN.md)** (tier T0–T3, item ID). Prefer T0/T1 items that do not depend on other teams.
2. **Plan before large changes** (new module, interface change, >3 files): state the workload and ask for plan mode to turn on if needed.
3. **Interface first**: change [spec/docs/interfaces.md](spec/docs/interfaces.md) before changing msgs/topics/protocols in code.
4. **Logic in `core/`, ROS in `nodes/`**: pure Python logic must not import `rospy` or do I/O (see [convention.md](spec/docs/convention.md#3-tách-logic-và-ros)).
5. **Tests first** for `core/` logic; coverage ≥ 80% (see [testing.md](spec/docs/testing.md)).
6. **Python 3.8 compatible** for anything running in the ROS Noetic container.
7. **Keep docs in sync** after finishing:
   - tick completed checklist items in `spec/AI_PLAN.md`
   - record new or changed decisions in `spec/docs/decisions.md` (append, never rewrite history)
   - update `architecture.md` / `interfaces.md` / `testing.md` if affected
8. **Report honestly**: say which tests ran and which could not (e.g. no Pi/Hailo available). Never claim hardware results you did not measure.

## Environment notes

- Dev machine is macOS. Unit tests of `core/` logic must run here. ROS, HailoRT, and camera code only run on the Pi 5 (inside Docker) — do not try to install them on macOS.
- ROS is ROS1 **Noetic** (catkin, `rospy`). On the Pi 5 it runs in Docker; the ROS team's Docker setup is not in the repo yet (open question O-001).
- Commands for AI code are in [spec/docs/testing.md](spec/docs/testing.md#4-lệnh).
- A CodeGraph index may exist at `.codegraph/`; if the `codegraph` CLI is available, `codegraph explore "<symbol or question>"` is faster than grepping.

## Language

- Code, identifiers, comments, commit messages: **English**.
- Docs in `spec/`: **Vietnamese**.
- Replies to the user: **Vietnamese**.

## Git

- Do not commit or push unless the user asks.
- Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `perf:`, `ci:`).
- Never commit `.env`, API keys, model files (`.hef`, `.onnx`, `.pt`), datasets, or recordings of real people.
- `spec/` is git-ignored on purpose (kept local, never pushed). Never `git add -f` it. `AGENTS.md` is committed.
