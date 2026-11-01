"""Run a workflow through the interpreter in its isolated root environment."""

from __future__ import annotations

import dataclasses
import os
import pathlib
import subprocess
import sys
from collections.abc import Mapping
from typing import Any, Literal, cast

from verdog_runtime import runs as runtime_runs

from verdog_cli import local, sync


@dataclasses.dataclass(frozen=True, slots=True)
class LifecycleRequest:
    """A resume, restart, or fork request for an isolated workflow process."""

    operation: runtime_runs.Operation
    source: pathlib.Path
    workflow_id: str
    sessions: runtime_runs.SessionMode
    checkpoint: int | None = None
    arguments: tuple[str, ...] = ()
    arguments_mode: runtime_runs.ArgumentMode = "checkpoint"
    retry_incomplete: bool = False
    as_json: bool = False


def _isolated_environment(
    environment: pathlib.Path, interpreter: pathlib.Path, /
) -> dict[str, str]:
    process_environment = os.environ.copy()
    process_environment.pop("PYTHONHOME", None)
    process_environment.pop("PYTHONPATH", None)
    process_environment["PYTHONNOUSERSITE"] = "1"
    process_environment["VIRTUAL_ENV"] = str(environment)
    path = process_environment.get("PATH")
    process_environment["PATH"] = str(interpreter.parent) + (
        os.pathsep + path if path else ""
    )
    return process_environment


def _runtime(
    clone: local.Clone, workflow_id: str | None, /
) -> tuple[str, str, pathlib.Path, dict[str, str]]:
    workflow = clone.workflow_definition(workflow_id)
    environment = sync.require_current_workflow_environments(clone, workflow)
    interpreter = local.interpreter_in(environment)
    if interpreter is None:
        raise local.WorkspaceError(
            f"{environment} has no Python interpreter; run `verdog sync`"
        )
    return (
        workflow.id,
        workflow.module,
        interpreter,
        _isolated_environment(environment, interpreter),
    )


_SANDBOX_MODES = ("read-only", "workspace-write")


def _config_arguments(extra_args: object, /) -> tuple[str, ...]:
    """Keep the profile's `-c` overrides, such as sandbox network access."""
    values = (
        [str(item) for item in cast(list[object], extra_args)]
        if isinstance(extra_args, list)
        else []
    )
    result: list[str] = []
    for index, argument in enumerate(values):
        if argument in ("-c", "--config") and index + 1 < len(values):
            result.extend(("-c", values[index + 1]))
        elif argument.startswith("--config="):
            result.extend(("-c", argument.removeprefix("--config=")))
        elif (
            argument.startswith("-c")
            and not argument.startswith("--")
            and (value := argument[2:].removeprefix("="))
        ):
            result.extend(("-c", value))
    return tuple(result)


def codex_sandbox_preflight(
    project: Mapping[str, Any],
    cwd: pathlib.Path,
    environment: Mapping[str, str],
    /,
) -> str | None:
    """Run `true` in each sandbox a Codex profile may use; describe a failure.

    Codex reports a sandbox that cannot start only as failed tool calls, so
    the run would continue with an agent that cannot act.
    """
    configurations: set[tuple[str, ...]] = set()
    for owner in ("workflows", "subroutines"):
        for graph in cast(list[Any], project.get(owner) or []):
            for profile in cast(list[Any], graph.get("profiles") or []):
                options = cast(dict[str, Any], profile.get("options") or {})
                if (
                    profile.get("provider") == "codex"
                    and options.get("danger_full_access") is not True
                ):
                    configurations.add(
                        _config_arguments(options.get("extra_args"))
                    )
    # ponytail: local profiles only; external projects' profiles run unchecked.
    for configuration in sorted(configurations):
        for mode in _SANDBOX_MODES:
            command = [
                "codex",
                "sandbox",
                *configuration,
                "-c",
                f'sandbox_mode="{mode}"',
                "--",
                "true",
            ]
            try:
                result = subprocess.run(  # noqa: S603 - fixed argv, no shell
                    command,
                    cwd=cwd,
                    env=dict(environment),
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                return f"{' '.join(command)}: {error}"
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()[-2000:]
                return f"{' '.join(command)} exited with {result.returncode}: {detail}"
    return None


def run(
    clone: local.Clone,
    output_dir: pathlib.Path | None = None,
    *,
    workflow_id: str | None = None,
    arguments: tuple[str, ...] = (),
    checkpointing: Literal["off", "auto", "required"] = "auto",
    preflight: bool = True,
) -> int:
    """Trampoline into one workflow definition's own interpreter."""
    definition_id, definition_module, interpreter, process_environment = (
        _runtime(clone, workflow_id)
    )
    failure = (
        codex_sandbox_preflight(clone.project, clone.root, process_environment)
        if preflight
        else None
    )
    if failure is not None:
        print(
            f"verdog run: the Codex sandbox cannot run a command here.\n"
            f"{failure}\n"
            'Set "danger_full_access": true in the Codex profiles\' options '
            "for hosts where the sandbox cannot start, or pass "
            "--skip-preflight.",
            file=sys.stderr,
        )
        return 1
    requested = "" if output_dir is None else str(output_dir.resolve())
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            str(interpreter),
            "-m",
            "verdog_runtime.entry",
            str(clone.root),
            definition_id,
            definition_module,
            requested,
            f"--verdog-checkpointing={checkpointing}",
            *arguments,
        ],
        cwd=clone.root,
        env=process_environment,
        check=False,
    ).returncode


def operate(
    clone: local.Clone,
    request: LifecycleRequest,
    /,
) -> int:
    """Trampoline a run lifecycle operation into its workflow environment."""
    definition_id, definition_module, interpreter, process_environment = (
        _runtime(clone, request.workflow_id)
    )
    lifecycle = runtime_runs.LifecycleCommand(
        operation=request.operation,
        root=clone.root.resolve(),
        definition_id=definition_id,
        definition_module=definition_module,
        source_output=request.source.resolve(),
        sessions=request.sessions,
        checkpoint=request.checkpoint,
        arguments_mode=request.arguments_mode,
        retry_incomplete=request.retry_incomplete,
        as_json=request.as_json,
        arguments=request.arguments,
    )
    command = [
        str(interpreter),
        "-m",
        "verdog_runtime.entry",
        "--verdog-lifecycle",
        runtime_runs.encode_lifecycle_command(lifecycle),
    ]
    return subprocess.run(  # noqa: S603 - fixed interpreter and argv, no shell
        command,
        cwd=clone.root,
        env=process_environment,
        check=False,
    ).returncode
