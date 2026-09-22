#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${ROOT}/.reproduce"
ASSET1="mia-public-sealed-evidence-v1.zip"
ASSET2="mia-public-reproducibility-supplement-v1.zip"
SHA1="429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b"
SHA2="1687798651c324abc5824d14ce94569765a90117e0695bfcff87ccea8b08bd99"

rm -rf "${WORK}"
mkdir -p "${WORK}/downloads" "${WORK}/sealed" "${WORK}/supplement" "${WORK}/generated"

if [[ ! -f "${WORK}/downloads/${ASSET1}" ]]; then
  gh release download artifact-v1.0 --repo hollylessthan/metric-intent-assurance-artifact --pattern "${ASSET1}" --dir "${WORK}/downloads"
fi
if [[ ! -f "${WORK}/downloads/${ASSET2}" ]]; then
  gh release download artifact-v1.0 --repo hollylessthan/metric-intent-assurance-artifact --pattern "${ASSET2}" --dir "${WORK}/downloads"
fi

echo "${SHA1}  ${WORK}/downloads/${ASSET1}" | sha256sum -c -
echo "${SHA2}  ${WORK}/downloads/${ASSET2}" | sha256sum -c -

unzip -q "${WORK}/downloads/${ASSET1}" -d "${WORK}/sealed"
unzip -q "${WORK}/downloads/${ASSET2}" -d "${WORK}/supplement"

SEALED="${WORK}/sealed/mia-public-sealed-evidence"
SUPP="${WORK}/supplement/mia-public-reproducibility-supplement-v1"
GEN="${WORK}/generated"

# Replay scripts require the exact adapter inputs next to the sealed final-MIA outputs.
cp "${SUPP}/requests/final-mia/gpt/requests.jsonl" "${SEALED}/final-mia/gpt/requests.jsonl"
cp "${SUPP}/requests/final-mia/claude/requests.jsonl" "${SEALED}/final-mia/claude/requests.jsonl"

cd "${ROOT}"

python scripts/evaluate_historical.py --provider gpt --predictions "${SUPP}/historical/gpt/predictions.jsonl" --output "${GEN}/historical-gpt.json"
python scripts/evaluate_historical.py --provider claude --predictions "${SUPP}/historical/claude/predictions.jsonl" --output "${GEN}/historical-claude.json"

python scripts/evaluate_final_v2.py \
  --v2-gpt "${SEALED}/final-mia/gpt" --v2-claude "${SEALED}/final-mia/claude" \
  --v1-gpt "${SUPP}/historical/gpt" --v1-claude "${SUPP}/historical/claude" \
  --confirmatory-dir "${SUPP}/historical/confirmatory" --output-dir "${GEN}/final-v2" \
  --source-run-id 35426074276 --source-head-sha c3f8167473f9a4fa01beae39c1562d57e745932b

for provider in gpt claude; do
  python scripts/regenerate_b2_matched.py --provider "${provider}" --mia-artifact "${SEALED}/final-mia/${provider}" --output "${GEN}/b2-${provider}/predictions.jsonl"
  python scripts/evaluate_matched.py --predictions "${GEN}/b2-${provider}/predictions.jsonl" --output "${GEN}/b2-${provider}/evaluation.json"
  python scripts/evaluate_matched.py --predictions "${SEALED}/b4-matched/${provider}/predictions.jsonl" --output "${GEN}/b4-${provider}/evaluation.json"
  python scripts/v2_mechanism_replay.py --provider "${provider}" --mia-artifact "${SEALED}/final-mia/${provider}" --b4-artifact "${SEALED}/b4-matched/${provider}" --output "${GEN}/mechanism-${provider}/report.json"
  python scripts/clean_prompt_audit.py --provider "${provider}" --final-artifact "${SEALED}/final-mia/${provider}" --clean-artifact "${SEALED}/clean-prompt/${provider}" --output "${GEN}/clean-${provider}.json"
  python scripts/final_component_analysis.py --provider "${provider}" --mia-artifact "${SEALED}/final-mia/${provider}" --b4-artifact "${SEALED}/b4-matched/${provider}" --b2-eval "${GEN}/b2-${provider}" --output "${GEN}/component-${provider}.json"
done

python scripts/topn_defect_sensitivity.py \
  --confirmatory "${SUPP}/historical/confirmatory" \
  --gpt-mia "${SEALED}/final-mia/gpt" --claude-mia "${SEALED}/final-mia/claude" \
  --gpt-b4 "${SEALED}/b4-matched/gpt" --claude-b4 "${SEALED}/b4-matched/claude" \
  --output "${GEN}/topn.json"

python scripts/summarize_challenge_v2.py --evaluation "${SUPP}/challenge-v2/challenge_v2_evaluation.json" --output "${GEN}/challenge-v2.json"
cp "${SUPP}/historical/confirmatory/h2-contrastive-visibility.json" "${GEN}/h2.json"

python scripts/verify_reproduced_evidence.py --generated "${GEN}" --repo-root "${ROOT}"
echo "Paper evidence reproduction: PASS"
