#!/usr/bin/env python3
"""Source changes that the Gradle build of Contacts needs. Run in the upstream tree.

1. The three classes of the PhoneCommon and frameworks/ex libraries that Contacts uses are copied into
   libs-src/ (the libraries are whole Android modules; only these few files are needed, and the rest
   would need platform APIs the SDK does not have).
2. The vcard library (frameworks/opt/vcard) imports the platform-internal
   com.android.internal.annotations.VisibleForTesting, which an app cannot compile against. The
   androidx annotation of the same name stands in for it; the annotation has no effect at run time.
   The same goes for android.annotation.NonNull and Nullable, which the platform keeps out of the SDK.
"""
import re
import shutil
import sys
from pathlib import Path

COPIES = [
    "libs/phonecommon/src/com/android/phone/common/PhoneConstants.java",
    "libs/phonecommon/src/com/android/phone/common/animation/AnimUtils.java",
    "libs/phonecommon/src/com/android/phone/common/compat/PathInterpolatorCompat.java",
    "libs/ex/common/java/com/android/common/widget/CompositeCursorAdapter.java",
]
for rel in COPIES:
    src = Path(rel)
    if not src.is_file():
        sys.exit(f"prepare: {rel} missing; was the dependency fetched?")
    # The package directory starts after src/ (PhoneCommon) or java/ (frameworks/ex).
    sub = re.split(r"/(?:src|java)/", rel, maxsplit=1)[1]
    dest = Path("libs-src") / sub
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
print(f"prepare: copied {len(COPIES)} library files into libs-src")

INTERNAL = "com.android.internal.annotations.VisibleForTesting"
HIDDEN_ANNOTATIONS = {
    f"import android.annotation.{name};": f"import androidx.annotation.{name};"
    for name in ("NonNull", "Nullable")
}
changed = 0
for path in sorted(Path("libs/vcard").rglob("*.java")):
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
