#!/usr/bin/env python3
"""Source changes that the Gradle build of Messaging needs. Run in the upstream tree.

The vcard library (frameworks/opt/vcard) imports the platform-internal
com.android.internal.annotations.VisibleForTesting, which an app cannot compile against. The
androidx annotation of the same name stands in for it; the annotation has no effect at run time.
The same goes for android.annotation.NonNull and Nullable, which the platform keeps out of the SDK.
"""
import re
import sys
from pathlib import Path

INTERNAL = "com.android.internal.annotations.VisibleForTesting"
HIDDEN_ANNOTATIONS = {
    f"import android.annotation.{name};": f"import androidx.annotation.{name};"
    for name in ("NonNull", "Nullable")
}
changed = 0
for path in sorted(Path("libs").rglob("*.java")):
    text = path.read_text()
    new = text
    for old, repl in HIDDEN_ANNOTATIONS.items():
        new = new.replace(old, repl)
    if INTERNAL not in new:
        if new != text:
            path.write_text(new)
            changed += 1
        continue
    new = new.replace(f"import {INTERNAL};", "import androidx.annotation.VisibleForTesting;")
    # androidx spells the visibility "otherwise = VisibleForTesting.PACKAGE_PRIVATE".
    new = re.sub(r"@VisibleForTesting\(\s*visibility\s*=\s*VisibleForTesting\.Visibility\.PACKAGE\s*\)",
                 "@VisibleForTesting(otherwise = VisibleForTesting.PACKAGE_PRIVATE)", new)
    new = re.sub(r"@VisibleForTesting\(\s*visibility\s*=\s*VisibleForTesting\.Visibility\.PRIVATE\s*\)",
                 "@VisibleForTesting(otherwise = VisibleForTesting.PRIVATE)", new)
    path.write_text(new)
    changed += 1
print(f"prepare: updated {changed} library files")

left = [p for p in Path("libs/vcard/java").rglob("*.java") if "VisibleForTesting.Visibility" in p.read_text()]
if left:
    sys.exit(f"prepare: unhandled VisibleForTesting visibility in {left}")
