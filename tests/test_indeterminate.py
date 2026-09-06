"""The third state: what the geometry engine could not model (A3).

`has_changes: boolean` could not carry "could not tell". A layer holding an
operation the engine does not model -- a stroke drawn with a macro aperture, say
-- reported `0 changes` at exit `0`, and its JSON was byte-identical to comparing
a board against a copy of itself. The raster engine saw the same trace and
reported a change, so the two engines answered the same question differently and
the geometry one gave the dangerous answer.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner, Result

from gerberdiff import cli
from gerberdiff.geometry import compute_geometry_diff
from gerberdiff.geometry.layer_geometry import UNREPRESENTED_REASONS, build_layer_geometry
from gerberdiff.geometry.types import DiffOutcome, GeometryDiffResult, LayerGeometryDiff
from gerberdiff.parse.gerber_state import parse_gerber
from gerberdiff.types import LayerStatus, LayerType

_HEADER = "%FSLAX36Y36*%\n%MOMM*%\n%AMROUND*\n1,1,$1,0,0*%\n%ADD10C,1.0*%\n%ADD11ROUND,1.0*%\n"
_PAD = "D10*\nX1000000Y1000000D03*\n"
_MACRO_STROKE = "D11*\nX3000000Y3000000D02*\nX8000000Y8000000D01*\n"
_FOOTER = "M02*\n"


def _run(*args: str) -> Result:
    return CliRunner().invoke(cli.cli, list(args))


def _board(directory: Path, body: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "board-F_Cu.gbr").write_text(_HEADER + body + _FOOTER)


# -- the engine records what it could not model ----------------------------------------


def test_a_macro_stroke_is_recorded_not_dropped() -> None:
    geometry = build_layer_geometry(parse_gerber(_HEADER + _PAD + _MACRO_STROKE + _FOOTER))
    assert geometry.unrepresented == {"stroke_with_macro_aperture": 1}
    assert len(geometry.ops) == 1, "only the pad was modelled"


def test_a_board_the_engine_fully_models_records_nothing() -> None:
    """Guard against every board looking incomplete."""
    geometry = build_layer_geometry(parse_gerber(_HEADER + _PAD + _FOOTER))
    assert geometry.unrepresented == {}


def test_every_reason_has_human_text() -> None:
    """`cannot_represent` asserts membership, so a typo would be a crash in the field."""
    assert all(isinstance(v, str) and v for v in UNREPRESENTED_REASONS.values())


# -- the outcome -----------------------------------------------------------------------


def _result(*, changes: bool, unrepresented: dict[str, int]) -> GeometryDiffResult:
    layer = LayerGeometryDiff(
        name="F_Cu",
        layer_type=LayerType.FCu,
        status=LayerStatus.Added if changes else LayerStatus.Matched,
        unrepresented=unrepresented,
    )
    return GeometryDiffResult(layers=[layer])


def test_nothing_unmodelled_and_no_changes_is_identical() -> None:
    assert _result(changes=False, unrepresented={}).outcome == DiffOutcome.Identical


def test_something_unmodelled_and_no_changes_is_indeterminate() -> None:
    """The A3 defect: this used to be indistinguishable from identical."""
    assert (
        _result(changes=False, unrepresented={"stroke_with_macro_aperture": 1}).outcome
        == DiffOutcome.Indeterminate
    )


def test_a_real_change_outranks_something_unmodelled() -> None:
    """One unmodellable stroke must not mask a trace that actually moved."""
    assert (
        _result(changes=True, unrepresented={"stroke_with_macro_aperture": 1}).outcome
        == DiffOutcome.Different
    )


# -- end to end ------------------------------------------------------------------------


def test_geomdiff_does_not_report_an_unmodelled_trace_as_no_change(tmp_path: Path) -> None:
    """The reproduction. An added trace used to pass the gate at exit 0."""
    _board(tmp_path / "b", _PAD)
    _board(tmp_path / "a", _PAD + _MACRO_STROKE)
    result = _run("geomdiff", str(tmp_path / "b"), str(tmp_path / "a"), "--fail-on-diff")
    assert result.exit_code == cli.EXIT_INDETERMINATE
    assert "indeterminate" in result.output
    assert "could not be modelled" in result.output


def test_indeterminate_does_not_wait_for_fail_on_diff(tmp_path: Path) -> None:
    """--fail-on-diff chooses whether a *difference* fails. It has no bearing on
    whether the tool could look."""
    _board(tmp_path / "b", _PAD)
    _board(tmp_path / "a", _PAD + _MACRO_STROKE)
    result = _run("geomdiff", str(tmp_path / "b"), str(tmp_path / "a"))
    assert result.exit_code == cli.EXIT_INDETERMINATE


def test_identical_boards_still_exit_0(tmp_path: Path) -> None:
    """The control. Without it, every one of these would pass on a tool that always
    exited 2."""
    _board(tmp_path / "b", _PAD)
    _board(tmp_path / "a", _PAD)
    result = _run("geomdiff", str(tmp_path / "b"), str(tmp_path / "a"), "--fail-on-diff")
    assert result.exit_code == cli.EXIT_OK
    assert "identical" in result.output


def test_the_report_distinguishes_the_two_situations(tmp_path: Path) -> None:
    """They used to be byte-identical, so no field existed to branch on."""
    _board(tmp_path / "b", _PAD)
    _board(tmp_path / "a", _PAD + _MACRO_STROKE)
    _board(tmp_path / "same", _PAD)

    incomplete = tmp_path / "incomplete.json"
    identical = tmp_path / "identical.json"
    _run("geomdiff", str(tmp_path / "b"), str(tmp_path / "a"), "--out-json", str(incomplete))
    _run("geomdiff", str(tmp_path / "b"), str(tmp_path / "same"), "--out-json", str(identical))

    a = json.loads(incomplete.read_text())
    b = json.loads(identical.read_text())
    assert a != b, "a real omission must not serialise the same as two identical boards"
    assert a["summary"]["outcome"] == "indeterminate"
    assert b["summary"]["outcome"] == "identical"
    assert a["summary"]["unrepresented"] == {"stroke_with_macro_aperture": 1}
    assert b["summary"]["unrepresented"] == {}
    # has_changes alone still cannot tell them apart -- that is why outcome exists.
    assert a["summary"]["has_changes"] == b["summary"]["has_changes"] is False


def test_the_geometry_engine_no_longer_contradicts_the_raster_engine(tmp_path: Path) -> None:
    """Both engines saw the same added trace; only one used to say so."""
    _board(tmp_path / "b", _PAD)
    _board(tmp_path / "a", _PAD + _MACRO_STROKE)
    geom = _run("geomdiff", str(tmp_path / "b"), str(tmp_path / "a"), "--fail-on-diff")
    assert geom.exit_code != cli.EXIT_OK, "geomdiff must not call this clean"


# -- the exit-code contract ------------------------------------------------------------


def test_exit_codes_match_the_org_vocabulary() -> None:
    """A1 settled these across partspec and netspec; gerberdiff follows (A3)."""
    assert cli.EXIT_OK == 0
    assert cli.EXIT_DIFFERENT == 1
    assert cli.EXIT_INDETERMINATE == 2
    assert cli.EXIT_ERROR == 4
    assert cli.EXIT_USAGE == 64


def test_indeterminate_is_not_the_error_code() -> None:
    """ "I could not model part of this" is not "I could not read the file"."""
    assert cli.EXIT_INDETERMINATE != cli.EXIT_ERROR


def test_compute_geometry_diff_carries_the_reason_through(tmp_path: Path) -> None:
    _board(tmp_path / "b", _PAD)
    _board(tmp_path / "a", _PAD + _MACRO_STROKE)
    result = compute_geometry_diff(tmp_path / "b", tmp_path / "a")
    assert result.outcome == DiffOutcome.Indeterminate
    assert result.unrepresented == {"stroke_with_macro_aperture": 1}
    assert result.layers[0].indeterminate
