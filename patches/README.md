# Patches

Patches for the *modified* variant of an app go in `patches/<app>/NN-description.patch`
(plain `git diff` output, applied with `git apply` from the app's root). An app only
builds a modified variant when its `variants` list in `apps.toml` includes `"modified"`.

A patch that stops applying fails the build, which is the signal to rebase it.
Renaming the application id and setting the version are not patches: they are done by
`scripts/losforgos.py prepare` for every variant.
