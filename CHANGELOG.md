# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

No tracked entries yet.

## 0.2.0 - 2026-02-22

Minor release extending pathlib-style key path ergonomics.

- Added `Key.parent` and `Key.parents()` for lexical ancestor navigation.
- Added `Key.parts` plus `Key.from_parts(...)` / `Key.from_path(...)` for path round-tripping.
- Simplified rooted-key construction internals (`from_parts(...)` now uses direct rooted construction).
- **Breaking:** `Key.name` now returns only the final lexical segment; internal full relative path storage is kept private.
- Added `Key.iterdir()`, `Key.joinpath(...)`, `/` operator composition, and `Key.walk(...)` traversal (`os.walk`-like).

## 0.1.3 - 2026-02-22

Patch release adding traversal and pathlib-style path ergonomics.

- Added `Key.walk(...)` with `os.walk`-like semantics for key-tree traversal.
- Added `Key.iterdir()` as a pathlib-style alias for subkey iteration.
- Added `Key.joinpath(...)` and `/` operator support for key path composition.
- Expanded README method reference and examples for new traversal/path APIs.

## 0.1.2 - 2026-02-21

Patch release adding typing metadata for downstream type checkers.

- Added `py.typed` marker to declare inline typing support in `winregkit` (PEP 561).

## 0.1.1 - 2026-02-21

Patch release to validate automated GitHub Release notes.

- Publish workflow now uses GitHub-generated release notes for tag releases.

## 0.1.0 - 2026-02-21

First stable 0.1 release.

- Finalizes the 0.1 API surface for key traversal, typed value operations, and path-based key construction.
- Strengthens test coverage across fake and real backends, with backend-selective test flags for CI and local runs.
- Enforces formatting checks in CI alongside linting, tests, and Windows mypy checks.

## 0.1.0rc2 - 2026-02-21

Second release candidate for the 0.1 line.

- Publish workflow now creates a basic GitHub Release alongside PyPI publication.
- Release automation now avoids duplicate publish attempts from branch-triggered CI runs.

## 0.1.0rc1 - 2026-02-21

Initial release candidate for the 0.1 line.

- API surface refined for clearer typed value access and iteration naming.
- Cross-platform test strategy stabilized for real Windows `winreg` and fake backend coverage.
- CI and publish workflows aligned around `uv` tooling with release-tag-driven publishing.
- Project release/version workflow standardized on `uv version`.
