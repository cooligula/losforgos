#!/usr/bin/env python3
"""Build helper for losforgos. Standard library only (Python 3.11+).

Subcommands:
  plan       print the build matrix as JSON (apps whose inputs changed)
  fetch      shallow-clone one app at its pinned upstream commit
  prepare    rename, version and patch a fetched app
  bump       move pinned SHAs to the current upstream branch heads
  obtainium  write obtainium-apps.json for the released apps
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "apps.toml"
WORK = ROOT / "work"
BUILD_MARKER = "Build-Input:"


def load():
    with CONFIG.open("rb") as f:
        data = tomllib.load(f)
    defaults = data.get("defaults", {})
    apps = {}
    for name, app in data.get("apps", {}).items():
        merged = {**defaults, **app}
        merged["name"] = name
        merged.setdefault("build_file", "app/build.gradle.kts")
        merged.setdefault("gradle_task", ":app:assembleRelease")
        merged.setdefault("apk_dir", "app/build/outputs/apk/release")
        merged.setdefault("enabled", False)
        merged.setdefault("replace", [])
        apps[name] = merged
    return defaults, apps


def run(cmd, **kw):
    kw.setdefault("check", True)
    return subprocess.run(cmd, text=True, **kw)


def out(cmd, **kw):
    return run(cmd, stdout=subprocess.PIPE, **kw).stdout.strip()


def patches_for(name, variant):
    """patches/<app>/*.patch apply to every non-unmodified variant,
    patches/<app>/<variant>/*.patch only to that variant (applied after the common ones)."""
    if variant == "unmodified":
        return []
    base = ROOT / "patches" / name
    return sorted(base.glob("*.patch")) + sorted((base / variant).glob("*.patch"))


def input_hash(app, variant):
    """Hash of everything that decides the contents of a build of this app."""
    h = hashlib.sha256()
    h.update((ROOT / "build-rev.txt").read_bytes())
    h.update(json.dumps(app, sort_keys=True).encode())
    h.update(variant.encode())
    for p in patches_for(app["name"], variant):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def release_tags(repo_slug):
    """Existing release tags and bodies, via gh. Empty when gh is unavailable."""
    try:
        raw = out(["gh", "release", "list", "--repo", repo_slug, "--limit", "200",
                   "--json", "tagName"], stderr=subprocess.DEVNULL)
        tags = [r["tagName"] for r in json.loads(raw or "[]")]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    bodies = {}
    for tag in tags:
        try:
            body = out(["gh", "release", "view", tag, "--repo", repo_slug,
                        "--json", "body", "-q", ".body"], stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            body = ""
        bodies[tag] = body
    return bodies


def latest_input(bodies, app_name, variant):
    """Build-Input of the newest release of this app and variant, or None."""
    prefix = f"{app_name}-v"
    for tag in sorted((t for t in bodies if t.startswith(prefix)), reverse=True):
        m = re.search(rf"{BUILD_MARKER}\s*(\w+)\s+variant=(\w+)", bodies[tag])
        if m and m.group(2) == variant:
            return m.group(1)
    return None


def cmd_plan(args):
    _, apps = load()
    bodies = release_tags(args.repo) if args.repo and not args.all else {}
    include = []
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    for name, app in apps.items():
        if not app["enabled"]:
            continue
        if args.only and name not in args.only.split(","):
            continue
        for variant in app["variants"]:
            digest = input_hash(app, variant)
            changed = args.all or latest_input(bodies, name, variant) != digest
            if changed:
                used = sum(1 for t in bodies if t.startswith(f"{name}-v") and f".{today}." in t)
                include.append({"app": name, "variant": variant, "input": digest,
                                "java": app["java"], "title": app["title"],
                                "date": today, "seq": used + 1})
    print(json.dumps({"include": include}))


def cmd_fetch(args):
    _, apps = load()
    app = apps[args.app]
    dest = WORK / args.app
    if dest.exists():
        sys.exit(f"{dest} already exists")
    url = f"{app['upstream']}/{app['repo']}"
    dest.mkdir(parents=True)
    run(["git", "init", "-q"], cwd=dest)
    run(["git", "remote", "add", "origin", url], cwd=dest)
    run(["git", "fetch", "-q", "--depth", "1", "origin", app["sha"]], cwd=dest)
    run(["git", "checkout", "-q", "FETCH_HEAD"], cwd=dest)
    print(f"fetched {url} at {app['sha']}")


def sub_once(text, pattern, repl, what):
    new, n = re.subn(pattern, repl, text, count=1)
    if n != 1:
        sys.exit(f"prepare: could not find {what}; upstream build file changed?")
    return new


def cmd_prepare(args):
    _, apps = load()
    app = apps[args.app]
    src = WORK / args.app
    build_file = src / app["build_file"]
    text = build_file.read_text()

    # Upstream version name is kept as the prefix of ours.
    m = re.search(r'versionName\s*=?\s*"([^"]*)"', text)
    if not m:
        sys.exit("prepare: no versionName found")
    upstream_name = m.group(1)

    date = args.date or datetime.date.today().strftime("%Y%m%d")
    seq = int(args.seq)
    version_code = int(f"{date}{seq:02d}")
    version_name = f"{upstream_name}.{date}.{seq:02d}"

    # Apps that must keep their upstream id (the Gcam bridge impersonates Google Photos on purpose).
    if app.get("rename_application_id", True):
        text = sub_once(text, r'(applicationId\s*=?\s*)"[^"]+"',
                        lambda mm: f'{mm.group(1)}"{app["application_id"]}"', "applicationId")
    text = sub_once(text, r'(versionCode\s*=?\s*)\d+',
                    lambda mm: f"{mm.group(1)}{version_code}", "versionCode")
    text = sub_once(text, r'(versionName\s*=?\s*)"[^"]*"',
                    lambda mm: f'{mm.group(1)}"{version_name}"', "versionName")
    build_file.write_text(text)

    for rep in app["replace"]:
        path = src / rep["file"]
        body = path.read_text()
        if rep["from"] not in body:
            sys.exit(f"prepare: '{rep['from']}' not found in {rep['file']}")
        path.write_text(body.replace(rep["from"], rep["to"]))

    for patch in patches_for(args.app, args.variant):
        run(["git", "apply", "--unidiff-zero", "--check", str(patch)], cwd=src)
        run(["git", "apply", "--unidiff-zero", str(patch)], cwd=src)
        print(f"applied {patch.name}")

    # Several variants of one app need distinct tags; single-variant apps keep the short form.
    multi = len(app["variants"]) > 1
    tag = f"{args.app}-v{version_name}" + (f"-{args.variant}" if multi else "")
    prerelease = args.variant in app.get("prerelease_variants", ["probe"])

    meta = {
        "app": args.app, "variant": args.variant, "title": app["title"],
        "application_id": app["application_id"], "upstream_sha": app["sha"],
        "upstream_repo": app["repo"], "upstream_version_name": upstream_name,
        "version_code": version_code, "version_name": version_name,
        "tag": tag,
        "multi_variant": multi,
        "prerelease": prerelease,
        "input": input_hash(app, args.variant),
        "native": bool(app.get("native", False)),
    }
    (src / "losforgos-meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


def cmd_bump(args):
    _, apps = load()
    text = CONFIG.read_text()
    changed = []
    for name, app in apps.items():
        if not app["enabled"]:
            continue
        url = f"{app['upstream']}/{app['repo']}"
        head = out(["git", "ls-remote", url, f"refs/heads/{app['branch']}"]).split()[0]
        if head != app["sha"]:
            text = text.replace(f'sha = "{app["sha"]}"', f'sha = "{head}"', 1)
            changed.append(f"{name}: {app['sha'][:8]} -> {head[:8]}")
    if changed:
        CONFIG.write_text(text)
    print("\n".join(changed) if changed else "no changes")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


def cmd_obtainium(args):
    """Best-effort Obtainium import file. Verify the import on a device before relying on it."""
    _, apps = load()
    entries = []
    for name, app in apps.items():
        if not app["enabled"]:
            continue
        for variant in app["variants"]:
            if variant in app.get("prerelease_variants", ["probe"]):
                continue  # test builds are published as pre-releases, not for tracking
            settings = {
                "includePrereleases": False,
                "fallbackToOlderReleases": True,
                "filterReleaseTitlesByRegEx": "^" + re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\1", app["title"]) + " ",
                "apkFilterRegEx": f"-{variant}\\.apk$",
                "autoApkFilterByArch": False,
            }
            entries.append({
                "id": app["application_id"],
                "url": f"https://github.com/{args.repo}",
                "author": args.repo.split("/")[0],
                "name": f"{app['title']} ({variant})" if len(app["variants"]) > 1 else app["title"],
                "preferredApkIndex": 0,
                "additionalSettings": json.dumps(settings),
            })
    Path(args.output).write_text(json.dumps({"apps": entries}, indent=2) + "\n")
    print(f"wrote {args.output} with {len(entries)} apps")


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("plan")
    s.add_argument("--repo", help="owner/name, to compare with existing releases")
    s.add_argument("--all", action="store_true", help="ignore existing releases")
    s.add_argument("--only", help="comma separated app names")
    s.set_defaults(fn=cmd_plan)

    s = sp.add_parser("fetch")
    s.add_argument("app")
    s.set_defaults(fn=cmd_fetch)

    s = sp.add_parser("prepare")
    s.add_argument("app")
    s.add_argument("--variant", default="unmodified")
    s.add_argument("--date")
    s.add_argument("--seq", default="1")
    s.set_defaults(fn=cmd_prepare)

    s = sp.add_parser("bump")
    s.set_defaults(fn=cmd_bump)

    s = sp.add_parser("obtainium")
    s.add_argument("--repo", required=True)
    s.add_argument("--output", default=str(ROOT / "obtainium-apps.json"))
    s.set_defaults(fn=cmd_obtainium)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
