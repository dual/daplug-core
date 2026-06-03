# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

`daplug-core` is a shared library providing schema, merge, and SNS event publishing primitives for the daplug adapter ecosystem (`daplug-ddb`, `daplug-cypher`, etc.). It consolidates previously duplicated code from adapter `common/` directories into a single Python package.

**Key constraint**: This codebase is fully type-hinted and mypy (`pipenv run type-check`) is a CI gate. Add precise annotations to new code and keep mypy clean.

## Development Commands

### Environment Setup
```bash
pipenv install --dev
```

### Testing
```bash
# Run full test suite
pipenv run test

# Run tests with coverage report
pipenv run test-cov

# Run single test module
pipenv run pytest tests/test_publisher.py

# Run tests matching a pattern
pipenv run pytest tests/test_publisher.py -k "logs"

# Full coverage report (as used in CI)
pipenv run coverage
```

### Linting
```bash
# Lint with pylint (must score ≥10)
pipenv run lint
```

### Validation
```bash
# Verify imports resolve (fast syntax check)
python -m compileall daplug_core
```

## Architecture

### Core Modules

The package follows a flat module structure where each file in `daplug_core/` has a corresponding test file in `tests/`:

- **`base_adapter.py`** – Minimal SNS-aware adapter scaffold providing `publish()` and `create_format_attributes()` methods. Used as a mixin by downstream adapters (daplug-ddb, daplug-cypher).

- **`publisher.py`** – Thin wrapper over `boto3.SNSClient` with FIFO support (group/deduplication IDs) and structured logging via the logger module.

- **`logger.py`** – JSON stdout logger that respects `RUN_MODE=unittest` to suppress output during test runs.

- **`json_helper.py`** – Best-effort `try_encode_json` / `try_decode_json` utilities used by logger and publisher to handle non-serializable payloads gracefully.

- **`schema_loader.py`** – Loads OpenAPI/JSON schemas from YAML files and resolves `$ref` pointers using `jsonref`.

- **`schema_mapper.py`** – Recursively projects payloads into schema-shaped dictionaries. Supports `allOf` inheritance and nested object/array schemas.

- **`dict_merger.py`** – Deep merge utility with configurable strategies:
  - `update_list_operation`: `add` (default, unique append), `remove`, `replace`
  - `update_dict_operation`: `upsert` (default), `remove`

- **`event_registry.py`** – Module-level registry binding an SNS event name to the OpenAPI schema describing its payload (`register_event`, `get_event`, `all_events`, `clear`). Generate-only; not read on the publish hot path.

- **`asyncapi_generator.py`** – Builds an AsyncAPI 3.0 spec from registered events. `build_spec` (pure), `generate` (reads registry), `write_spec` (YAML dump), `main` (CLI with `--bootstrap`/`--output`). Payloads `$ref` `#/components/schemas/<key>` from the service's `openapi.yml` via `schema_loader`.

### Testing Philosophy

- **100% coverage** is enforced. Extend tests when touching modules.
- **Shared mocks** live in `tests/mocks/fakes.py` (e.g., `FakeSNSClient`, `RecordingLogger`). Extend this file rather than creating ad-hoc test doubles.
- Tests focus on **observable behavior**: captured SNS payloads, structured logs, transformed data structures.
- Use `tmp_path` fixture for tests requiring real files (e.g., schema_loader tests).
- Use `monkeypatch` to stub dependencies (e.g., stubbing `schema_loader.load_schema` in schema_mapper tests).

### Integration with Downstream Adapters

When `daplug-core` is updated, consuming repos (`daplug-ddb`, `daplug-cypher`) must:

1. Bump dependency version in their Pipfile/setup.py
2. Remove any residual `common/` code (now redundant)
3. Update imports: `from daplug_core import dict_merger` instead of `from .common.dict_merger import merge`
4. Re-run their test suites to verify compatibility

**Backwards compatibility matters**: Avoid breaking signature changes. When editing public APIs, ensure existing usage patterns in downstream adapters remain valid.

## Python & Tooling

- **Python version**: 3.9.17 (managed via pyenv, specified in `.python-version`)
- **Dependency management**: Pipenv (Pipfile + Pipfile.lock)
- **Linting**: pylint with custom `.pylintrc` (score must be ≥10)
- **Testing**: pytest with coverage enforcement
- **Line length**: 120 characters (enforced in both `.pylintrc` and `setup.cfg`)

## CI/CD

CircleCI workflows (`.circleci/config.yml`):

- **install-build-test-workflow** (on all branches):
  - Runs `pipenv run lint` and `pipenv run test`
  - Uploads coverage to SonarCloud
  - Stores test artifacts and HTML reports

- **install-build-publish-workflow** (on tags only):
  - Publishes to PyPI using version from `CIRCLE_TAG` environment variable

## Module-Specific Notes

### When editing `base_adapter.py`
- The `create_format_attributes` method converts SNS attributes to the boto3 format with `DataType` and `StringValue` fields
- Attributes are merged in order: `sns_defaults` → `call_attributes` → `{"operation": operation}`
- Only non-None values are included in the final message attributes

### When editing `publisher.py`
- Uses `RecordingLogger` mock in tests to verify structured logging
- Uses `FakeSNSClient` mock to capture SNS publish calls without hitting AWS
- FIFO attributes (`fifo_group_id`, `fifo_duplication_id`) are optional and only added when provided

### When editing `dict_merger.py`
- Operates on deep copies to avoid mutating input data
- List merge strategies: `add` appends unique items, `remove` matches items via JSON serialization, `replace` overwrites the entire list
- Dict merge strategies: `upsert` overwrites keys, `remove` deletes keys from the original

### When editing schema modules
- `schema_loader` expects real files on disk (use `tmp_path` in tests)
- `schema_mapper` handles `allOf` by merging schemas, then recursively projects each property
- Both modules are used together: load schema → map payload to schema shape
