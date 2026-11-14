from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from score import (
    ManifestError,
    Utterance,
    main,
    normalize_text,
    read_hypotheses,
    read_manifest,
    render_markdown,
    score_model,
)

MANIFEST_HEADER = "id,text,speaker,noise,audio_path\n"


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# --- normalize_text --------------------------------------------------------------------------


def test_normalize_lowercases_strips_punctuation_and_collapses_spaces() -> None:
    assert normalize_text("  Đi theo TÔI!!  Nhé,  ") == "đi theo tôi nhé"


def test_normalize_unifies_composed_and_decomposed_vietnamese() -> None:
    decomposed = unicodedata.normalize("NFD", "uống thuốc")

    assert normalize_text(decomposed) == normalize_text("uống thuốc") == "uống thuốc"


def test_normalize_keeps_digits() -> None:
    assert normalize_text("Phòng 102.") == "phòng 102"


# --- manifest / hypotheses -------------------------------------------------------------------


def test_read_manifest_parses_rows(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "m.csv",
        MANIFEST_HEADER + "u1,Đi theo tôi,spk1,quiet,a/u1.wav\nu2,Dừng lại,spk2,noisy,a/u2.wav\n",
    )

    rows = read_manifest(path)

    assert rows == [
        Utterance("u1", "Đi theo tôi", "spk1", "quiet"),
        Utterance("u2", "Dừng lại", "spk2", "noisy"),
    ]


def test_read_manifest_rejects_missing_columns(tmp_path: Path) -> None:
    path = _write(tmp_path / "m.csv", "id,text\nu1,abc\n")

    with pytest.raises(ManifestError, match="speaker"):
        read_manifest(path)


def test_read_manifest_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = _write(tmp_path / "m.csv", MANIFEST_HEADER + "u1,a,s,quiet,x\nu1,b,s,quiet,y\n")

    with pytest.raises(ManifestError, match="u1"):
        read_manifest(path)


def test_read_manifest_rejects_empty_reference(tmp_path: Path) -> None:
    path = _write(tmp_path / "m.csv", MANIFEST_HEADER + "u1, !! ,s,quiet,x\n")

    with pytest.raises(ManifestError, match="empty"):
        read_manifest(path)


def test_read_hypotheses_maps_id_to_text(tmp_path: Path) -> None:
    path = _write(tmp_path / "h.csv", "id,text\nu1,đi theo tôi\nu2,\n")

    assert read_hypotheses(path) == {"u1": "đi theo tôi", "u2": ""}


def test_read_hypotheses_rejects_missing_columns(tmp_path: Path) -> None:
    path = _write(tmp_path / "h.csv", "id,transcript\nu1,x\n")

    with pytest.raises(ManifestError, match="text"):
        read_hypotheses(path)


# --- score_model -----------------------------------------------------------------------------


def _manifest() -> list:
    return [
        Utterance("u1", "đi theo tôi", "s1", "quiet"),
        Utterance("u2", "dừng lại", "s2", "noisy"),
    ]


def test_score_model_perfect_match_is_zero() -> None:
    result = score_model("m", _manifest(), {"u1": "Đi theo tôi.", "u2": "dừng lại"})

    assert result.overall.wer == 0.0
    assert result.overall.cer == 0.0
    assert result.missing_ids == ()


def test_score_model_counts_word_errors_and_groups_by_noise() -> None:
    # u1: 1 substitution out of 3 words; u2: perfect (2 words) → overall 1/5.
    result = score_model("m", _manifest(), {"u1": "đi theo bạn", "u2": "dừng lại"})

    assert result.overall.wer == pytest.approx(1 / 5)
    assert result.by_noise["quiet"].wer == pytest.approx(1 / 3)
    assert result.by_noise["noisy"].wer == pytest.approx(0.0)
    assert result.by_noise["quiet"].count == 1


def test_score_model_missing_hypothesis_counts_as_deletion() -> None:
    result = score_model("m", _manifest(), {"u1": "đi theo tôi"})

    assert result.missing_ids == ("u2",)
    assert result.overall.wer == pytest.approx(2 / 5)


def test_score_model_ignores_hypotheses_not_in_manifest() -> None:
    result = score_model("m", _manifest(), {"u1": "đi theo tôi", "u2": "dừng lại", "x": "?"})

    assert result.overall.wer == 0.0


# --- render + CLI ----------------------------------------------------------------------------


def test_render_markdown_contains_one_row_per_model() -> None:
    results = [
        score_model("whisper_base", _manifest(), {"u1": "đi theo bạn", "u2": "dừng lại"}),
        score_model("phowhisper_base", _manifest(), {"u1": "đi theo tôi", "u2": "dừng lại"}),
    ]

    text = render_markdown(results, title="ASR laptop")

    assert "# ASR laptop" in text
    assert "| whisper_base | 2 | 20.0% |" in text
    assert "| phowhisper_base | 2 | 0.0% |" in text
    assert "noisy" in text and "quiet" in text


def test_main_writes_report_and_returns_zero(tmp_path: Path) -> None:
    manifest = _write(tmp_path / "m.csv", MANIFEST_HEADER + "u1,đi theo tôi,s,quiet,x\n")
    hyp = _write(tmp_path / "h.csv", "id,text\nu1,đi theo tôi\n")
    out = tmp_path / "report.md"

    code = main(["--manifest", str(manifest), "--hyp", f"base={hyp}", "--out", str(out)])

    assert code == 0
    assert "| base | 1 | 0.0% |" in out.read_text(encoding="utf-8")


def test_main_rejects_malformed_hyp_argument(tmp_path: Path) -> None:
    manifest = _write(tmp_path / "m.csv", MANIFEST_HEADER + "u1,a,s,quiet,x\n")

    with pytest.raises(SystemExit):
        main(["--manifest", str(manifest), "--hyp", "no-equals-sign"])


def test_main_returns_error_code_on_bad_manifest(tmp_path: Path, capsys) -> None:
    manifest = _write(tmp_path / "m.csv", "id\nu1\n")
    hyp = _write(tmp_path / "h.csv", "id,text\nu1,a\n")

    code = main(["--manifest", str(manifest), "--hyp", f"base={hyp}"])

    assert code == 2
    assert "error" in capsys.readouterr().err.lower()
