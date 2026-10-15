#!/usr/bin/env python3
"""Source changes that the Gradle build of the Dialer needs. Run in the upstream tree.

1. Soong generates an R class in every package listed in --extra-packages; Gradle makes one.
   Files outside com.android.dialer that use R without importing one get
   `import com.android.dialer.R;`, and qualified references to the per-package classes point at it.
2. The .proto files import each other by their path from the repository root
   (java/com/android/...), so they are copied to src/main/proto/ with that path kept, which is
   where the protobuf plugin looks.
3. Soong treats resource_dirs as ordered overlays, where a later definition replaces an earlier one;
   Gradle fails on duplicates. The earlier definitions (values entries, and files of the same name
   in the same qualifier directory) are removed.
"""
import re
import shutil
import sys
from pathlib import Path
from xml.parsers import expat

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
print(f"prepare: updated {changed} files")

protos = sorted(Path("java").rglob("*.proto"))
for proto in protos:
    dest = Path("src/main/proto") / proto
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(proto, dest)
print(f"prepare: staged {len(protos)} proto files")


def resource_dirs():
    bp = Path("Android.bp").read_text()
    block = re.search(r"resource_dirs:\s*\[(.*?)]", bp, re.S).group(1)
    return re.findall(r'"([^"]+)"', block)

def top_level_elements(path):
    """(identity, start, end) of every resource a values file defines, as byte offsets.

    These are the direct children of <resources> that have a name, and the <attr> definitions
    (with a format or children) inside a <declare-styleable>, which are global attrs as well.
    """
    data = path.read_bytes()
    found = []
    stack = []
    state = {"ident": None, "start": 0, "attr_name": None, "attr_start": 0, "attr_defined": False,
             "attr_empty_end": None, "empty_end": None}
    parser = expat.ParserCreate()

    def tag_end(begin):
        """End offset of an empty element such as <attr name="x"/>, else None."""
        j = data.find(b">", begin)
        return j + 1 if data[j - 1:j] == b"/" else None

    def start(tag, attrs):
        stack.append(tag)
        empty_end = tag_end(parser.CurrentByteIndex)
        depth = len(stack)
        name = attrs.get("name")
        if depth == 2:
            state["start"] = parser.CurrentByteIndex
            state["empty_end"] = empty_end
            state["ident"] = None
            if name and tag != "declare-styleable":
                kind = attrs.get("type", "") if tag == "item" else ""
                state["ident"] = (tag, kind, name)
        elif depth == 3 and stack[1] == "declare-styleable" and tag == "attr" and name \
                and ":" not in name:
            state["attr_start"] = parser.CurrentByteIndex
            state["attr_name"] = name
            state["attr_defined"] = "format" in attrs
            state["attr_empty_end"] = empty_end
        elif depth == 4 and stack[1] == "declare-styleable":
            state["attr_defined"] = True  # <enum> or <flag> children

    def end(tag):
        depth = len(stack)
        if depth == 2 and state["ident"]:
            stop = state["empty_end"] or data.find(b">", parser.CurrentByteIndex) + 1
            found.append((state["ident"], state["start"], stop))
        elif depth == 3 and stack[1] == "declare-styleable" and tag == "attr" \
                and state["attr_name"] and state["attr_defined"]:
            stop = state["attr_empty_end"] or data.find(b">", parser.CurrentByteIndex) + 1
            found.append((("attr", "", state["attr_name"]), state["attr_start"], stop))
        if depth == 3:
            state["attr_name"] = None
            state["attr_defined"] = False
        stack.pop()

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(data, True)
    return data, found

def main():
    dirs = [Path(d) for d in resource_dirs()]
    # Later directories win, like the overlays Soong builds.
    owner = {}          # (qualifier dir, identity) -> (file, start, end)
    files_seen = {}     # (qualifier dir, file name) for non-values resources
    removals = {}       # file -> list of (start, end)
    deleted_files = []
    for d in dirs:
        if not d.is_dir():
            continue
        for qdir in sorted(p for p in d.iterdir() if p.is_dir()):
            for f in sorted(p for p in qdir.iterdir() if p.is_file()):
                if qdir.name.startswith("values") and f.suffix == ".xml":
                    _, elems = top_level_elements(f)
                    for ident, s, e in elems:
                        key = (qdir.name, ident)
                        if key in owner:
                            pf, ps, pe = owner[key]
                            removals.setdefault(pf, []).append((ps, pe))
                        owner[key] = (f, s, e)
                else:
                    key = (qdir.name, f.name)
                    if key in files_seen:
                        deleted_files.append(files_seen[key])
                    files_seen[key] = f
    for f, spans in removals.items():
        data = f.read_bytes()
        for s, e in sorted(set(spans), reverse=True):
            # Also drop the whitespace that followed the element.
            while e < len(data) and data[e:e + 1] in (b" ", b"\t"):
                e += 1
            if data[e:e + 1] == b"\n":
                e += 1
            data = data[:s] + data[e:]
        f.write_bytes(data)
    for f in deleted_files:
        f.unlink()
    print(f"prepare: removed {sum(len(set(v)) for v in removals.values())} duplicate values, "
          f"{len(deleted_files)} duplicate files")


main()
sys.exit(0)
