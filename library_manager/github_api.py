from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass

from ._subprocess import SUBPROCESS_NO_WINDOW


GITHUB_API = "https://api.github.com"


@dataclass(frozen=True)
class GitHubRepo:
    owner: str
    repo: str
    base_branch: str = "main"


class GitHubError(RuntimeError):
    pass


def _read_gh_hosts_token() -> str | None:
    # ~/.config/gh/hosts.yml contains oauth_token for github.com.
    path = os.path.join(os.path.expanduser("~"), ".config", "gh", "hosts.yml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read()
    except Exception:
        return None

    in_github = False
    for raw in txt.splitlines():
        line = raw.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        if not line.startswith(" ") and line.strip().endswith(":"):
            host = line.strip()[:-1]
            in_github = host == "github.com"
            continue
        if in_github and "oauth_token:" in line:
            _, v = line.split("oauth_token:", 1)
            token = v.strip().strip('"').strip("'")
            return token or None
    return None


def get_token() -> str:
    # Priority:
    # 1) env var (allows CI/testing)
    # 2) gh CLI
    # 3) gh config file
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("KICAD_LIBRARY_MANAGER_GITHUB_TOKEN")
    if env:
        return env.strip()

    try:
        cp = subprocess.run(
            ["gh", "auth", "token"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            **SUBPROCESS_NO_WINDOW,
        )
        tok = (cp.stdout or "").strip()
        if tok:
            return tok
    except Exception:
        pass

    tok = _read_gh_hosts_token()
    if tok:
        return tok

    raise GitHubError(
        "No GitHub token found. Please authenticate with `gh auth login` "
        "or set GITHUB_TOKEN / KICAD_LIBRARY_MANAGER_GITHUB_TOKEN."
    )


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "kicad-library-manager")
    if data is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8", errors="replace")
        except Exception:
            msg = str(e)
        raise GitHubError(f"GitHub API error: {e.code} {e.reason}: {msg}")
    except urllib.error.URLError as e:
        raise GitHubError(f"GitHub API connection error: {e}")


def get_ref_sha(repo: GitHubRepo, token: str, branch: str) -> str:
    url = f"{GITHUB_API}/repos/{repo.owner}/{repo.repo}/git/ref/heads/{branch}"
    data = _request("GET", url, token)
    sha = (((data or {}).get("object") or {}).get("sha") or "").strip()
    if not sha:
        raise GitHubError(f"Could not resolve branch SHA for {branch}")
    return sha


def get_branch_head_sha(repo: GitHubRepo, token: str) -> str:
    """
    Convenience: latest commit SHA for repo.base_branch.
    """
    return get_ref_sha(repo, token, repo.base_branch)


def create_branch(repo: GitHubRepo, token: str, new_branch: str, from_sha: str) -> None:
    url = f"{GITHUB_API}/repos/{repo.owner}/{repo.repo}/git/refs"
    _request("POST", url, token, {"ref": f"refs/heads/{new_branch}", "sha": from_sha})


def get_file(repo: GitHubRepo, token: str, path: str, ref: str) -> tuple[str, str]:
    """
    Returns (decoded_text, sha)
    """
    url = f"{GITHUB_API}/repos/{repo.owner}/{repo.repo}/contents/{path}?ref={ref}"
    data = _request("GET", url, token)
    content_b64 = (data.get("content") or "").encode("utf-8")
    sha = (data.get("sha") or "").strip()
    if not sha:
        raise GitHubError(f"Missing sha for file {path}")
    decoded = base64.b64decode(content_b64).decode("utf-8", errors="replace")
    return decoded, sha


def put_file(repo: GitHubRepo, token: str, path: str, branch: str, message: str, content_text: str, sha: str) -> None:
    url = f"{GITHUB_API}/repos/{repo.owner}/{repo.repo}/contents/{path}"
    content_b64 = base64.b64encode(content_text.encode("utf-8")).decode("utf-8")
    _request(
        "PUT",
        url,
        token,
        {
            "message": message,
            "content": content_b64,
            "branch": branch,
            "sha": sha,
        },
    )


def create_file(repo: GitHubRepo, token: str, path: str, branch: str, message: str, content_text: str) -> None:
    """
    Create a brand-new file. This will fail if the file already exists.
    """
    url = f"{GITHUB_API}/repos/{repo.owner}/{repo.repo}/contents/{path}"
    content_b64 = base64.b64encode(content_text.encode("utf-8")).decode("utf-8")
    _request(
        "PUT",
        url,
        token,
        {
            "message": message,
            "content": content_b64,
            "branch": branch,
        },
    )


def create_pr(repo: GitHubRepo, token: str, head: str, title: str, body: str) -> str:
    url = f"{GITHUB_API}/repos/{repo.owner}/{repo.repo}/pulls"
    data = _request(
        "POST",
        url,
        token,
        {"title": title, "head": head, "base": repo.base_branch, "body": body},
    )
    html_url = (data.get("html_url") or "").strip()
    if not html_url:
        raise GitHubError("Failed to create PR (missing html_url)")
    return html_url

