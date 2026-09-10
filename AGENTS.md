# AGENTS.md -- gerberdiff

Instructions for humans and AI coding agents working in this repository.

The org-wide contract at <https://github.com/heibench/.github/blob/main/AGENTS.md>
is the floor. This file carries what is specific to gerberdiff; where the two
conflict, this file wins.

## Project

`gerberdiff` is a **differ** over fabrication output: Gerber (RS-274X) and
Excellon. It sits on the org's VERIFY layer, but it adjudicates a comparison
rather than a contract -- there is no declared intent to check against, so it
answers *identical / different / indeterminate* rather than *pass / fail*.

Two engines over the same parsed IR, and they are not interchangeable:

- **`diff`** rasterises both revisions through Cairo and reports changed
  pixels and regions. Correct, and hard to read: a small uniform shift renders
  as add/remove crescents indistinguishable from real material change.
- **`geomdiff`** works on the parsed vector geometry with shapely, and
  attributes each change as `added` / `removed` / `moved` / `resized`, down to
  micrometre displacements. Resolution-independent and Cairo-free.

**Version 0.30.0. Four verbs: `parse`, `render`, `diff`, `geomdiff`.**
`parse` reports diagnostics for one file; `render` writes a PNG of one file;
`diff` and `geomdiff` compare two directories. Only `geomdiff` can return the
third outcome -- see the exit-code section, where that asymmetry is spelled out
as the thing it is.

Treat this paragraph as code (org contract 2.5): the moment a verb is added,
removed, or gains an outcome it does not have, this section is false and the
change that made it false is not finished until it is corrected.

## Start here

**There is no `docs/DECISIONS.md` in this repository**, though the org contract
(section 7) points at one and most siblings have it. This repo's
numbered-decision equivalent is `CHANGELOG.md` plus the docstrings that carry
the reasoning at the point it binds -- `EXIT_*` in
`gerberdiff/cli.py`, `DiffOutcome` and `LayerGeometryDiff.unrepresented` in
`gerberdiff/geometry/types.py`. Cite a commit when you need to cite a decision.
If you are about to relitigate something, read the commit that settled it first.

Then:

1. `docs/schema.md` -- the JSON report schemas. This is a stable surface (org
   contract 5); consumers branch on it and on the exit code, never on the
   Python API.
2. `docs/geometry-diff.md` -- how the geometry engine works and what it does
   not model.
3. `docs/architecture.md` -- module layout and the parse/render/diff/geometry
   split.
4. `CONTRIBUTING.md` -- the ASCII rule, with the table of banned characters.

`planning/`, `artifacts/` and `outputs/` are **gitignored local scratch**, not
part of the repository (`.gitignore` lines 221-223, and `git ls-files planning`
returns nothing). `planning/` in particular holds the 2026-06 phase plan for
the geometry engine; its own README records that work as finished and the docs
as historical. Do not plan against it and do not treat it as a tracker.

## Stack

- **Python >= 3.11**, packaged with `hatchling`, `uv` against a committed
  `uv.lock`.
- **Runtime dependencies**: `click`, `numpy`, `cairocffi`, `scipy`, `shapely`.
  Adding another is org contract section 10 -- escalate, do not decide.
- **Tooling**: `ruff` (format + lint), `mypy` (strict), `pytest` +
  `pytest-cov`, `just`, `pre-commit`.
- The version is set in **both** `pyproject.toml` and `gerberdiff/__init__.py`.
  Nothing checks that they agree; keep them in sync by hand.

## Commands

```sh
just setup       # uv sync --dev
just fmt         # format + autofix (mutates the tree)
just check       # fmt-check + lint + ascii + typecheck -- the CI gate
just test        # pytest with the 90% coverage gate
just test-nocov  # pytest without it, as CI's Windows leg runs it
just hooks       # every pre-commit hook over the whole tree
```

Run `just check && just test` before every commit. Never `--no-verify`.

Every recipe inside `check` and `test` is a command `.github/workflows/ci.yml`
runs, with CI's arguments rather than tidier ones. Change a recipe and you must
change the workflow, or the name stops being true. Note that `check` includes
an **`ascii` recipe with no sibling equivalent**: CI greps `gerberdiff/ tests/
*.md *.toml` for anything outside U+0000-U+007F and fails on a hit, so an em
dash in this file would turn CI red.

`hooks` is not in `check` because nothing in `ci.yml` runs pre-commit. A green
`just check` says nothing about the hooks.

## Outcomes and exit codes

Settled in `0685cde` as org adjudication A3, and released in 0.30.0. These are
the org contract section 6.2 codes; gerberdiff conforms rather than chooses.

| Outcome | Exit | Meaning |
|---|---|---|
| `identical` | 0 | No differences, and everything was modelled. |
| `different` | 1 | Differences found. A finding about the fabrication output. |
| `indeterminate` | 2 | Part of the comparison could not be made. **Not** a statement about the boards. |
| -- | 4 | Could not read or parse an input. Not a statement about the boards either. |
| -- | 64 | Usage: bad arguments, or an output file that exists without `--overwrite`. |

Three things about this are load-bearing and each is enforced by code you can
read:

1. **`2` is a third *diff outcome*, not a verdict.** A differ answers a
   different question from a checker, so the word beside `identical` and
   `different` is `indeterminate`, not `fail`. The code and its meaning are the
   org's. `DiffOutcome` in `gerberdiff/geometry/types.py` is that enum.
2. **`different` outranks `indeterminate`.** A change that *was* found stays a
   finding even when some other operation could not be modelled; the reverse
   would let one unmodellable stroke mask a trace that actually moved.
   `GeometryDiffResult.outcome` implements the precedence.
3. **`indeterminate` does not wait for `--fail-on-diff`.** That flag chooses
   whether a *difference* is a failure. It has no bearing on whether the tool
   could look, so exit `2` is returned regardless of it
   (`gerberdiff/cli.py`, the `geomdiff` exit path).

**The raster `diff` verb has no third outcome.** It exits `0`, `1`, `4` or
`64` and never `2`. That is the current state of the code, not a design claim:
`geomdiff` knows an operation was unmodelled because `layer_geometry.py` counts
the reason, and the raster path has no equivalent record. Do not describe
`diff` as carrying the third outcome, and do not add a `2` to it by inference
-- if the raster engine can be blind in a way it can detect, that is a change
with a finding behind it.

## The rules that are not negotiable

1. **What was not modelled must never be reported as unchanged.** This is the
   whole of `0685cde` and the org's first rule in this repo's terms. When the
   geometry engine cannot build a shape it records the reason in
   `UNREPRESENTED_REASONS` (`gerberdiff/geometry/layer_geometry.py`), which
   makes the layer `indeterminate`. Before that existed, a layer full of
   unmodellable strokes reported `identical` at exit 0 with JSON
   byte-identical to comparing a board against a copy of itself.
2. **`import gerberdiff` stays Cairo-free.** The render path imports
   `cairocffi` lazily, so the parse and geometry pipelines work on a machine
   with no system Cairo. Verify with
   `python -c "import sys, gerberdiff; print('cairocffi' in sys.modules)"`; it
   must print `False`. A top-level render import puts the whole library behind
   a system library it does not need. The tests skip the raster engine
   separately, through `HAS_CAIRO` in `tests/cairo_support.py` --
   `pytest.importorskip` cannot do it, because `cairocffi` raises `OSError`
   rather than `ImportError` when the shared library is missing.
3. **Every tracked text file is pure ASCII (U+0000-U+007F).** Enforced by
   `just ascii` and by CI. `CONTRIBUTING.md` carries the replacement table:
   `--` for an em dash, `->` for an arrow, `>=` for the inequality.
4. **Coverage must not fall below 90%.** `just test` and CI both pass
   `--cov-fail-under=90`. `gerberdiff/cli.py` is omitted from the measurement
   (`[tool.coverage.run] omit`) because it is covered through integration
   tests; that omission is why the gate can be met without CLI unit tests, and
   it is not licence to move logic into `cli.py` to escape the gate.
5. **Do not reimplement geometry the library already does.** shapely owns the
   boolean operations and the Minkowski sums. Where the engine cannot express
   something, record it as unrepresented -- do not approximate it (org
   contract 2.3: never substitute a plausible number for an answer).
6. **`ok` is the only required status check.** Adding a job to `ci.yml` means
   adding it to the `ok` job's `needs:` and to its explicit
   `result != 'success'` test. This workflow does no path filtering, so a
   skipped job is always a defect and the tolerant `contains(needs.*.result,
   'failure')` form must not be used here (org contract 8.1).
7. Do not add AI attribution to commits or PR descriptions -- no co-author
   trailers, session links, or generated-with footers.
8. Do not name, link, or describe any private repository in public output.

## Related

Siblings, deliberately non-overlapping:

- `netspec` -- PCB connectivity against declared intent, with KiCad as the
  oracle. Run its checks, and KiCad's own ERC and DRC, **before** reaching for
  gerberdiff: they are cheaper and catch more. gerberdiff answers the last
  question, about the bytes the fab actually receives.
- `partspec` -- verifies CAD-as-code mechanical parts. Its
  `{identical: 0, different: 1, indeterminate: 2}` comparison verbs are where
  this repo's outcome vocabulary comes from.
- `slicelab` and `prusaslicer-py` -- slicer drivers. `orlab` -- OpenRocket.

Design review belongs to `kicad-happy`; authoring belongs to Konnect / SKiDL /
atopile. Neither is in scope here.
