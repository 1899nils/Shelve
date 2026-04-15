#!/usr/bin/env bash
# Bootstrap this checkout with the dannyvfilms/yamtrack source tree.
#
# Run from the root of a fresh clone of this repo on a branch that only
# contains the local-customization files (.env.example,
# docker-compose.local.yml, scripts/bootstrap-from-upstream.sh).
#
#   bash scripts/bootstrap-from-upstream.sh
#   git push
#
# Result: a single new commit that adds the upstream yamtrack source
# next to your local customizations, ready to push.

set -euo pipefail

UPSTREAM_REPO="https://github.com/dannyvfilms/yamtrack.git"
UPSTREAM_REF="${UPSTREAM_REF:-main}"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit or stash changes first." >&2
  exit 1
fi

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

echo "Cloning $UPSTREAM_REPO ($UPSTREAM_REF) ..."
git clone --depth 1 --branch "$UPSTREAM_REF" "$UPSTREAM_REPO" "$work_dir/yamtrack"
upstream_sha="$(git -C "$work_dir/yamtrack" rev-parse HEAD)"
rm -rf "$work_dir/yamtrack/.git"

# Preserve our local customization files (in case upstream ships same paths).
backup="$work_dir/keep"
mkdir -p "$backup/scripts"
cp .env.example                       "$backup/.env.example"
cp docker-compose.local.yml           "$backup/docker-compose.local.yml"
cp scripts/bootstrap-from-upstream.sh "$backup/scripts/bootstrap-from-upstream.sh"

# Wipe the working tree (preserving .git) and drop upstream in.
find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
cp -a "$work_dir/yamtrack/." ./

# Re-apply customizations.
cp "$backup/.env.example"             .env.example
cp "$backup/docker-compose.local.yml" docker-compose.local.yml
mkdir -p scripts
cp "$backup/scripts/bootstrap-from-upstream.sh" scripts/bootstrap-from-upstream.sh
chmod +x scripts/bootstrap-from-upstream.sh

git add -A
git commit -m "chore: import dannyvfilms/yamtrack@${upstream_sha:0:10}"

echo
echo "Imported upstream commit ${upstream_sha}."
echo "Review the commit, then push with: git push"
