"""Score ASR hypotheses against the domain test set (WER / CER, split by noise condition).

Runs on a laptop only. Inputs are CSV files (UTF-8):

  manifest: id,text,speaker,noise,audio_path   (reference transcripts; see manifest.example.csv)
  hypothesis (one per model): id,text

Example:
  python eval/asr/score.py --manifest $AI_DATA_DIR/asr/manifest.csv \\
      --hyp whisper_base=out/whisper_base.csv --hyp phowhisper_base=out/phowhisper_base.csv \\
      --out eval/results/2026-11-20_asr_laptop.md
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import jiwer

MANIFEST_COLUMNS = ("id", "text", "speaker", "noise")
HYPOTHESIS_COLUMNS = ("id", "text")
_NON_WORD = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACES = re.compile(r"\s+")


class ManifestError(ValueError):
    """Malformed manifest or hypothesis file."""


@dataclass(frozen=True)
class Utterance:
    id: str
    text: str
    speaker: str
    noise: str


@dataclass(frozen=True)
class Scores:
    count: int
    wer: float
    cer: float


@dataclass(frozen=True)
class ModelResult:
    model: str
    overall: Scores
    by_noise: Mapping[str, Scores]
    missing_ids: Tuple[str, ...]


def normalize_text(text: str) -> str:
    """NFC (Vietnamese may arrive decomposed), lowercase, drop punctuation, collapse spaces."""
    text = unicodedata.normalize("NFC", text).lower()
    text = _NON_WORD.sub(" ", text).replace("_", " ")
    return _SPACES.sub(" ", text).strip()


def _read_rows(path: Path, required: Sequence[str]) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [col for col in required if col not in (reader.fieldnames or [])]
        if missing:
            raise ManifestError(f"{path}: missing column(s) {', '.join(missing)}")
        return [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]


def read_manifest(path: Path) -> List[Utterance]:
    rows = _read_rows(Path(path), MANIFEST_COLUMNS)
    seen: Dict[str, int] = {}
    utterances = []
    for line_no, row in enumerate(rows, start=2):
        utt_id = row["id"]
        if utt_id in seen:
            raise ManifestError(f"{path}:{line_no}: duplicate id {utt_id!r}")
        if not normalize_text(row["text"]):
            raise ManifestError(f"{path}:{line_no}: empty reference text for {utt_id!r}")
        seen[utt_id] = line_no
        utterances.append(Utterance(utt_id, row["text"], row["speaker"], row["noise"]))
    return utterances


def read_hypotheses(path: Path) -> Dict[str, str]:
    return {row["id"]: row["text"] for row in _read_rows(Path(path), HYPOTHESIS_COLUMNS)}


def _scores(refs: List[str], hyps: List[str]) -> Scores:
    return Scores(count=len(refs), wer=jiwer.wer(refs, hyps), cer=jiwer.cer(refs, hyps))


def score_model(
    model: str, manifest: Sequence[Utterance], hypotheses: Mapping[str, str]
) -> ModelResult:
    """Corpus-level WER/CER. A missing hypothesis is scored as empty (all deletions)."""
    pairs: Dict[str, Tuple[List[str], List[str]]] = {}
    all_refs: List[str] = []
    all_hyps: List[str] = []
    for utt in manifest:
        ref = normalize_text(utt.text)
        hyp = normalize_text(hypotheses.get(utt.id, ""))
        all_refs.append(ref)
        all_hyps.append(hyp)
        refs, hyps = pairs.setdefault(utt.noise, ([], []))
        refs.append(ref)
        hyps.append(hyp)
    missing = tuple(u.id for u in manifest if u.id not in hypotheses)
    by_noise = {noise: _scores(r, h) for noise, (r, h) in sorted(pairs.items())}
    return ModelResult(model, _scores(all_refs, all_hyps), by_noise, missing)


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_markdown(results: Sequence[ModelResult], title: str) -> str:
    noises = sorted({noise for r in results for noise in r.by_noise})
    header = ["Model", "N", "WER", "CER"] + [f"WER {n}" for n in noises] + ["Missing"]
    lines = [f"# {title}", "", "| " + " | ".join(header) + " |"]
    lines.append("|" + "---|" * len(header))
    for r in results:
        per_noise = [_pct(r.by_noise[n].wer) if n in r.by_noise else "-" for n in noises]
        row = [r.model, str(r.overall.count), _pct(r.overall.wer), _pct(r.overall.cer)]
        lines.append("| " + " | ".join(row + per_noise + [str(len(r.missing_ids))]) + " |")
    lines += ["", "Text normalised: NFC, lowercase, punctuation removed (eval/asr/score.py)."]
    return "\n".join(lines) + "\n"


def _parse_hyp_arg(value: str) -> Tuple[str, Path]:
    name, sep, path = value.partition("=")
    if not sep or not name or not path:
        raise argparse.ArgumentTypeError(f"expected NAME=PATH, got {value!r}")
    return name, Path(path)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--hyp", type=_parse_hyp_arg, action="append", required=True)
    parser.add_argument("--out", type=Path, help="Write markdown report here (else stdout)")
    parser.add_argument("--title", default="ASR evaluation")
    args = parser.parse_args(argv)
    try:
        manifest = read_manifest(args.manifest)
        results = [score_model(n, manifest, read_hypotheses(p)) for n, p in args.hyp]
    except (ManifestError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = render_markdown(results, args.title)
    if args.out is None:
        sys.stdout.write(report)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
