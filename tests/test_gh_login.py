"""An expired saved session is renewed once through gh, never otherwise."""

import json
import subprocess
from io import BytesIO, StringIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from verdog_cli import main as cli
from verdog_cli.local import Clone, write_config
from verdog_cli.manage import blank_graph
from verdog_cli.session import Login, config_home, load, store

GITHUB_TOKEN = "gho_github-secret-from-gh"
ORIGIN = "https://verdog.test"


def _expired(request: Request) -> HTTPError:
    body = b'{"error":{"code":"auth.required","message":"authentication is required"}}'
    return HTTPError(request.full_url, 401, "Unauthorized", None, BytesIO(body))  # type: ignore[arg-type]


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """A gh stub that hands out a token; records each invocation."""
    monkeypatch.delenv("VERDOG_NO_GH_LOGIN")
    calls: list[list[str]] = []

    def run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        assert kwargs["timeout"]
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, f"{GITHUB_TOKEN}\n", "")

    monkeypatch.setattr("verdog_cli.session.subprocess.run", run)
    return calls


def _service(monkeypatch: pytest.MonkeyPatch, *, valid: set[str]) -> list[str]:
    """Answer /me for tokens in `valid`, auth.required otherwise."""
    requests: list[str] = []

    def respond(request: Request, *, timeout: float) -> BytesIO:
        assert timeout > 0
        requests.append(f"{request.get_method()} {request.full_url}")
        if request.full_url.endswith("/api/v1/auth/github"):
            assert isinstance(request.data, bytes)
            assert json.loads(request.data) == {"access_token": GITHUB_TOKEN}
            return BytesIO(
                b'{"session_token":"fresh-session","user":{"login":"ada"}}'
            )
        if request.get_header("Authorization") in {
            f"Bearer {t}" for t in valid
        }:
            return BytesIO(b'{"user":{"login":"ada"},"seat":true}')
        raise _expired(request)

    monkeypatch.setattr("verdog_cli.api.urlopen", respond)
    return requests


def test_expired_session_is_renewed_once_through_gh(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    gh: list[list[str]],
) -> None:
    store(Login(ORIGIN, "expired-session", "ada"))
    requests = _service(monkeypatch, valid={"fresh-session"})
    assert cli.main(["whoami"]) == 0
    assert gh == [["gh", "auth", "token", "--hostname", "github.com"]]
    assert requests == [
        f"GET {ORIGIN}/api/v1/me",
        f"POST {ORIGIN}/api/v1/auth/github",
        f"GET {ORIGIN}/api/v1/me",
    ]
    assert load() == Login(ORIGIN, "fresh-session", "ada")
    captured = capsys.readouterr()
    assert "Session expired; signing in again through gh" in captured.err
    assert "ada at" in captured.out
    assert GITHUB_TOKEN not in captured.out + captured.err
    for path in config_home().rglob("*"):
        assert GITHUB_TOKEN not in path.read_text("utf-8")


def test_second_refusal_is_reported_without_another_attempt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    gh: list[list[str]],
) -> None:
    store(Login(ORIGIN, "expired-session", "ada"))
    requests = _service(monkeypatch, valid=set())
    assert cli.main(["whoami"]) == 1
    assert len(gh) == 1
    assert len(requests) == 3
    assert "run `verdog login`" in capsys.readouterr().err


@pytest.mark.parametrize(
    "failure", ["missing", "signed-out", "timeout", "opt-out"]
)
def test_without_gh_the_error_is_reported_as_before(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    monkeypatch.delenv("VERDOG_NO_GH_LOGIN")
    if failure == "opt-out":
        monkeypatch.setenv("VERDOG_NO_GH_LOGIN", "1")

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        assert failure != "opt-out"
        if failure == "missing":
            raise FileNotFoundError(command[0])
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 10)
        return subprocess.CompletedProcess(command, 1, "", "not logged in")

    monkeypatch.setattr("verdog_cli.session.subprocess.run", run)
    store(Login(ORIGIN, "expired-session", "ada"))
    requests = _service(monkeypatch, valid=set())
    assert cli.main(["whoami"]) == 1
    assert requests == [f"GET {ORIGIN}/api/v1/me"]
    assert "auth.required" in capsys.readouterr().err
    assert load().token == "expired-session"


def test_project_token_never_triggers_gh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gh: list[list[str]]
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "project.json").write_text(
        json.dumps(blank_graph("test.project", "Project token")), "utf-8"
    )
    write_config(tmp_path, ORIGIN, "expired-project-token")
    monkeypatch.chdir(tmp_path)

    def repository(_clone: Clone) -> tuple[str, str]:
        return "ada", "tools"

    monkeypatch.setattr(Clone, "require_repository", repository)
    requests = _service(monkeypatch, valid=set())
    assert cli.main(["access"]) == 1
    assert gh == []
    assert len(requests) == 1


def test_stdin_handoff_never_triggers_gh(
    monkeypatch: pytest.MonkeyPatch, gh: list[list[str]]
) -> None:
    store(Login(ORIGIN, "expired-session", "ada"))
    monkeypatch.setenv("VERDOG_BACKEND_ORIGIN", ORIGIN)
    monkeypatch.setenv("VERDOG_SESSION_TOKEN_STDIN", "1")
    monkeypatch.setattr("sys.stdin", StringIO("expired-editor-session\n"))
    _service(monkeypatch, valid=set())
    assert cli.main(["whoami"]) == 1
    assert gh == []


def test_login_gh_signs_in_with_gh_token(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    gh: list[list[str]],
) -> None:
    _service(monkeypatch, valid=set())
    assert cli.main(["login", ORIGIN, "--gh"]) == 0
    assert len(gh) == 1
    assert load() == Login(ORIGIN, "fresh-session", "ada")
    captured = capsys.readouterr()
    assert "Signed in as ada" in captured.out
    assert GITHUB_TOKEN not in captured.out + captured.err
