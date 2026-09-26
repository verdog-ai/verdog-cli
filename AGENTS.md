# Ownership

This file is maintained and reviewed by the user. Agents MUST NOT edit, delete,
rename, replace or regenerate it. Report outdated or conflicting instructions
and propose amendments in the conversation.

# Repository Scope

- This repository provides the public `verdog-cli` distribution and the `verdog` command.
- It owns local project management, service requests, dependency import/pinning,
  environment provisioning, type checking, and launching runtime operations.
- The compiler and hosted service live in `verdog`; execution lives in `verdog-runtime`.
- Use [pyproject.toml](pyproject.toml) for package metadata, dependency constraints,
  entry points, and tooling configuration; use [README.md](README.md) for setup.

# Dependency Chain

- Package dependency: CLI → public runtime, plus the dependencies declared in the manifest.
- API dependency: compiler and catalogue operations → the configured Verdog service.
  Backend packages must not become local CLI package dependencies.
- Git dependency: clone/import/pinning use Git and the user's Git credentials to fetch
  repository contents; the service provides authorization and metadata, not source bundles.
- Consumers: terminal users, editor integrations, and automation invoke the CLI.
  Generated workflow projects depend on the runtime rather than the CLI.
- Development may use the sibling runtime checkout as described in the README.
  Install its distribution normally: provisioning copies installed runtime files.
- Backend integration tests consume this CLI; extension integration tests check its
  machine-facing run-history contract. Coordinate changes to those shared contracts.

# Design Constraints

- Keep the CLI/runtime/backend package boundaries intact; reuse public runtime APIs.
- Compiler requests are anonymous. Catalogue/account operations use credentials bound
  to the selected service origin. Do not add a custom GitHub App or OAuth application.
- Resolve destination before credentials: command-specific origin, global backend flag,
  inherited backend origin, then project configuration or the hosted default.
  Saved credentials never redirect project requests. Global account commands may use
  the saved account's origin when no backend was selected explicitly.
- Preserve the session contract in [session.py](verdog_cli/session.py): marker `1` uses
  only stdin credentials bound to the original inherited origin; marker `0` excludes
  saved credentials; an absent marker allows matching standalone saved credentials.
- Never forward credentials across origins or redirects, or expose them in arguments,
  logs, project content, or compiler requests. Account administration needs a session.
- `describe --project` reads metadata without importing project code. Inspection callers
  launch the CLI from a trusted directory and pass the inspected path explicitly.
- Dependency installation requires trust. Wheels-only selection is not a sandbox.
  Keep installer startup isolated, its working directory in the new environment, and
  project source links absent until installation succeeds.
- Preserve exact dependency pins, filesystem containment, recovery on failed mutations,
  generated/authored ownership, and structured machine output.
- Workflow environments contain runtime and workflow dependencies, not CLI/backend code.

# Development and Validation

- Follow the installation instructions in the README and checks in
  [quality.yml](.github/workflows/quality.yml); do not invent a second toolchain.
- Before starting a local build, check whether another local build is active.
  Do not overlap local builds, and use at most 12 workers for a build.
- Use the manifest's quality configuration. After setup, run
  `uv run --no-sync ruff check .`, `uv run --no-sync ruff format --check .`,
  `uv run --no-sync pyright` and `uv run --no-sync pytest`.
  Run focused meaningful regressions during development; check distributions with
  `uv build` when packaging changes.
- Keep service transports and credentials isolated in tests. Test origin selection at
  the request boundary, and installer startup without network/package-download reliance.
- Validate changes to CLI JSON, generated-project compatibility, or runtime contracts
  against the relevant consumer integration tests. Do not require sibling repositories
  for ordinary standalone CLI checks.

# Release Flow

- Commit/push authorization does not authorize release, publishing, tagging, or deployment;
  obtain explicit authorization for those actions.
- [release.yml](.github/workflows/release.yml) is the release source of truth:
  matching version tag, quality checks, distributions, installed-wheel checks, then PyPI.
- Required runtime releases must be available before publishing a CLI that requires them.
  Required backend behavior must be deployed before consumers rely on it.
- Release a compatible CLI before an extension requires its new commands or JSON contract.
  Keep installation and compatibility documentation aligned with the shipped artifacts.
