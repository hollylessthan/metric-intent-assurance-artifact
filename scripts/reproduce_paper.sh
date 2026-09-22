#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${ROOT}/.reproduce"
DOWNLOADS="${ROOT}/.reproduce-downloads"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ASSET1="mia-public-sealed-evidence-v1.zip"
ASSET2="mia-public-reproducibility-supplement-v1.zip"
SHA1="429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b"
SHA2="1687798651c324abc5824d14ce94569765a90117e0695bfcff87ccea8b08bd99"

"${PYTHON_BIN}" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"Python 3.11+ is required; found {sys.version.split()[0]}")
print(f"Using Python {sys.version.split()[0]}")
PY

rm -rf "${WORK}"
mkdir -p "${DOWNLOADS}" "${WORK}/sealed" "${WORK}/supplement" "${WORK}/generated"

download_asset() {
  local asset="$1"
  local url="$2"
  local dest="${DOWNLOADS}/${asset}"
  if [[ -f "${dest}" ]]; then
    echo "Using pre-downloaded ${dest}"
    return
  fi
  if command -v gh >/dev/null 2>&1; then
    if gh release download artifact-v1.0 \
      --repo hollylessthan/metric-intent-assurance-artifact \
      --pattern "${asset}" --dir "${DOWNLOADS}"; then
      return
    fi
    echo "gh release download failed; falling back to curl" >&2
  fi
  command -v curl >/dev/null 2>&1 || { echo "curl is required when gh download is unavailable" >&2; exit 2; }
  curl -L --fail --retry 3 -o "${dest}" "${url}"
}

verify_sha256() {
  local expected="$1"
  local path="$2"
  if command -v sha256sum >/dev/null 2>&1; then
    echo "${expected}  ${path}" | sha256sum -c -
  elif command -v shasum >/dev/null 2>&1; then
    local observed
    observed="$(shasum -a 256 "${path}" | awk '{print $1}')"
    [[ "${observed}" == "${expected}" ]] || {
      echo "SHA-256 mismatch for ${path}: expected ${expected}, observed ${observed}" >&2
      exit 2
    }
    echo "${path}: OK"
  else
    echo "Need sha256sum or shasum for integrity verification" >&2
    exit 2
  fi
}

download_asset "${ASSET1}" "https://github.com/hollylessthan/metric-intent-assurance-artifact/releases/download/artifact-v1.0/${ASSET1}"
download_asset "${ASSET2}" "https://github.com/hollylessthan/metric-intent-assurance-artifact/releases/download/artifact-v1.0/${ASSET2}"
verify_sha256 "${SHA1}" "${DOWNLOADS}/${ASSET1}"
verify_sha256 "${SHA2}" "${DOWNLOADS}/${ASSET2}"

unzip -q "${DOWNLOADS}/${ASSET1}" -d "${WORK}/sealed"
unzip -q "${DOWNLOADS}/${ASSET2}" -d "${WORK}/supplement"

SEALED="${WORK}/sealed/mia-public-sealed-evidence"
SUPP="${WORK}/supplement/mia-public-reproducibility-supplement-v1"
GEN="${WORK}/generated"

# Replay scripts require the exact adapter inputs next to the sealed final-MIA outputs.
cp "${SUPP}/requests/final-mia/gpt/requests.jsonl" "${SEALED}/final-mia/gpt/requests.jsonl"
cp "${SUPP}/requests/final-mia/claude/requests.jsonl" "${SEALED}/final-mia/claude/requests.jsonl"

cd "${ROOT}"

"${PYTHON_BIN}" scripts/evaluate_historical.py --provider gpt --predictions "${SUPP}/historical/gpt/predictions.jsonl" --output "${GEN}/historical-gpt.json"
"${PYTHON_BIN}" scripts/evaluate_historical.py --provider claude --predictions "${SUPP}/historical/claude/predictions.jsonl" --output "${GEN}/historical-claude.json"

"${PYTHON_BIN}" scripts/evaluate_final_v2.py \
  --v2-gpt "${SEALED}/final-mia/gpt" --v2-claude "${SEALED}/final-mia/claude" \
  --v1-gpt "${SUPP}/historical/gpt" --v1-claude "${SUPP}/historical/claude" \
  --confirmatory-dir "${SUPP}/historical/confirmatory" --output-dir "${GEN}/final-v2" \
  --source-run-id 35426074276 --source-head-sha c3f8167473f9a4fa01beae39c1562d57e745932b

for provider in gpt claude; do
  "${PYTHON_BIN}" scripts/regenerate_b2_matched.py --provider "${provider}" --mia-artifact "${SEALED}/final-mia/${provider}" --output "${GEN}/b2-${provider}/predictions.jsonl"
  "${PYTHON_BIN}" scripts/evaluate_matched.py --predictions "${GEN}/b2-${provider}/predictions.jsonl" --output "${GEN}/b2-${provider}/evaluation.json"
  "${PYTHON_BIN}" scripts/evaluate_matched.py --predictions "${SEALED}/b4-matched/${provider}/predictions.jsonl" --output "${GEN}/b4-${provider}/evaluation.json"
  "${PYTHON_BIN}" scripts/v2_mechanism_replay.py --provider "${provider}" --mia-artifact "${SEALED}/final-mia/${provider}" --b4-artifact "${SEALED}/b4-matched/${provider}" --output "${GEN}/mechanism-${provider}/report.json"
  "${PYTHON_BIN}" scripts/clean_prompt_audit.py --provider "${provider}" --final-artifact "${SEALED}/final-mia/${provider}" --clean-artifact "${SEALED}/clean-prompt/${provider}" --output "${GEN}/clean-${provider}.json"
  "${PYTHON_BIN}" scripts/final_component_analysis.py --provider "${provider}" --mia-artifact "${SEALED}/final-mia/${provider}" --b4-artifact "${SEALED}/b4-matched/${provider}" --b2-eval "${GEN}/b2-${provider}" --output "${GEN}/component-${provider}.json"
done

"${PYTHON_BIN}" scripts/topn_defect_sensitivity.py \
  --confirmatory "${SUPP}/historical/confirmatory" \
  --gpt-mia "${SEALED}/final-mia/gpt" --claude-mia "${SEALED}/final-mia/claude" \
  --gpt-b4 "${SEALED}/b4-matched/gpt" --claude-b4 "${SEALED}/b4-matched/claude" \
  --output "${GEN}/topn.json"

"${PYTHON_BIN}" scripts/summarize_challenge_v2.py --evaluation "${SUPP}/challenge-v2/challenge_v2_evaluation.json" --output "${GEN}/challenge-v2.json"
cp "${SUPP}/historical/confirmatory/h2-contrastive-visibility.json" "${GEN}/h2.json"

"${PYTHON_BIN}" scripts/generate_paper_assets.py --generated "${GEN}" --output-dir "${GEN}/paper-assets"
"${PYTHON_BIN}" scripts/verify_reproduced_evidence.py --generated "${GEN}" --repo-root "${ROOT}"
echo "Paper evidence reproduction: PASS"
