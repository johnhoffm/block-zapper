#!/usr/bin/env bash
set -euo pipefail

repo="${MCMETA_REPO:-https://github.com/misode/mcmeta.git}"
ref="${1:-${MCMETA_REF:-1.21.8-data}}"
cache_dir="${MCMETA_CACHE_DIR:-tests/integration/.cache/mcmeta}"
structure_path="${MCMETA_STRUCTURE_PATH:-data/minecraft/structure}"
safe_ref="${ref//\//_}"
dest="${cache_dir}/${safe_ref}"

mkdir -p "${cache_dir}"

if [[ -d "${dest}/.git" ]]; then
  git -C "${dest}" fetch --depth 1 origin "${ref}"
  git -C "${dest}" checkout --detach FETCH_HEAD
else
  tmp_dest="${dest}.tmp"
  rm -rf "${tmp_dest}"
  git clone \
    --depth 1 \
    --filter=blob:none \
    --sparse \
    --branch "${ref}" \
    "${repo}" \
    "${tmp_dest}"
  mv "${tmp_dest}" "${dest}"
fi

git -C "${dest}" sparse-checkout set "${structure_path}"

structure_dir="${dest}/${structure_path}"
if [[ ! -d "${structure_dir}" ]]; then
  echo "Expected structure directory was not found: ${structure_dir}" >&2
  exit 1
fi

structure_count="$(find "${structure_dir}" -type f -name '*.nbt' | wc -l | tr -d '[:space:]')"

echo "Cached ${structure_count} Minecraft structure files from ${repo} (${ref})."
echo "Structure root: ${structure_dir}"
echo "To use a custom cache in tests:"
echo "  BZ_MCMETA_STRUCTURE_DIR=${structure_dir} .venv/bin/python -m pytest tests/integration"
