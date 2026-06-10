#!/usr/bin/env python3
"""
GitHub blueprint sync — bridge between the deployed app and the local pipeline.

The deployed "Add Client" tab commits blueprints to a GitHub folder (see
api/upload-blueprint.js). This module lets the automation pull that folder into
the local intake directory before each run, and (optionally) push a blueprint.

Config via environment variables (e.g. a .env file):
  GITHUB_REPO           "owner/repo"            (required)
  GITHUB_TOKEN          PAT, Contents: Read[/Write]   (required for private repos / push)
  GITHUB_BRANCH         default "main"
  GITHUB_BLUEPRINT_DIR  default "blueprints"

If GITHUB_REPO is unset, pull_blueprints() is a no-op so local-only runs still work.
"""

import os
import json
import base64
import urllib.request
import urllib.error
import urllib.parse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _cfg():
    return {
        "repo": os.environ.get("GITHUB_REPO"),
        "token": os.environ.get("GITHUB_TOKEN"),
        "branch": os.environ.get("GITHUB_BRANCH", "main"),
        "dir": os.environ.get("GITHUB_BLUEPRINT_DIR", "blueprints"),
    }


def _request(url, token, accept="application/vnd.github+json", method="GET", data=None):
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "artis-pipeline",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    return urllib.request.urlopen(req)


def pull_blueprints(dest_dir):
    """Download all blueprint files from the GitHub folder into dest_dir. Returns count."""
    c = _cfg()
    if not c["repo"]:
        print("  (GITHUB_REPO not set — skipping GitHub pull; using local intake only)")
        return 0

    os.makedirs(dest_dir, exist_ok=True)
    listing = (f'https://api.github.com/repos/{c["repo"]}/contents/'
               f'{c["dir"]}?ref={c["branch"]}')
    try:
        with _request(listing, c["token"]) as resp:
            items = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  GitHub folder '{c['dir']}' not found yet (nothing to pull).")
            return 0
        raise

    n = 0
    for it in items:
        if it.get("type") == "file" and it["name"].lower().endswith((".md", ".markdown", ".txt")):
            with _request(it["url"], c["token"], accept="application/vnd.github.raw") as r:
                content = r.read()
            with open(os.path.join(dest_dir, it["name"]), "wb") as f:
                f.write(content)
            n += 1
            print(f"  pulled {it['name']}")
    print(f"  [ok] pulled {n} blueprint(s) from github:{c['repo']}/{c['dir']}")
    return n


def _put_file(repo_path, data_bytes, message):
    """Create or update a file in the repo via the Contents API. Returns (ok, path_or_error)."""
    c = _cfg()
    if not c["repo"] or not c["token"]:
        return False, "GITHUB_REPO/GITHUB_TOKEN not set"

    enc = "/".join(urllib.parse.quote(p) for p in repo_path.split("/"))
    base = f'https://api.github.com/repos/{c["repo"]}/contents/{enc}'

    sha = None
    try:
        with _request(f'{base}?ref={c["branch"]}', c["token"]) as r:
            sha = json.load(r).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    body = {
        "message": message,
        "content": base64.b64encode(data_bytes).decode("ascii"),
        "branch": c["branch"],
    }
    if sha:
        body["sha"] = sha

    try:
        with _request(base, c["token"], method="PUT", data=json.dumps(body).encode("utf-8")) as r:
            json.load(r)
        return True, repo_path
    except urllib.error.HTTPError as e:
        return False, f"GitHub {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"


def push_blueprint(filename, text):
    """Commit a single blueprint to the GitHub blueprints folder."""
    c = _cfg()
    return _put_file(f'{c["dir"]}/{filename}', text.encode("utf-8"),
                     f"Add client blueprint: {filename}")


def push_data(text, repo_path=None):
    """Commit the rebuilt web app dataset (data.js) so the deployed app redeploys."""
    repo_path = repo_path or os.environ.get("GITHUB_DATA_PATH", "prototype/data.js")
    return _put_file(repo_path, text.encode("utf-8"), "Update ARTIS dataset (automated)")


def get_file_text(repo_path):
    """Fetch the current text of a repo file, or None if it doesn't exist."""
    c = _cfg()
    if not c["repo"]:
        return None
    enc = "/".join(urllib.parse.quote(p) for p in repo_path.split("/"))
    url = f'https://api.github.com/repos/{c["repo"]}/contents/{enc}?ref={c["branch"]}'
    try:
        with _request(url, c["token"], accept="application/vnd.github.raw") as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def push_files(files, message):
    """Commit MANY files in a single atomic commit (Git Data API).

    files: dict of {repo_path: text}. Returns (ok, short_sha_or_error).
    """
    c = _cfg()
    if not c["repo"] or not c["token"]:
        return False, "GITHUB_REPO/GITHUB_TOKEN not set"

    repo = c["repo"]
    git = f"https://api.github.com/repos/{repo}/git"

    def _post(path, payload):
        data = json.dumps(payload).encode("utf-8")
        with _request(f"{git}/{path}", c["token"], method="POST", data=data) as r:
            return json.load(r)

    try:
        # 1. current branch head + its tree
        with _request(f"{git}/ref/heads/{c['branch']}", c["token"]) as r:
            base_sha = json.load(r)["object"]["sha"]
        with _request(f"{git}/commits/{base_sha}", c["token"]) as r:
            base_tree = json.load(r)["tree"]["sha"]

        # 2. blob per file → 3. new tree on top of base
        tree = []
        for path, text in files.items():
            blob = _post("blobs", {
                "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                "encoding": "base64",
            })
            tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        new_tree = _post("trees", {"base_tree": base_tree, "tree": tree})

        # 4. commit → 5. move the branch
        new_commit = _post("commits", {"message": message, "tree": new_tree["sha"], "parents": [base_sha]})
        data = json.dumps({"sha": new_commit["sha"]}).encode("utf-8")
        with _request(f"{git}/refs/heads/{c['branch']}", c["token"], method="PATCH", data=data) as r:
            json.load(r)

        return True, new_commit["sha"][:7]
    except urllib.error.HTTPError as e:
        return False, f"GitHub {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"


if __name__ == "__main__":
    import sys
    dest = sys.argv[1] if len(sys.argv) > 1 else "."
    pull_blueprints(dest)
