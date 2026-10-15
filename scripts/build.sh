#!/usr/bin/env bash
# Build the unsigned release APK of a prepared app: scripts/build.sh <app>
# Produces dist/<app>/<app>-<version>-<variant>-unsigned.apk and the metadata file next to it.
set -euo pipefail
app="$1"
root="$(cd "$(dirname "$0")/.." && pwd)"
src="$root/work/$app"
meta="$src/losforgos-meta.json"
task="$(python3 -c "import sys,tomllib;d=tomllib.load(open('$root/apps.toml','rb'));print(d['apps']['$app'].get('gradle_task',':app:assembleRelease'))")"
apkdir="$(python3 -c "import sys,tomllib;d=tomllib.load(open('$root/apps.toml','rb'));print(d['apps']['$app'].get('apk_dir','app/build/outputs/apk/release'))")"

( cd "$src" && chmod +x gradlew && ./gradlew --no-daemon --stacktrace "$task" )

apk="$(ls "$src/$apkdir"/*.apk | head -n1)"
version="$(python3 -c "import json;print(json.load(open('$meta'))['version_name'])")"
variant="$(python3 -c "import json;print(json.load(open('$meta'))['variant'])")"
mkdir -p "$root/dist/$app"
cp "$apk" "$root/dist/$app/$app-$version-$variant-unsigned.apk"
cp "$meta" "$root/dist/$app/meta.json"
echo "built $root/dist/$app/$app-$version-$variant-unsigned.apk"
