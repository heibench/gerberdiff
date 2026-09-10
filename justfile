# gerberdiff task runner
#
# Every recipe in `check` and `test` is a command .github/workflows/ci.yml runs.
# If you change one here, change it there; the point of this file is that
# `just check && just test` is the CI gate rather than a shorter list wearing
# its name. The path arguments are CI's, not `.`, for the same reason.

set dotenv-load := false

# Show available recipes
default:
    @just --list

# Install dependencies (ci.yml: `uv sync --dev` in all three jobs)
setup:
    uv sync --dev

# Update the lockfile after changing dependencies in pyproject.toml
lock:
    uv lock

# Format and apply lint fixes (mutates the working tree; CI never runs this)
fmt:
    uv run ruff format gerberdiff/ tests/
    uv run ruff check --fix gerberdiff/ tests/

# Verify formatting without mutating (ci.yml lint job)
fmt-check:
    uv run ruff format --check gerberdiff/ tests/

# Lint (ci.yml lint job)
lint:
    uv run ruff check gerberdiff/ tests/

# --exclude-dir is a no-op on CI's clean checkout and load-bearing locally:
# `just test` leaves __pycache__ behind, .pyc files contain non-ASCII bytes, and
# without it `just check` after `just test` fails on compiled output nobody wrote.
# ci.yml carries the same flag so the two commands stay one command.

# Every tracked text file is pure ASCII -- see CONTRIBUTING.md (ci.yml lint job)
ascii:
    #!/usr/bin/env bash
    set -euo pipefail
    if grep -rP --exclude-dir=__pycache__ '[^\x00-\x7F]' gerberdiff/ tests/ *.md *.toml; then
        echo "Non-ASCII characters found"
        exit 1
    fi

# Type-check (ci.yml typecheck job)
typecheck:
    uv run mypy gerberdiff/ tests/

# The CI-equivalent gate: everything ci.yml's lint and typecheck jobs run
check: fmt-check lint ascii typecheck

# Run tests with the coverage gate (ci.yml test job, Linux legs)
test:
    uv run pytest tests/ --cov=gerberdiff --cov-fail-under=90 -q

# ci.yml also passes --cov-report=xml on one leg, purely to upload the
# report as an artifact. Left out here: it writes a file nobody reads locally.

# Tests without the coverage gate -- ci.yml's Windows leg, where no system Cairo makes the raster tests skip
test-nocov:
    uv run pytest tests/ -q

# Run every pre-commit hook. Nothing in ci.yml runs these, so `just check` says nothing about them
hooks:
    pre-commit run --all-files

# Remove build and tool caches
clean:
    rm -rf dist .pytest_cache .ruff_cache .mypy_cache .coverage coverage.xml
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
