"""A usage error exits EXIT_USAGE (64), not click's 2 (#30).

click exits 2 on a usage error -- an unknown flag, a missing argument, an
argument that fails its type check -- and 2 is this tool's `indeterminate`: part
of the comparison could not be made. A mistyped flag must not read as a finding
about the boards, so the usage errors are remapped to 64, as partspec does.

`EXIT_USAGE` was declared 64 throughout while a bad flag exited 2, so a test of
the constant would have passed the whole time. These measure a real process
running the console-script entry point, and pin the codes that must *not* move:
`--help` and `--version` stay 0, and a command's own exit 2 (`indeterminate`)
stays 2.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from gerberdiff import cli

_HEADER = "%FSLAX36Y36*%\n%MOMM*%\n%AMROUND*\n1,1,$1,0,0*%\n%ADD10C,1.0*%\n%ADD11ROUND,1.0*%\n"
_PAD = "D10*\nX1000000Y1000000D03*\n"
_MACRO_STROKE = "D11*\nX3000000Y3000000D02*\nX8000000Y8000000D01*\n"
_FOOTER = "M02*\n"


def _exit(*args: str) -> int:
    """Exit status of `gerberdiff <args>`, run exactly as the console script runs it."""
    proc = subprocess.run(
        [sys.executable, "-c", "from gerberdiff.cli import cli; cli()", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode


def _board(directory: Path, body: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "board-F_Cu.gbr").write_text(_HEADER + body + _FOOTER)


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["--bogus-flag"], id="unknown-group-flag"),
        pytest.param(["geomdiff", "--bogus-flag", "a", "b"], id="unknown-command-flag"),
        pytest.param(["no-such-verb"], id="unknown-verb"),
        pytest.param(["geomdiff"], id="missing-arguments"),
        pytest.param(["geomdiff", "/no/such/before", "/no/such/after"], id="bad-path-argument"),
        pytest.param([], id="no-arguments"),
    ],
)
def test_a_usage_error_exits_64(args: list[str]) -> None:
    assert _exit(*args) == cli.EXIT_USAGE


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["--help"], id="group-help"),
        pytest.param(["geomdiff", "--help"], id="command-help"),
        pytest.param(["--version"], id="version"),
    ],
)
def test_help_and_version_still_exit_0(args: list[str]) -> None:
    """click exits 0 for these; a successful run must not become 64."""
    assert _exit(*args) == cli.EXIT_OK


def test_a_commands_own_exit_2_is_not_remapped(tmp_path: Path) -> None:
    """The remap is for click's usage errors, not for every 2. `indeterminate` is
    raised by the command after parsing succeeded, and must reach the caller as 2."""
    _board(tmp_path / "b", _PAD)
    _board(tmp_path / "a", _PAD + _MACRO_STROKE)
    assert _exit("geomdiff", str(tmp_path / "b"), str(tmp_path / "a")) == cli.EXIT_INDETERMINATE


def test_a_commands_own_exit_64_is_unchanged(tmp_path: Path) -> None:
    """An existing output file without --overwrite was already 64 from the command."""
    _board(tmp_path / "b", _PAD)
    _board(tmp_path / "a", _PAD)
    out = tmp_path / "report.json"
    out.write_text("{}")
    args = ("geomdiff", str(tmp_path / "b"), str(tmp_path / "a"), "--out-json", str(out))
    assert _exit(*args) == cli.EXIT_USAGE
