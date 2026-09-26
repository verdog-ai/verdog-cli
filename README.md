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

Publish runtime 0.1.2 before the first CLI release so the declared dependency is
available. Both the quality and release workflows install the declared runtime
from the package index; local sibling checkouts are only a development option.
Build locally with `uv build`.

Existing runs remain inspectable. Exact resumption or forking of a checkpoint
created before the runtime split may be rejected by its runtime/environment
compatibility checks. Those checks are preserved.

## License

AGPL-3.0-only; see [LICENSE](LICENSE).
