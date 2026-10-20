# CLI development

## Development

For a released runtime:

```sh
uv venv
uv pip install -e . --group dev
```

To develop against a local runtime checkout, place `verdog-runtime` beside
this repository and install both packages:

```sh
uv venv
uv pip install ../verdog-runtime -e . --group dev
```

Reinstall the runtime after changing its source. The CLI provisions installed
runtime distributions, so use a regular runtime installation rather than an
editable runtime installation.

Run the checks in this environment:

```sh
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pyright
uv run --no-sync pytest
```

Tests isolate credentials and mock backend access. They do not publish workflows
or require a running backend. The backend repository has additional integration
tests for its compiler and service.

## Release

The `release.yml` workflow tests and packages this project when a `v*` tag is
pushed. The tag must match `project.version` in `pyproject.toml`.

Configure a GitHub environment named `pypi` and a PyPI Trusted Publisher for:

- Project: `verdog-cli`
- Owner: `verdog-ai`
- Repository: `verdog-cli`
- Workflow: `release.yml`
- Environment: `pypi`

Publish any newly required runtime version before releasing the CLI so the declared
dependency is available. Both the quality and release workflows install the runtime
from the package index; local sibling checkouts are only a development option.
Build locally with `uv build`.

## Integration contracts

`verdog runs --brief --json` lists validated run headers and current liveness
without loading checkpoint histories or artifact inventories. Its version 1 JSON
response has `operation: "runs"` and `brief: true`; run summaries omit
`checkpoints` and `sessions`. Trace activity is independent of the stored header's
`updated_at` timestamp. Use `--output /path/to/run` (repeatable, with `--brief`)
to inspect known runs directly without run discovery or registry reads. A recorded
running run whose execution lock is no longer held is reported as interrupted.
Load checkpoint details on demand with `verdog checkpoints /path/to/run --json`;
explicit output paths do not inspect unrelated runs.

A successful `verdog check` (including `--json`) writes a local receipt to
`.verdog/check.json` for editor integrations. Version 1 records the graph hash,
diagnostics, and SHA-256 hashes of the checked source/configuration files; absent
optional files have a `null` hash. It stores paths and hashes, not source content,
and stays on this machine. Consumers must verify those hashes before showing a
passed check. A new check removes the previous receipt before starting; failed
or interrupted checks leave no success receipt.

`describe main --project /path/to/project --json` reads graph and requirement
metadata without importing project code. Inspection tools should launch the CLI
from a trusted directory and pass the project path explicitly. Preparing or
selecting a Python environment belongs after importing into a trusted project.
`sync --only-binary` requests wheels; it is not a sandbox, and dependencies must
still be trusted. Sync isolates installer startup and adds project source paths
only after installation succeeds.

Backend selection is command `--origin` (or the `login` positional origin), then
`--backend-origin`, then `VERDOG_BACKEND_ORIGIN`, then the project's
`.git/verdog.json` origin or the hosted default. `init` and `clone` persist the
selected origin. Global account commands without an explicit backend use the
saved account's origin. A saved login never redirects a project's requests;
compiler calls are anonymous, and authenticated commands accept only credentials
for their selected origin. Standalone explicit backend overrides can use a
matching saved session. Repository tokens cannot administer account tokens.

Editor integrations set `VERDOG_SESSION_TOKEN_STDIN=1` for an ephemeral session
bound to the inherited `VERDOG_BACKEND_ORIGIN`, or `0` when no editor session is
available. Both modes exclude saved terminal and project credentials. A command
override cannot relabel an incoming session token for another origin. Omit the
marker for standalone saved-session authentication.

