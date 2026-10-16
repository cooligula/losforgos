#!/usr/bin/env python3
"""Build helper for losforgos. Standard library only (Python 3.11+).

Subcommands:
  plan       print the build matrix as JSON (apps whose inputs changed)
  fetch      shallow-clone one app at its pinned upstream commit
  prepare    rename, version and patch a fetched app
  bump       move pinned SHAs to the current upstream branch heads
  obtainium  write obtainium-apps.json for the released apps
  deeplink   build the Obtainium one-tap links; --write refreshes README, docs page and json
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.parse
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


def port_files(app):
    """Files that are part of the build: the overlay directory and the post scripts."""
    files = []
    if app.get("overlay"):
        files += sorted(p for p in (ROOT / "ports" / app["overlay"]).rglob("*") if p.is_file())
    files += [ROOT / s for s in app.get("post_scripts", [])]
    return files


def input_hash(app, variant):
    """Hash of everything that decides the contents of a build of this app."""
    h = hashlib.sha256()
    h.update((ROOT / "build-rev.txt").read_bytes())
    h.update(json.dumps(app, sort_keys=True).encode())
    h.update(variant.encode())
    for p in patches_for(app["name"], variant):
        h.update(p.read_bytes())
    for p in port_files(app):
        h.update(str(p.relative_to(ROOT)).encode())
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
    # Always read the releases: even a forced rebuild needs them to pick a free sequence number.
    bodies = release_tags(args.repo) if args.repo else {}
    include = []
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    for name, app in apps.items():
        if not app["enabled"]:
            continue
        if args.only and name not in args.only.split(","):
            continue
        if app.get("experimental") and not args.only:
            continue  # only built when asked for by name, so that it cannot block releases
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
    # Extra repositories the app needs next to its own tree (libraries that upstream builds from
    # other projects of the Android source tree). Each has a name, url, sha and a directory
    # relative to the app, and is pinned like the app itself.
    for dep in app.get("deps", []):
        ddest = dest / dep["dest"]
        if ddest.exists():
            sys.exit(f"{ddest} already exists")
        ddest.mkdir(parents=True)
        run(["git", "init", "-q"], cwd=ddest)
        run(["git", "remote", "add", "origin", dep["url"]], cwd=ddest)
        run(["git", "fetch", "-q", "--depth", "1", "origin", dep["sha"]], cwd=ddest)
        run(["git", "checkout", "-q", "FETCH_HEAD"], cwd=ddest)
        print(f"fetched {dep['name']}: {dep['url']} at {dep['sha']}")


def sub_once(text, pattern, repl, what):
    new, n = re.subn(pattern, repl, text, count=1)
    if n != 1:
        sys.exit(f"prepare: could not find {what}; upstream build file changed?")
    return new


def set_field(text, name, value, value_re, after):
    """Set a defaultConfig field; when upstream does not declare it, add it after the `after` line."""
    pat = rf'({name}\s*=?\s*){value_re}'
    if re.search(pat, text):
        return sub_once(text, pat, lambda mm: f"{mm.group(1)}{value}", name)
    m = re.search(rf'^([ \t]*){after}[^\n]*$', text, re.M)
    if not m:
        sys.exit(f"prepare: could not find {name} or a place to add it")
    return text[:m.end()] + f"\n{m.group(1)}{name} = {value}" + text[m.end():]


def cmd_prepare(args):
    _, apps = load()
    app = apps[args.app]
    src = WORK / args.app
    if app.get("overlay"):
        # Files for apps whose upstream has no Gradle build (or a different one).
        shutil.copytree(ROOT / "ports" / app["overlay"], src, dirs_exist_ok=True)
    build_file = src / app["build_file"]
    text = build_file.read_text()

    # Upstream version name is kept as the prefix of ours (apps without one use base_version).
    m = re.search(r'versionName\s*=?\s*["\']([^"\']*)["\']', text)
    upstream_name = m.group(1) if m else app.get("base_version", "1.0")

    date = args.date or datetime.date.today().strftime("%Y%m%d")
    seq = int(args.seq)
    version_code = int(f"{date}{seq:02d}")
    version_name = f"{upstream_name}.{date}.{seq:02d}"

    # Apps that must keep their upstream id (the Gcam bridge impersonates Google Photos on purpose).
    if app.get("rename_application_id", True):
        text = sub_once(text, r'(?m)^([ \t]*applicationId\s*=?\s*)(["\'])[^"\']+\2',
                        lambda mm: f'{mm.group(1)}"{app["application_id"]}"', "applicationId")
    text = set_field(text, "versionCode", str(version_code), r"\d+", "applicationId")
    text = set_field(text, "versionName", f'"{version_name}"', r'["\'][^"\']*["\']', "applicationId")
    build_file.write_text(text)

    for rep in app["replace"]:
        # `file` may be a glob (for example res/**/*.xml); then every match containing `from` changes.
        if any(c in rep["file"] for c in "*?["):
            paths = [p for p in sorted(src.glob(rep["file"])) if p.is_file()]
            paths = [p for p in paths if rep["from"] in p.read_text()]
        else:
            paths = [src / rep["file"]]
            if rep["from"] not in paths[0].read_text():
                paths = []
        if not paths:
            sys.exit(f"prepare: '{rep['from']}' not found in {rep['file']}")
        for path in paths:
            path.write_text(path.read_text().replace(rep["from"], rep["to"]))

    for script in app.get("post_scripts", []):
        run([sys.executable, str(ROOT / script)], cwd=src)

    for patch in patches_for(args.app, args.variant):
        run(["git", "apply", "--unidiff-zero", "--check", str(patch)], cwd=src)
        run(["git", "apply", "--unidiff-zero", str(patch)], cwd=src)
        print(f"applied {patch.name}")

    # Several variants of one app need distinct tags; single-variant apps keep the short form.
    multi = len(app["variants"]) > 1
    tag = f"{args.app}-v{version_name}" + (f"-{args.variant}" if multi else "")
    # Experimental ports are published as pre-releases, which Obtainium skips by default.
    prerelease = args.variant in app.get("prerelease_variants", ["probe"]) or app.get("experimental", False)

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
        # What a non-unmodified variant does differently; release.py puts it in the release notes.
        "modified_summary": app.get("modified_summary", "") if args.variant != "unmodified" else "",
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


def obtainium_entries(repo):
    """One Obtainium app config per released app. additionalSettings is a JSON string, as Obtainium stores it."""
    _, apps = load()
    entries = []
    for name, app in apps.items():
        if not app["enabled"] or app.get("experimental"):
            continue
        for variant in app["variants"]:
            if variant in app.get("prerelease_variants", ["probe"]):
                continue  # test builds are published as pre-releases, not for tracking
            if app.get("obtainium_variant", variant) != variant:
                continue  # variants that share one application id: track only this one
            settings = {
                "includePrereleases": False,
                "fallbackToOlderReleases": True,
                "filterReleaseTitlesByRegEx": "^" + re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\1", app["title"]) + " ",
                "apkFilterRegEx": f"-{variant}\\.apk$",
                "autoApkFilterByArch": False,
            }
            entries.append({
                "id": app["application_id"],
                "url": f"https://github.com/{repo}",
                "author": repo.split("/")[0],
                "name": f"{app['title']} ({variant})" if len(app["variants"]) > 1 else app["title"],
                "preferredApkIndex": 0,
                "additionalSettings": json.dumps(settings),
            })
    return entries


def cmd_obtainium(args):
    """Best-effort Obtainium import file. Verify the import on a device before relying on it."""
    entries = obtainium_entries(args.repo)
    Path(args.output).write_text(json.dumps({"apps": entries}, indent=2) + "\n")
    print(f"wrote {args.output} with {len(entries)} apps")


REDIRECT = "https://apps.obtainium.imranr.dev/redirect?r="
README = ROOT / "README.md"
PAGE = ROOT / "docs" / "obtainium.html"
BADGE_START, BADGE_END = "<!-- obtainium-badge:start -->", "<!-- obtainium-badge:end -->"


def compact_json(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def app_link(entry):
    """Per-app link through Obtainium's own redirect page. That page reads `r` with
    searchParams (one decode) and then decodeURIComponent on the JSON (a second one),
    so the JSON is encoded twice. It only accepts obtainium://app/ and obtainium://add/."""
    inner = "obtainium://app/" + urllib.parse.quote(compact_json(entry), safe=":,/")
    return REDIRECT + urllib.parse.quote(inner, safe=":,/")


def bulk_link(entries):
    """obtainium://apps/<url-encoded JSON array>; the deep link handler decodes the path once.
    It is not an https link, so GitHub's markdown would drop it: it lives in docs/obtainium.html."""
    return "obtainium://apps/" + urllib.parse.quote(compact_json(entries), safe=":,/")


def default_repo():
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    url = out(["git", "remote", "get-url", "origin"], cwd=ROOT)
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    if not m:
        sys.exit("deeplink: cannot work out OWNER/REPO, pass --repo")
    return m.group(1)


def badge_block(repo, entries, page_url):
    owner, name = repo.split("/")
    lines = [
        BADGE_START,
        "<!-- generated by `python3 scripts/losforgos.py deeplink --write`; do not edit by hand -->",
        f'<a href="{page_url}"><img src="docs/assets/badge_obtainium.png" height="48" alt="Get on Obtainium"></a>',
        "",
        "Adds every app here to Obtainium's list; nothing is installed. Then open the app you want in Obtainium and tap Install.",
        "Badge from the [Obtainium](https://github.com/ImranR98/Obtainium) repository.",
        "",
        "<details><summary>One link per app, or add them by hand</summary>",
        "",
    ]
    lines += [f"- [{e['name']}]({app_link(e)})" for e in entries]
    lines += [
        "",
        f"By hand: in Obtainium tap Add app, enter `https://github.com/{repo}`, and set the release title",
        "and APK filters shown under [Install and update](#install-and-update-with-obtainium); or import",
        "[obtainium-apps.json](obtainium-apps.json) (Obtainium, Import/Export, Import from file).",
        "",
        "</details>",
        BADGE_END,
    ]
    return "\n".join(lines)


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Add the losforgos apps to Obtainium</title>
<!-- generated by `python3 scripts/losforgos.py deeplink --write`; do not edit by hand -->
<style>
  body{{font:16px/1.5 system-ui,sans-serif;max-width:32rem;margin:3rem auto;padding:0 1rem}}
  a.button{{display:inline-block;margin:.5rem 0;padding:.6rem 1.2rem;border-radius:2rem;background:#6438b5;color:#fff;text-decoration:none}}
</style>
</head>
<body>
<h1>Add the losforgos apps to Obtainium</h1>
<p>Opening Obtainium to add {count} apps to its list. Nothing is installed: afterwards open the app you want and tap Install.</p>
<p><a class="button" id="go" href="{link}">Open Obtainium</a></p>
<p>Nothing happened? <a href="https://obtainium.imranr.dev/">Get Obtainium</a> first, or use the
<a href="https://github.com/{repo}#readme">per-app links on the repository page</a>.</p>
<script>
  // Android browsers need the redirect to follow the page load; the button is the fallback.
  window.location.href = document.getElementById("go").href;
</script>
</body>
</html>
"""


def cmd_deeplink(args):
    repo = args.repo or default_repo()
    owner, name = repo.split("/")
    page_url = args.page_url or f"https://{owner.lower()}.github.io/{name}/obtainium.html"
    entries = obtainium_entries(repo)
    bulk = bulk_link(entries)
    singles = [app_link(e) for e in entries]
    block = badge_block(repo, entries, page_url)
    page = PAGE_TEMPLATE.format(count=len(entries), link=bulk, repo=repo)
    export = json.dumps({"apps": entries}, indent=2) + "\n"
    targets = {}
    text = README.read_text()
    if BADGE_START in text and BADGE_END in text:
        head, rest = text.split(BADGE_START, 1)
        targets[README] = head + block + rest.split(BADGE_END, 1)[1]
    else:
        targets[README] = text  # first run: the block is placed by hand, see README
        if args.write or args.check:
            sys.exit("deeplink: README.md has no obtainium-badge markers")
    targets[PAGE] = page
    targets[ROOT / "obtainium-apps.json"] = export
    print(f"{len(entries)} apps; bulk link {len(bulk)} chars (page {page_url}); "
          f"per-app redirect links {min(map(len, singles))}-{max(map(len, singles))} chars")
    if args.check:
        stale = [str(p.relative_to(ROOT)) for p, t in targets.items() if not p.exists() or p.read_text() != t]
        if stale:
            sys.exit("out of date, run `python3 scripts/losforgos.py deeplink --write`: " + ", ".join(stale))
        print("up to date")
    elif args.write:
        for p, t in targets.items():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(t)
        print("wrote " + ", ".join(str(p.relative_to(ROOT)) for p in targets))
    else:
        print(bulk)
        print("\n".join(singles))


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

    s = sp.add_parser("deeplink")
    s.add_argument("--repo", help="owner/name; default: GITHUB_REPOSITORY or the origin remote")
    s.add_argument("--page-url", help="public URL of docs/obtainium.html (default: GitHub Pages of the repo)")
    s.add_argument("--write", action="store_true", help="refresh the README block, docs/obtainium.html and obtainium-apps.json")
    s.add_argument("--check", action="store_true", help="fail when those files are out of date")
    s.set_defaults(fn=cmd_deeplink)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
