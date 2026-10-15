#!/usr/bin/env python3
"""Source changes that the Gradle build of Messaging needs. Run in the upstream tree.

The vcard library (frameworks/opt/vcard) imports the platform-internal
com.android.internal.annotations.VisibleForTesting, which an app cannot compile against. The
androidx annotation of the same name stands in for it; the annotation has no effect at run time.
"""
import re
import sys
from pathlib import Path

INTERNAL = "com.android.internal.annotations.VisibleForTesting"
changed = 0
for path in sorted(Path("libs/vcard/java").rglob("*.java")):
    text = path.read_text()
    if INTERNAL not in text:
        continue
    new = text.replace(f"import {INTERNAL};", "import androidx.annotation.VisibleForTesting;")
    # androidx spells the visibility "otherwise = VisibleForTesting.PACKAGE_PRIVATE".
    new = re.sub(r"@VisibleForTesting\(\s*visibility\s*=\s*VisibleForTesting\.Visibility\.PACKAGE\s*\)",
                 "@VisibleForTesting(otherwise = VisibleForTesting.PACKAGE_PRIVATE)", new)
    new = re.sub(r"@VisibleForTesting\(\s*visibility\s*=\s*VisibleForTesting\.Visibility\.PRIVATE\s*\)",
                 "@VisibleForTesting(otherwise = VisibleForTesting.PRIVATE)", new)
    path.write_text(new)
    changed += 1
print(f"prepare: updated {changed} vcard files")

left = [p for p in Path("libs/vcard/java").rglob("*.java") if "VisibleForTesting.Visibility" in p.read_text()]
if left:
    sys.exit(f"prepare: unhandled VisibleForTesting visibility in {left}")
