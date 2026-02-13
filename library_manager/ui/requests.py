from __future__ import annotations

import json
import os
import random
import time

import wx

from ..config import Config
from ..github_api import GitHubError, GitHubRepo, create_file, get_token


def prompt_commit_message(parent: wx.Window, *, default: str) -> str | None:
    dlg = wx.TextEntryDialog(parent, "Commit message for this request:", "Commit message", value=str(default or ""))
    try:
        if dlg.ShowModal() != wx.ID_OK:
            return None
        msg = (dlg.GetValue() or "").strip()
        return msg or str(default or "").strip() or None
    finally:
        dlg.Destroy()


def submit_request(cfg: Config, *, action: str, payload: dict, commit_message: str | None) -> str:
    token = get_token()
    repo = GitHubRepo(
        owner=cfg.github_owner.strip(),
        repo=cfg.github_repo.strip(),
        base_branch=(cfg.github_base_branch.strip() or "main"),
    )

    user = os.environ.get("USER") or os.environ.get("USERNAME") or "user"
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    rnd = random.randint(0, 999999)
    req_name = f"{ts}_{user}_{rnd:06d}.json"
    path = f"Requests/{req_name}"

    body = {
        "schema_version": 1,
        "action": str(action or "").strip(),
        "created_at": ts,
        "created_by": user,
        "source": "kicad_plugin_ui",
    }
    body.update(dict(payload or {}))

    create_file(
        repo,
        token,
        path=path,
        branch=repo.base_branch,
        message=commit_message or f"request: {action}",
        content_text=json.dumps(body, indent=2, sort_keys=True) + "\n",
    )
    return path

