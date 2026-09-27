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

if git fetch -q --depth=1 origin pages 2>/dev/null; then
  prev=$(git show FETCH_HEAD:v1/index.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["release"])' || true)
  if [[ -n "$prev" && "$prev" != "$release" ]] && git cat-file -e "FETCH_HEAD:v1/$prev" 2>/dev/null; then
    echo "keeping previous release $prev"
    git archive FETCH_HEAD "v1/$prev" | tar -x -C "$public"
  fi
fi

gitdir=$(git rev-parse --absolute-git-dir)
index=$(mktemp -u)
tree=$(cd "$public" && GIT_INDEX_FILE=$index git --git-dir="$gitdir" --work-tree=. add -A . \
  && GIT_INDEX_FILE=$index git --git-dir="$gitdir" write-tree)
rm -f "$index"
commit=$(git -c user.name="aime-data build" -c user.email="actions@users.noreply.github.com" \
  commit-tree "$tree" -m "Landmark cells, Overture release $release")
echo "pages commit $commit (release $release)"
if [[ "$dry" == "--dry-run" ]]; then
  git ls-tree -r --name-only "$commit" | sed -n '1,5p;$p'
  exit 0
fi
git push --force origin "$commit:refs/heads/pages"
