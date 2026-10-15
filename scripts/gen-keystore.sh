#!/usr/bin/env bash
# Run once, on your own machine. Creates the signing key for every losforgos app.
#   scripts/gen-keystore.sh [output-dir]
# Never commit the keystore. Keep a backup somewhere safe: if it is lost, every
# installed app has to be uninstalled before an update signed by a new key will install.
set -euo pipefail
dir="${1:-$HOME/losforgos-keystore}"
mkdir -p "$dir"; chmod 700 "$dir"
ks="$dir/losforgos.p12"
[ -e "$ks" ] && { echo "$ks already exists, refusing to overwrite" >&2; exit 1; }

read -r -s -p "Choose a keystore password (min 12 chars): " pw; echo
[ "${#pw}" -ge 12 ] || { echo "too short" >&2; exit 1; }

keytool -genkeypair -v -keystore "$ks" -storetype PKCS12 \
  -alias losforgos -keyalg RSA -keysize 4096 -validity 36500 \
  -storepass "$pw" -keypass "$pw" \
  -dname "CN=losforgos, O=LineageOS apps for GrapheneOS"

sha="$(keytool -list -v -keystore "$ks" -storepass "$pw" | awk -F'SHA256: ' '/SHA256:/{print $2; exit}' | tr -d ':')"
cat <<MSG

Created $ks
Certificate SHA-256 (put this in the repo variable CERT_SHA256, it is public):
  $sha

Next, from a machine with the gh CLI logged in (replace OWNER/REPO):
  gh secret set KEYSTORE_B64 --env release --repo OWNER/REPO < <(base64 < "$ks")
  gh secret set KEYSTORE_PASSWORD --env release --repo OWNER/REPO --body '<the password>'
  gh secret set KEY_ALIAS --env release --repo OWNER/REPO --body losforgos
  gh secret set KEY_PASSWORD --env release --repo OWNER/REPO --body '<the password>'
  gh variable set CERT_SHA256 --repo OWNER/REPO --body $sha

Then back up $ks and the password in a password manager or offline.
MSG
