#!/usr/bin/env bash
# Publish public/ to the orphan branch `pages` (Cloudflare Pages deploys it).
# aime_data/publish.py decides: identical rebuilds are a no-op, changed bytes
# for an already published Overture release become the next data revision
# (<release>-r<N+1>), and published dataset paths are never rewritten. The
# previous dataset stays next to the new one; older ones drop out. History on
# `pages` is never kept.
#
#   scripts/publish.sh [public] [--dry-run]
set -euo pipefail
public=${1:-public}
dry=${2:-}
python3 -m aime_data.validate "$public"

# Distinguish an absent branch from a transport/authentication failure. Never
# discard retained data merely because a fetch failed.
remote=$(git ls-remote --heads origin refs/heads/pages)
expected=${remote%%[[:space:]]*}
published=$(mktemp -d)
trap 'rm -rf "$published"' EXIT
if [[ -n "$expected" ]]; then
  git fetch -q --depth=1 origin pages
  expected=$(git rev-parse FETCH_HEAD)
  git archive "$expected" | tar -x -C "$published"
fi

plan=$(python3 -m aime_data.publish "$public" "$published")
if [[ "$plan" == noop ]]; then
  echo "Dataset unchanged; retaining the existing pages commit."
  exit 0
fi
dataset=${plan#publish }

gitdir=$(git rev-parse --absolute-git-dir)
index_dir=$(mktemp -d)
index="$index_dir/index"
tree=$(cd "$public" && GIT_INDEX_FILE=$index git --git-dir="$gitdir" --work-tree=. add -A . \
  && GIT_INDEX_FILE=$index git --git-dir="$gitdir" write-tree)
rm -rf "$index_dir"
commit=$(git -c user.name="aime-data build" -c user.email="actions@users.noreply.github.com" \
  commit-tree "$tree" -m "Landmark cells, dataset $dataset")
echo "pages commit $commit (dataset $dataset)"
if [[ "$dry" == "--dry-run" ]]; then
  git ls-tree -r --name-only "$commit" | sed -n '1,5p;$p'
  exit 0
fi
git push --force-with-lease="refs/heads/pages:$expected" origin "$commit:refs/heads/pages"
