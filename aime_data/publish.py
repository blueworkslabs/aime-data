"""Plan a publication of public/ against what `pages` currently serves.

    python -m aime_data.publish public published

`published` is an extract of the current `pages` tree (empty when the branch
does not exist yet). Prints `noop` or `publish <dataset>` and prepares public/:

- Same Overture release, same bytes (ignoring `built` and the revision labels):
  nothing to publish.
- Same release, changed bytes: the build becomes revision N+1 of that release.
  A published dataset path is never rewritten.
- Newer release: published as built (revision 1).
- Older release than the one published: refused (no rollback by rebuild).

The published dataset is copied next to the new one, so exactly the current
and the previous dataset are served; older ones drop out.
"""
import json
import os
import shutil
import sys

from . import contract as C
from .cells import dumps
from .validate import read, validate


class Refused(Exception):
    pass


def load_index(root):
    path = os.path.join(root, "v1", "index.json")
    return json.loads(read(path)) if os.path.exists(path) else None


def cells_of(root, index):
    """{cell name: cell document without its revision label}."""
    out = {}
    for name in index["cells"]:
        doc = json.loads(read(os.path.join(root, "v1", index["path"], name + ".json")))
        doc.pop("revision", None)
        out[name] = doc
    return out


def same_content(public, new, published, old):
    skip = {"built", "revision", "dataset", "path"}
    if {k: v for k, v in new.items() if k not in skip} != {k: v for k, v in old.items() if k not in skip}:
        return False
    return cells_of(public, new) == cells_of(published, old)


def relabel(public, index, revision):
    """Move the built dataset to `revision`, rewriting its labels."""
    old_ds, new_ds = index["dataset"], C.dataset_name(index["release"], revision)
    src, dst = os.path.join(public, "v1", old_ds), os.path.join(public, "v1", new_ds)
    os.rename(src, dst)
    for name in index["cells"]:
        path = os.path.join(dst, "cells", name + ".json")
        doc = json.loads(read(path))
        doc["revision"] = revision
        with open(path, "wb") as fh:
            fh.write(dumps(doc).encode())
    index = dict(index, revision=revision, dataset=new_ds, path=f"{new_ds}/cells/")
    with open(os.path.join(public, "v1", "index.json"), "w", encoding="utf-8") as fh:
        fh.write(dumps(index))
    html = os.path.join(public, "index.html")
    if os.path.exists(html):
        text = read(html).replace(f"Dataset {old_ds} ", f"Dataset {new_ds} ")
        with open(html, "w", encoding="utf-8") as fh:
            fh.write(text)
    return index


def plan(public, published):
    new, old = load_index(public), load_index(published)
    if old:
        if new["release"] < old["release"]:
            raise Refused(f"release {new['release']} is older than the published {old['release']}; no rollback")
        if new["release"] == old["release"]:
            if same_content(public, new, published, old):
                return "noop", old["dataset"]
            new = relabel(public, new, old["revision"] + 1)
        if os.path.exists(os.path.join(published, "v1", new["dataset"])):
            raise Refused(f"dataset {new['dataset']} is already published; paths are never rewritten")
        prev = os.path.join(published, "v1", old["dataset"])
        if not os.path.isdir(prev):
            raise Refused(f"published dataset {old['dataset']} is missing from pages")
        shutil.copytree(prev, os.path.join(public, "v1", old["dataset"]))
    errs, _ = validate(public)
    if errs:
        raise Refused("; ".join(errs[:5]))
    return "publish", new["dataset"]


def main(argv):
    try:
        action, dataset = plan(argv[1], argv[2])
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    print(action if action == "noop" else f"{action} {dataset}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
