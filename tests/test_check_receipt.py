"""Successful terminal and editor checks share one source-bound receipt."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from verdog_cli import api, local
from verdog_cli import main as cli
from verdog_cli.manage import blank_graph


def _clone(root: Path) -> local.Clone:
    root.mkdir(parents=True, exist_ok=True)
    project = blank_graph("test.receipt", "Check receipt")
    project["sources"] = [
        {"path": "source.py", "ownership": "user"},
        {"path": "missing.py", "ownership": "user"},
    ]
    (root / "project.json").write_text(json.dumps(project), encoding="utf-8")
    (root / "source.py").write_bytes("name = 'π'\r\n".encode())
    return local.Clone(root, "https://compiler.test", None)


def _backend(
    monkeypatch: pytest.MonkeyPatch,
    result: dict[str, Any],
) -> None:
    def check(_service: api.Service, _files: dict[str, str]) -> dict[str, Any]:
        return result

    monkeypatch.setattr(api.Service, "check", check)


@pytest.mark.parametrize("as_json", [False, True])
def test_success_records_projected_bytes_and_absent_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    as_json: bool,
) -> None:
    clone = _clone(tmp_path)
    warning = {"severity": "warning", "message": "Compiler warning"}
    typed_warning = {"severity": "warning", "message": "Type warning"}
    _backend(
        monkeypatch,
        {
            "graph_hash": "a" * 64,
            "files": {"source.py": "name = 'checked π'\r\n"},
            "diagnostics": [warning],
        },
    )

    def type_check(_clone: local.Clone) -> int:
        print("Type checker output")
        return 0

    def type_check_json(_clone: local.Clone) -> tuple[list[Any], int]:
        return [typed_warning], 0

    monkeypatch.setattr(cli, "_type_check", type_check)
    monkeypatch.setattr(cli, "_type_check_json", type_check_json)
    assert cli.check_clone(clone, as_json=as_json) == 0
    receipt = json.loads((tmp_path / ".verdog/check.json").read_text())
    assert receipt == {
        "version": 1,
        "graph_hash": "a" * 64,
        "diagnostics": [warning],
        "type_diagnostics": [typed_warning] if as_json else [],
        "sources": {
            "project.json": hashlib.sha256(
                (tmp_path / "project.json").read_bytes()
            ).hexdigest(),
            "source.py": hashlib.sha256(
                (tmp_path / "source.py").read_bytes()
            ).hexdigest(),
            "missing.py": None,
            "pyproject.toml": None,
            "ty.toml": None,
        },
    }
    output = capsys.readouterr().out
    if as_json:
        assert json.loads(output)["type_diagnostics"] == [typed_warning]
    else:
        assert "Type checker output" in output
    (tmp_path / "missing.py").write_text("value = 1\n")
    assert clone.check_sources() != receipt["sources"]


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize(
    "failure", ["structural", "types", "crash", "interrupted", "service"]
)
def test_unsuccessful_checks_invalidate_previous_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    as_json: bool,
    failure: str,
) -> None:
    clone = _clone(tmp_path)
    receipt = tmp_path / ".verdog/check.json"
    receipt.parent.mkdir()
    receipt.write_text("previous success")
    _backend(
        monkeypatch,
        {
            "files": {},
            "diagnostics": (
                [{"severity": "error", "message": "Invalid graph"}]
                if failure == "structural"
                else []
            ),
        },
    )

    def type_check(_clone: local.Clone) -> int:
        assert not receipt.exists()
        if failure == "crash":
            raise RuntimeError("type checker crashed")
        if failure == "interrupted":
            raise KeyboardInterrupt
        return int(failure == "types")

    def type_check_json(owner: local.Clone) -> tuple[list[Any], int]:
        return [], type_check(owner)

    def failed_service(
        _service: api.Service, _files: dict[str, str]
    ) -> dict[str, Any]:
        assert not receipt.exists()
        raise api.ServiceError("compiler unavailable")

    monkeypatch.setattr(cli, "_type_check", type_check)
    monkeypatch.setattr(cli, "_type_check_json", type_check_json)
    if failure == "service":
        monkeypatch.setattr(api.Service, "check", failed_service)
    if failure in {"structural", "types"}:
        assert cli.check_clone(clone, as_json=as_json) == 1
    else:
        error = {
            "crash": RuntimeError,
            "interrupted": KeyboardInterrupt,
            "service": api.ServiceError,
        }[failure]
        with pytest.raises(error):
            cli.check_clone(clone, as_json=as_json)
    assert not receipt.exists()


@pytest.mark.parametrize("changed", ["source.py", "missing.py", "ty.toml"])
def test_source_changes_during_type_check_are_not_stamped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    clone = _clone(tmp_path)
    _backend(monkeypatch, {"files": {}, "diagnostics": []})

    def type_check(_clone: local.Clone) -> int:
        (tmp_path / changed).write_text("changed = 1\n")
        return 0

    monkeypatch.setattr(cli, "_type_check", type_check)
    with pytest.raises(local.WorkspaceError, match="during type checking"):
        cli.check_clone(clone)
    assert not (tmp_path / ".verdog/check.json").exists()


def test_source_change_after_projection_is_not_stamped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = _clone(tmp_path)
    _backend(monkeypatch, {"files": {}, "diagnostics": []})
    original_sources = local.Clone.check_sources

    def changed_sources(
        owner: local.Clone, *, expected: dict[str, str] | None = None
    ) -> dict[str, str | None]:
        (tmp_path / "source.py").write_text("changed = 1\n")
        return original_sources(owner, expected=expected)

    monkeypatch.setattr(local.Clone, "check_sources", changed_sources)
    with pytest.raises(local.WorkspaceError, match="after projection"):
        cli.check_clone(clone)
    assert not (tmp_path / ".verdog/check.json").exists()


@pytest.mark.parametrize(
    "linked", [".verdog", ".verdog/check.json", "source.py", "ty.toml"]
)
def test_check_receipt_rejects_symlink_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, linked: str
) -> None:
    clone = _clone(tmp_path / "project")
    outside = tmp_path / "outside"
    outside.mkdir()
    protected = outside / "check.json"
    protected.write_text("outside data")
    path = clone.root / linked
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    path.symlink_to(outside if linked == ".verdog" else protected)
    _backend(monkeypatch, {"files": {}, "diagnostics": []})
    with pytest.raises(local.WorkspaceError, match="symbolic link"):
        cli.check_clone(clone)
    assert protected.read_text() == "outside data"
