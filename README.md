# 🧩 daplug-core (da•plug)

> **Shared schema + event plumbing for daplug-* adapters**

[![CircleCI](https://circleci.com/gh/dual/daplug-core.svg?style=shield)](https://circleci.com/gh/dual/daplug-core)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=dual_daplug-core&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=dual_daplug-core)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=dual_daplug-core&metric=bugs)](https://sonarcloud.io/summary/new_code?id=dual_daplug-core)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=dual_daplug-core&metric=coverage)](https://sonarcloud.io/summary/new_code?id=dual_daplug-core)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![PyPI package](https://img.shields.io/pypi/v/daplug-core?color=blue&label=pypi%20package)](https://pypi.org/project/daplug-core/)
[![License](https://img.shields.io/badge/license-apache%202.0-blue)](LICENSE)
[![Contributions](https://img.shields.io/badge/contributions-welcome-blue)](https://github.com/paulcruse3/daplug-core/issues)

`daplug-core` is the tiny layer of glue that both `daplug-ddb`, `daplug-cypher`, and future `daplug-*` projects, relied on in their old `common/` directories. It bundles a publisher, logging shim, schema utilities, and merge helpers so the higher-level adapters can stay laser-focused on their respective datastores. This repository is not meant to be a fully fledged adapter on its own—it simply centralizes the primitives the adapters share.

---

## 🌈 Why this exists

- **Single source of truth** – The DynamoDB and Cypher adapters used to carry duplicate copies of the same helpers. `daplug-core` keeps those modules in one place.
- **Batteries-included SNS publishing** – The base `publisher` encapsulates SNS fan-out, FIFO metadata, and logging so consuming packages can just hand it messages.
- **Schema-first tooling** – `schema_loader` and `schema_mapper` read OpenAPI/JSON schemas and project payloads to the shapes your adapters expect.
- **Deterministic merging** – `dict_merger` upgrades nested payloads with configurable list/dict strategies (add, replace, remove) so you can keep optimistic writes tight.
- **Model-driven event catalog** – `event_registry` + `asyncapi_generator` turn the events you already publish through daplug into a generated AsyncAPI spec. Because publishing flows through daplug, the catalog is derived from your models instead of hand-written and drifting.

If you are migrating `daplug-ddb` or `daplug-cypher`, remove their legacy `common/` folder and import from `daplug_core` instead. Nothing else changes.

---

## 📦 Installation

```bash
pip install daplug-core
# or
pipenv install daplug-core
```

> Not on PyPI yet? Until release, install straight from the repo:
>
> ```bash
> pip install git+https://github.com/paulcruse3/daplug-core.git
> ```

---

## 🔁 How consuming packages use the base

1. **Declare the dependency** in the adapter package (e.g. `daplug-ddb`) via Pipfile/pyproject.
2. **Drop the duplicated modules** (`common/logger.py`, `common/publisher.py`, etc.).
3. **Import from `daplug_core`** wherever those utilities were previously referenced.

```python
# inside daplug-ddb
from daplug_core import dict_merger, json_helper, publisher, schema_mapper

merged = dict_merger.merge(original, incoming, update_list_operation="replace")
publisher.publish(arn=sns_arn, data=merged, attributes={"event": "updated"})
```

Because the API surface stayed the same, adapter code typically only needs import-path updates.

---

## 🧱 Building blocks

| Module | Purpose |
| ------ | ------- |
| `base_adapter.BaseAdapter` | Minimal SNS-aware adapter scaffold (used as a mixin by higher-level adapters). |
| `publisher.publish` | Thin wrapper over `boto3` SNS clients with FIFO group/dedupe support and structured logging. |
| `logger.log` | Consistent JSON stdout logging that honors `RUN_MODE=unittest`. |
| `json_helper` | Best-effort `try_encode_json` / `try_decode_json` helpers used by loggers and publishers. |
| `schema_loader.load_schema` | Loads an OpenAPI/JSON schema and resolves `$ref`s using `jsonref`. |
| `schema_mapper.map_to_schema` | Recursively projects payloads into schema-shaped dictionaries (supports `allOf` inheritance). |
| `dict_merger.merge` | Deep merge with per-call list/dict strategies (`add`, `remove`, `replace`, `upsert`). |
| `event_registry.register_event` | Declares an event name and the schema (`schema_file` + `schema_key`) that describes its payload. |
| `asyncapi_generator` | Builds an AsyncAPI 3.0 spec from the registered events, `$ref`-ing the same OpenAPI schemas your API already defines. |

Mix and match these pieces inside datastore-specific adapters.

### 🔕 Per-call publish controls

`BaseAdapter.publish` recognises two extra kwargs that adapters propagate
through their `create`/`update`/`delete` method calls:

| Kwarg | Effect |
| ----- | ------ |
| `publish=False` | Skip the SNS publish for this call only. Defaults are unchanged. |
| `publish_data=<payload>` | Publish this payload to SNS instead of the data the adapter just wrote. Useful when the SNS consumers want a different shape than the row that was stored. |

```python
adapter.create(data=row, publish=False)             # write, do not notify
adapter.update(data=row, publish_data={"id": row["id"], "event": "updated"})
```

If both are passed, `publish=False` wins.

---

## 📣 Event catalog generation (AsyncAPI)

Services that publish through daplug shouldn't hand-maintain a separate `EVENTS.md`.
The payload of every event is just a model snapshot, and that model is already
described in the service's `openapi.yml` under `components/schemas`. `event_registry`
and `asyncapi_generator` turn that into a generated, verifiable contract.

> **Generate-only today.** The registry is read at build time to emit the spec.
> It does not validate or reshape payloads on the publish hot path (a possible
> future follow-up).

### 1. Register each event next to where it is published

```python
from daplug_core import event_registry

event_registry.register_event(
    "v1-documents-document-created",   # the SNS `event` attribute
    "api/v1/openapi.yml",              # schema_file: where the payload schema lives
    "Document",                        # schema_key: the components/schemas key
    "A document was created",          # optional human description
)
```

Registration is the single source that binds an **event name** to the **model
schema** describing its payload. The same map can later gate CI (every published
event name must be registered) and drive publish-time validation.

### 2. Generate the spec

```bash
python -m daplug_core.asyncapi_generator \
    --title documents \
    --version v1 \
    --channel documents \
    --bootstrap api.v1.persistence.events_registry \
    --output api/v1/asyncapi.yml
```

`--bootstrap` imports the module(s) that call `register_event` so the registry is
populated before the spec is written (repeatable). The emitted `asyncapi.yml` is
AsyncAPI 3.0: each event becomes a message whose `payload` `$ref`s
`#/components/schemas/<schema_key>`, pulled from your OpenAPI file via
`schema_loader` (so REST and events share one schema definition).

### 3. Verify and publish like OpenAPI

Treat the generated file exactly like `openapi.yml`: regenerate it in CI and diff
against the committed copy (fails on drift), then render it to Confluence. Because
the spec is generated from registered events, an undocumented event can't be
omitted and a stale payload can't survive the diff.

### Programmatic use

```python
from daplug_core import asyncapi_generator

spec = asyncapi_generator.generate(title="documents", version="v1", channel="documents")
asyncapi_generator.write_spec(spec, "api/v1/asyncapi.yml")
```

---

## 🧭 Example: refactoring `daplug-ddb`

```python
# before (inside daplug_ddb/common/publisher.py)
from . import logger
import boto3

# after
from daplug_core import publisher

publisher.publish(
    arn=self.sns_arn,
    data=payload,
    fifo_group_id=fifo_group,
    fifo_duplication_id=fifo_dedupe,
    attributes={"source": "daplug-ddb"},
)
```

```python
# before
from .common.dict_merger import merge

# after
from daplug_core import dict_merger

updated_item = dict_merger.merge(original, patch, update_list_operation="replace")
```

The same pattern applies inside `daplug-cypher` when merging node payloads or formatting SNS events.

---

## ⚙️ Local development

```bash
git clone https://github.com/paulcruse3/daplug-core.git
cd daplug-core
pipenv install --dev
```

### Run tests & coverage

```bash
pipenv run test       # pytest tests/
pipenv run test-cov   # pytest --cov=daplug_core --cov-report=term-missing
pipenv run lint       # pylint --fail-under 10 daplug_core
```

### Ship updates downstream

1. Bump the version in `setup.py` (and `setup.cfg` if needed).
2. Publish to PyPI or deliver a git tag.
3. Update `daplug-ddb` and `daplug-cypher` to depend on the new version.
4. Remove any residual `common/` references in those repos and re-run their suites.

---

## 🤝 Contributing

Pull requests are welcome—especially improvements that make life easier for the DynamoDB and Cypher adapters. If you add a helper here, remember to wire it up in the consuming packages as well.

```bash
git checkout -b feat/better-schema-mapper
pipenv run test-cov
pipenv run lint
git commit -am "feat: better schema mapper"
```

---

## 📄 License

Apache 2.0 – see [LICENSE](LICENSE).
