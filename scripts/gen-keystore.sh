#!/usr/bin/env bash
# Run once, on your own machine. Creates the signing key for every losforgos app.
#   scripts/gen-keystore.sh [output-dir] [OWNER/REPO]
# With OWNER/REPO and a logged-in gh CLI, it also uploads the secrets for you.
# Never commit the keystore. Keep a backup somewhere safe: if it is lost, every
# installed app has to be uninstalled before an update signed by a new key will install.
set -euo pipefail
dir="${1:-$HOME/losforgos-keystore}"
repo="${2:-}"

ask() { local a; read -r -p "$1 [y/N] " a; [[ "$a" =~ ^[Yy]$ ]]; }

# macOS ships a /usr/bin/keytool stub that fails without a JDK, so test that it really runs.
if ! keytool -help >/dev/null 2>&1; then
  echo "keytool (part of a JDK) is not installed." >&2
  if command -v brew >/dev/null; then
    ask "Install a JDK with 'brew install --cask temurin@17' now?" || { echo "Install a JDK, then rerun." >&2; exit 1; }
    brew install --cask temurin@17
    jh="$(/usr/libexec/java_home -v 17 2>/dev/null || true)"
    [ -n "$jh" ] && export PATH="$jh/bin:$PATH"
    keytool -help >/dev/null 2>&1 || { echo "keytool still not found; open a new terminal and rerun." >&2; exit 1; }
  else
    echo "Install Homebrew (https://brew.sh) or a JDK 17, then rerun." >&2; exit 1
  fi
fi

mkdir -p "$dir"; chmod 700 "$dir"
ks="$dir/losforgos.p12"
[ -e "$ks" ] && { echo "$ks already exists, refusing to overwrite" >&2; exit 1; }

read -r -s -p "Choose a keystore password (min 12 chars): " pw; echo
[ "${#pw}" -ge 12 ] || { echo "too short" >&2; exit 1; }
export KS_PW="$pw"   # passed to keytool via environment, not on the command line

keytool -genkeypair -v -keystore "$ks" -storetype PKCS12 \
  -alias losforgos -keyalg RSA -keysize 4096 -validity 36500 \
  -storepass:env KS_PW -keypass:env KS_PW \
  -dname "CN=losforgos, O=LineageOS apps for GrapheneOS"

sha="$(keytool -list -v -keystore "$ks" -storepass:env KS_PW | awk -F'SHA256: ' '/SHA256:/{print $2; exit}' | tr -d ':')"
echo; echo "Created $ks"
echo "Certificate SHA-256 (public, goes in the repo variable CERT_SHA256):"; echo "  $sha"; echo

upload() {
  gh secret set KEYSTORE_B64 --env release --repo "$repo" < <(base64 < "$ks")
  printf %s "$pw" | gh secret set KEYSTORE_PASSWORD --env release --repo "$repo"
  printf %s losforgos | gh secret set KEY_ALIAS --env release --repo "$repo"
  printf %s "$pw" | gh secret set KEY_PASSWORD --env release --repo "$repo"
  gh variable set CERT_SHA256 --repo "$repo" --body "$sha"
  echo "Secrets and CERT_SHA256 uploaded to $repo."
}

if [ -n "$repo" ] && command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  ask "Upload the secrets to $repo (environment 'release' must already exist)?" && upload
elif [ -n "$repo" ]; then
  echo "gh is missing or not logged in: 'brew install gh && gh auth login', then rerun the commands below."
fi

cat <<MSG
Manual upload (replace OWNER/REPO, use your password):
  gh secret set KEYSTORE_B64 --env release --repo OWNER/REPO < <(base64 < "$ks")
  gh secret set KEYSTORE_PASSWORD --env release --repo OWNER/REPO
  gh secret set KEY_ALIAS --env release --repo OWNER/REPO --body losforgos
  gh secret set KEY_PASSWORD --env release --repo OWNER/REPO
  gh variable set CERT_SHA256 --repo OWNER/REPO --body $sha

Then back up $ks and the password in a password manager or offline.
MSG
