#!/usr/bin/env python3
"""Publish signed APKs as GitHub releases: scripts/release.py <signed-dir> <owner/repo>

<signed-dir>/<app>/meta.json describes the build; the signed APK sits next to it.
One release per app and variant. The release body carries a Build-Input marker
that `losforgos.py plan` uses to skip builds whose inputs did not change.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

signed_dir, repo = Path(sys.argv[1]), sys.argv[2]

for meta_path in sorted(signed_dir.glob("*/meta.json")):
    meta = json.loads(meta_path.read_text())
    apks = sorted(meta_path.parent.glob("*.apk"))
    if len(apks) != 1:
        sys.exit(f"{meta_path.parent}: expected one signed APK, found {len(apks)}")
    apk = apks[0]
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    sums = apk.with_name(apk.name + ".sha256")
    sums.write_text(f"{digest}  {apk.name}\n")

    notes = (
        f"{meta['title']} {meta['version_name']} ({meta['variant']})\n\n"
        f"Application id: `{meta['application_id']}`\n"
        f"Upstream: LineageOS/{meta['upstream_repo']} @ `{meta['upstream_sha']}`\n"
        f"APK SHA-256: `{digest}`\n\n"
        f"{'Native libraries: yes, see the build log for the list.' if meta.get('native') else ''}\n\n"
        f"Build-Input: {meta['input']} variant={meta['variant']}\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as nf:
        nf.write(notes)
    title = f"{meta['title']} {meta['version_name']}"
    if meta.get("multi_variant"):
        title += f" ({meta['variant']})"
    cmd = ["gh", "release", "create", meta["tag"], str(apk), str(sums),
           "--repo", repo, "--title", title, "--notes-file", nf.name]
    if meta.get("prerelease"):
        cmd.append("--prerelease")
    subprocess.run(cmd, check=True)
    print(f"released {meta['tag']}")
