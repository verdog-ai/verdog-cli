"""The Codex sandbox preflight runs before `verdog run` starts a workflow."""

import json
import os
import stat
from pathlib import Path

from verdog_cli import runner


def _codex(tmp_path: Path, failing_mode: str | None = None) -> Path:
    """Install a fake codex that logs its argv and fails in one mode."""
    binary = tmp_path / "bin"
    binary.mkdir()
    log = tmp_path / "calls.jsonl"
    script = binary / "codex"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(log)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        f"if {failing_mode!r} and f'sandbox_mode=\"{failing_mode}\"' in sys.argv:\n"
        "    sys.exit('bwrap: Creating new namespace failed')\n",
        "utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return log


def _profile(provider: str, **options: object) -> dict[str, object]:
    return {
        "id": provider,
        "name": provider,
        "provider": provider,
        "options": {
            "model": None,
            "reasoning_effort": None,
            "extra_args": [],
            **options,
        },
    }


def _check(tmp_path: Path, project: dict[str, object]) -> str | None:
    environment = dict(os.environ)
    environment["PATH"] = f"{tmp_path / 'bin'}{os.pathsep}{environment['PATH']}"
    return runner.codex_sandbox_preflight(project, tmp_path, environment)


def _calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text("utf-8").splitlines()]


def test_preflight_runs_each_sandbox_once_per_codex_configuration(
    tmp_path: Path,
) -> None:
    log = _codex(tmp_path)
    network = ["-c", "sandbox_workspace_write.network_access=true"]
    project: dict[str, object] = {
        "workflows": [{"profiles": [_profile("codex", extra_args=network)]}],
        "subroutines": [
            {"profiles": [_profile("codex", extra_args=["--json", *network])]},
            {"profiles": [_profile("claude")]},
            {"profiles": [_profile("codex", danger_full_access=True)]},
        ],
    }
    assert _check(tmp_path, project) is None
    assert _calls(log) == [
        ["sandbox", *network, "-c", f'sandbox_mode="{mode}"', "--", "true"]
        for mode in ("read-only", "workspace-write")
    ]


def test_preflight_reports_the_sandbox_failure(tmp_path: Path) -> None:
    log = _codex(tmp_path, failing_mode="workspace-write")
    failure = _check(
        tmp_path, {"subroutines": [{"profiles": [_profile("codex")]}]}
    )
    assert failure is not None
    assert 'sandbox_mode="workspace-write"' in failure
    assert "bwrap: Creating new namespace failed" in failure
    assert len(_calls(log)) == 2


def test_projects_without_sandboxed_codex_profiles_skip_the_preflight(
    tmp_path: Path,
) -> None:
    log = _codex(tmp_path, failing_mode="read-only")
    project: dict[str, object] = {
        "subroutines": [
            {"profiles": [_profile("claude")]},
            {"profiles": [_profile("codex", danger_full_access=True)]},
        ]
    }
    assert _check(tmp_path, project) is None
    assert _calls(log) == []
