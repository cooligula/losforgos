#!/usr/bin/env bash
# One-time signing setup, for macOS or Linux. No Java needed (uses openssl).
#   scripts/setup-signing.sh [owner/repo]
# 1. creates the signing key once and keeps it in ~/.losforgos-keystore
# 2. installs/logs in the gh CLI if needed
# 3. creates the `release` environment (main branch only), the four secrets and the
#    CERT_SHA256 variable, and lets Actions open pull requests
# Safe to run again: an existing key is reused, never replaced.
set -euo pipefail

repo="${1:-}"
if [ -z "$repo" ]; then
  repo="$(git config --get remote.origin.url | sed -E 's#^.*github\.com[:/]##; s#\.git$##')"
fi
[ -n "$repo" ] || { echo "Pass the repository as owner/name" >&2; exit 1; }
echo "Repository: $repo"

dir="${LOSFORGOS_KEYDIR:-$HOME/.losforgos-keystore}"
ks="$dir/losforgos.p12"
pwfile="$dir/password.txt"
mkdir -p "$dir"; chmod 700 "$dir"

command -v openssl >/dev/null || { echo "openssl is required" >&2; exit 1; }

if [ -e "$ks" ]; then
  echo "Reusing existing key in $dir"
  [ -r "$pwfile" ] || { echo "$pwfile is missing, cannot reuse the key" >&2; exit 1; }
  pw="$(cat "$pwfile")"
  openssl pkcs12 -in "$ks" -passin "pass:$pw" -clcerts -nokeys -out "$dir/cert.pem" 2>/dev/null
else
  pw="$(openssl rand -base64 24 | tr -d '/+=\n')"
  umask 077
  openssl req -x509 -newkey rsa:4096 -sha256 -days 36500 -nodes \
    -keyout "$dir/key.pem" -out "$dir/cert.pem" \
    -subj "/CN=losforgos/O=LineageOS apps for GrapheneOS" 2>/dev/null
  openssl pkcs12 -export -inkey "$dir/key.pem" -in "$dir/cert.pem" \
    -name losforgos -out "$ks" -passout "pass:$pw"
  printf '%s' "$pw" > "$pwfile"
  rm -f "$dir/key.pem"
  echo "Created $ks"
fi
chmod 600 "$ks" "$pwfile"

sha="$(openssl x509 -in "$dir/cert.pem" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d ':')"
echo "Certificate SHA-256: $sha"

if ! command -v gh >/dev/null; then
  if command -v brew >/dev/null; then
    echo "Installing the GitHub CLI with Homebrew..."
    brew install gh
  else
    echo "Install the GitHub CLI (https://cli.github.com), then run this script again." >&2
    exit 1
  fi
fi
gh auth status >/dev/null 2>&1 || gh auth login

echo "Configuring $repo ..."
gh api -X PUT "repos/$repo/environments/release" \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true' >/dev/null
gh api -X POST "repos/$repo/environments/release/deployment-branch-policies" \
  -f name=main -f type=branch >/dev/null 2>&1 || true

base64 < "$ks" | tr -d '\n' | gh secret set KEYSTORE_B64 --env release --repo "$repo"
gh secret set KEYSTORE_PASSWORD --env release --repo "$repo" --body "$pw"
gh secret set KEY_ALIAS --env release --repo "$repo" --body losforgos
gh secret set KEY_PASSWORD --env release --repo "$repo" --body "$pw"
gh variable set CERT_SHA256 --repo "$repo" --body "$sha"

gh api -X PUT "repos/$repo/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true >/dev/null

cat <<MSG

Done. The release environment, secrets and CERT_SHA256 are set on $repo.

BACK THIS UP NOW (password manager or offline). If either is lost, every installed app
must be uninstalled before an update signed by a new key will install:
  $ks
  password: $pw

Publish the first releases with:
  gh workflow run build.yml --repo $repo --ref main -f release=true -f force=true
MSG
