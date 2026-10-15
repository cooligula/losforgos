#!/usr/bin/env python3
"""Soong generates an R class in every package listed in --extra-packages; Gradle makes one.

Run in the upstream tree. Files outside com.android.dialer that use R without importing one get
`import com.android.dialer.R;`, and qualified references to the per-package classes point at it.
"""
import re
import sys
from pathlib import Path

MAIN_R = "com.android.dialer.R"
own = re.compile(r"\bcom\.android\.(?:dialer|incallui|contacts|voicemail)(?:\.[a-z0-9_]+)*\.R\b")
uses_r = re.compile(r"(?<![\w.])R\.(?:string|id|layout|drawable|color|dimen|style|styleable|attr|"
                    r"integer|bool|array|plurals|menu|xml|raw|anim|animator|mipmap|font|interpolator)\b")
imports_r = re.compile(r"^import\s+[\w.]+\.R;", re.M)
package = re.compile(r"^package\s+([\w.]+);", re.M)

changed = 0
for path in sorted(Path("java").rglob("*.java")):
    text = path.read_text()
    new = own.sub(MAIN_R, text)
    m = package.search(new)
    if m and m.group(1) != "com.android.dialer" and uses_r.search(new) and not imports_r.search(new):
        new = new[:m.end()] + f"\n\nimport {MAIN_R};" + new[m.end():]
    if new != text:
        path.write_text(new)
        changed += 1
print(f"fix_r: updated {changed} files")
sys.exit(0)
