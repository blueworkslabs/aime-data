#!/usr/bin/env bash
# Publish public/ to the orphan branch `pages` (Cloudflare Pages deploys it).
# Keeps the previously published release's cells next to the new one, so a
# module holding the old index keeps working until its cache expires; older
# releases are dropped. History on `pages` is never kept.
#
#   scripts/publish.sh [public] [--dry-run]
set -euo pipefail
public=${1:-public}
dry=${2:-}
python3 -m aime_data.validate "$public"
release=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["release"])' "$public/v1/index.json")

# Distinguish an absent branch from a transport/authentication failure. Never
# discard retained data merely because a fetch failed.
remote=$(git ls-remote --heads origin refs/heads/pages)
expected=${remote%%[[:space:]]*}
if [[ -n "$expected" ]]; then
  git fetch -q --depth=1 origin pages
  expected=$(git rev-parse FETCH_HEAD)
  prev=$(git show "$expected:v1/index.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["release"])')
  if git cat-file -e "$expected:v1/$release" 2>/dev/null; then
    prior=$(mktemp -d)
    trap 'rm -rf "$prior"' EXIT
    git archive "$expected" "v1/$release" | tar -x -C "$prior"
    if ! diff -qr "$prior/v1/$release" "$public/v1/$release"; then
      echo "Refusing to change immutable release $release; use a new data revision." >&2
      exit 1
    fi
    if [[ "$prev" == "$release" ]]; then
      echo "Release $release is unchanged; retaining the existing pages commit."
      exit 0
    fi
    echo "Refusing to roll the current index back to retained release $release." >&2
    exit 1
  fi
  git cat-file -e "$expected:v1/$prev"
  echo "keeping previous release $prev"
  git archive "$expected" "v1/$prev" | tar -x -C "$public"
fi

gitdir=$(git rev-parse --absolute-git-dir)
index_dir=$(mktemp -d)
index="$index_dir/index"
tree=$(cd "$public" && GIT_INDEX_FILE=$index git --git-dir="$gitdir" --work-tree=. add -A . \
  && GIT_INDEX_FILE=$index git --git-dir="$gitdir" write-tree)
rm -f "$index"
rmdir "$index_dir"
commit=$(git -c user.name="aime-data build" -c user.email="actions@users.noreply.github.com" \
  commit-tree "$tree" -m "Landmark cells, Overture release $release")
echo "pages commit $commit (release $release)"
if [[ "$dry" == "--dry-run" ]]; then
  git ls-tree -r --name-only "$commit" | sed -n '1,5p;$p'
  exit 0
fi
git push --force-with-lease="refs/heads/pages:$expected" origin "$commit:refs/heads/pages"
