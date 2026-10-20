# Verdog CLI

Create, check, and run [Verdog](https://drexlerd.github.io/verdog-website/)
workflows from your terminal. Manage their Python environments, inspect runs,
and publish or reuse workflows from the catalogue.

## Installation

Requires Python 3.12 or later and Git. Install with
[uv](https://docs.astral.sh/uv/getting-started/installation/):

```sh
uv tool install verdog-cli
verdog --help
```

To update an existing installation, run `uv tool upgrade verdog-cli`.
See [Getting started](https://drexlerd.github.io/verdog-website/getting-started.html)
for project setup and a complete example.

## Run a workflow

From a workflow project's root:

```sh
verdog sync
verdog check
verdog run main
verdog runs main
```

- `sync` installs the Python environments required by the project.
- `check` validates the workflow and checks its Python types.
- `run main` executes the `main` workflow locally.
- `runs main` lists its recorded runs.

Use `verdog --help` or `verdog <command> --help` for available commands and options,
including inspecting checkpoints, resuming runs, and publishing workflows.

## Service and dependencies

Generation and structural checks use the configured Verdog service. Workflow
execution is local. Workflow code and its dependencies must be trusted before
installation or execution.

Install the CLI once as a tool. Workflow environments require the
[Verdog runtime](https://github.com/verdog-ai/verdog-runtime) and their declared
dependencies; you do not need to install the CLI into each environment.

## Sign in

`verdog login` exchanges a GitHub token for a service session saved in
`~/.config/verdog/session.json`; the GitHub token itself is not stored. The
service ends a session after 8 hours idle or 7 days. When a saved session has
expired and `gh` is signed in, the CLI exchanges `gh auth token` for a new
session, stores it, and retries the command once; set `VERDOG_NO_GH_LOGIN=1`
to turn this off. `verdog login --gh` signs in with gh's token explicitly.
Unattended agents should use a project token (`verdog token create`, 90 days)
instead; project tokens and editor sessions are never renewed through gh.

## Development

See [developer documentation](DEVELOPMENT.md) for setup, checks, integration
contracts, and release instructions.

## License

AGPL-3.0-only; see [LICENSE](LICENSE).
