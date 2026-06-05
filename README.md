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
- **Model-driven event catalog** – publish a self-naming Pydantic event model and `asyncapi_generator` reads those models to emit the AsyncAPI spec (exactly like OpenAPI generation reads decorated handlers). No hand-maintained catalog to drift; `required_payload_keys`/`required_headers` enforce the body + metadata contract before anything is published.

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
| `base_adapter.required_payload_keys` / `required_headers` | Transport-agnostic publish contract: the body keys and metadata headers that must be present, validated before publish (raises `PublishContractError`). |
| `asyncapi_generator` | Globs your Pydantic event models (those with an `event_name` ClassVar) and emits an AsyncAPI 3.0 spec — `payload` from the model, `headers` from the metadata contract. No hand catalog. |

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

This works exactly like OpenAPI generation: the developer writes normal typed
code, and `generate-asyncapi` **reads that code** to emit `api/v1/asyncapi.yml`,
which CI byte-diffs. There is **no hand-maintained catalog** — the event model is
the single source of truth, the same way a Pydantic response model is for OpenAPI.

An event is a **Pydantic model that names itself** via an `event_name` ClassVar;
its fields are the payload schema. Publish the model and daplug reads the name +
payload off it. The generator globs the event models, so an event cannot be
published without appearing in the spec.

### 1. Declare the event (the only thing the developer writes)

```python
# api/v1/events/document_events.py
from typing import ClassVar
from pydantic import BaseModel, Field

class DocumentCreated(BaseModel):
    """A document was created"""            # docstring -> AsyncAPI message title
    event_name: ClassVar[str] = "v1-documents-document-created"   # the ONLY place the name lives
    document_id: str = Field(examples=["doc-1"])
    user_id: str
    status: str = "draft"
    created: str
    modified: str
```

### 2. Publish it — daplug reads the name + payload off the model

```python
# the adapter detects the Pydantic model, dumps it, injects event_name as the
# 'event' header, and enforces the contract before anything reaches the transport
self.adapter.create(data=DocumentCreated.model_validate(document.to_dict()))
```

Declare the contract once on the adapter (transport-agnostic):

```python
daplug_ddb.adapter(
    ...,
    required_payload_keys=["document_id", "user_id", "status", "created", "modified"],  # message body
    required_headers=["event", "service", "version"],                                    # message metadata
)
```

`required_payload_keys` (body) and `required_headers` (metadata) are validated
**before publish** — a missing key raises `PublishContractError`, never a silent
half-event. They map onto the two halves of an AsyncAPI message: `payload` and
`headers`. Transport bindings stay operator-prefixed (`sns_arn`, future
`kafka_brokers`/`eventbridge_bus`); the contract names stay generic.

### 3. Generate the spec (mirrors `generate-openapi`)

```bash
python -m daplug_core.asyncapi_generator \
    --title documents --version v1 --channel documents \
    --events 'api/v1/events/**/*.py' \
    --output api/v1/asyncapi.yml
```

`--events` globs and imports the event modules, discovers every Pydantic model
carrying an `event_name`, and emits AsyncAPI 3.0: `payload` from
`model_json_schema()` (nested models inlined, no external `$ref`s) and `headers`
from the message metadata contract. Regenerate + diff in CI exactly like
`openapi.yml`; render to Confluence with `confluence-ops/publish-asyncapi`.

> The legacy `--bootstrap`/`event_registry` catalog path is retained, deprecated,
> only so in-flight repos migrate one event at a time.

### ⚠️ Models must mirror real nullability

You publish through the model (`publish_data=DocumentCreated.model_validate(item)`),
so the model is validated against the **actual** payload at runtime. If a field can
be `None` in practice, it **must** be `X | None = None` on the model — a model that
is *stricter* than the data raises `pydantic.ValidationError` and your endpoint
**500s**. Rule of thumb:

- A field is required on the model **only if it is always present and non-null** at
  publish time. Anything else is `X | None = None`.
- Cross-check each field against the entity dataclass / the `*CreateRequest` schema —
  a field that is optional/nullable on the request is nullable on the event.
- `payload()` dumps with `exclude_none=True`, so a null optional is simply omitted
  from the wire (the intended policy — not a dropped key); the schema marks it
  non-required automatically.

`integration-test-local` is the gate that catches an over-strict model (it exercises
the real publish paths with null-heavy payloads); if it 500s on `model_validate`,
loosen the offending field to `| None`.

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
