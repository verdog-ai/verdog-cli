# Verdog CLI

The command-line client for [Verdog](https://drexlerd.github.io/verdog-website/).
It communicates with the hosted backend, manages projects and Python environments,
and launches and inspects local workflow executions.

The CLI depends on the public [runtime](https://github.com/verdog-ai/verdog-runtime).
Workflow environments contain the runtime and their declared dependencies; they do
not require this CLI. The private compiler and backend are not included.

## Installation

Requires Python 3.12 or later and Git. Install with
[uv](https://docs.astral.sh/uv/getting-started/installation/):

```sh
uv tool install --upgrade verdog-cli
verdog --help
```

If `verdog` was installed as a tool through the older combined runtime package,
replace that tool first:

```sh
uv tool uninstall verdog-runtime
uv tool install verdog-cli
```

This changes the tool installation, not project dependencies. Retain
`verdog-runtime` in generated workflow projects. See
[Getting started](https://drexlerd.github.io/verdog-website/getting-started.html)
for the extension and a complete example.

CLI 0.1.1 requires `verdog-runtime>=0.1.3,<0.2`. For existing agent profiles, remove
`options.web_search` from `project.json` and configure search through provider-native
`extra_args`. Regenerate sources with an updated backend using `verdog generate`
before running with runtime 0.1.3; previously generated `web_search=False` arguments
also need regeneration. See the [runtime migration notes](https://github.com/verdog-ai/verdog-runtime#verdog-runtime)
for provider arguments.

## Commands

From a workflow project's root:

```sh
verdog sync
verdog check
verdog run main
verdog runs main
```

`sync` provisions the CLI installation's runtime into the editor and workflow
environments, after checking the projects' declared runtime constraints. `check`
uses the hosted compiler and local Python type checking. `run` launches the runtime
with the selected workflow's interpreter. Run arguments, credentials, backend
configuration, and run directories retain their existing formats.

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

Use `verdog --help` or `verdog <command> --help` for the full command interface.

## Development

For a released runtime:

```sh
uv venv
uv pip install -e . --group dev
```

To develop this split before the matching runtime is published, check out
`verdog-runtime` beside this repository and install both local packages:

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

Existing runs remain inspectable. Exact resumption or forking of a checkpoint
created before the runtime split may be rejected by its runtime/environment
compatibility checks. Those checks are preserved.

## License

AGPL-3.0-only; see [LICENSE](LICENSE).
