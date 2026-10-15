#!/usr/bin/env bash
# Report native libraries and check 16 KB alignment: scripts/check-apk.sh <apk>
# Memory tagging (MTE) only matters for the native libraries listed here.
set -euo pipefail
apk="$1"
echo "== $apk"
libs="$(unzip -Z1 "$apk" | grep -E '^lib/.*\.so$' || true)"
if [ -z "$libs" ]; then
  echo "native libraries: none"
else
  echo "native libraries:"; echo "$libs" | sed 's/^/  /'
  zipalign="$(ls -d "${ANDROID_HOME:-/usr/local/lib/android/sdk}"/build-tools/*/zipalign 2>/dev/null | sort -V | tail -n1)"
  if [ -n "$zipalign" ]; then
    "$zipalign" -c -P 16 4 "$apk" && echo "16 KB alignment: ok"
  fi
fi
