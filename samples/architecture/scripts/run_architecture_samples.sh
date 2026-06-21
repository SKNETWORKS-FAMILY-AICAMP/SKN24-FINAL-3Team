#!/usr/bin/env bash
set -euo pipefail

# 프로젝트 루트에서 실행하세요.
# 예: bash samples/architecture/scripts/run_architecture_samples.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

TEMPLATE="templates/arch_template.docx"
if [ ! -f "$TEMPLATE" ]; then
  echo "템플릿을 찾을 수 없습니다: $TEMPLATE"
  echo "프로젝트 루트에서 실행했는지 확인하세요."
  exit 1
fi

run_one() {
  local idx="$1"
  local req="$2"
  local infra="$3"
  local outdir="_arch_lab_sample_${idx}"

  echo ""
  echo "=============================="
  echo "ARCH SAMPLE ${idx}"
  echo "requirements: ${req}"
  echo "infra       : ${infra}"
  echo "outdir      : ${outdir}"
  echo "=============================="

  python run_architecture_agent.py "$req" --arch-config "$infra" --out-dir "$outdir"
  python render_arch_docx.py "$outdir/document.json" --structure "$outdir/structure.json" --template "$TEMPLATE" --out "$outdir/architecture.docx"

  echo "생성 완료: ${outdir}/architecture.docx"
}

run_one "01" "samples/architecture/requirements/requirements.01_ai_sdlc.json" "samples/architecture/infra/infra_spec.01_fastapi_sdlc.json"
run_one "02" "samples/architecture/requirements/requirements.02_public_portal.json" "samples/architecture/infra/infra_spec.02_spring_public_portal.json"
run_one "03" "samples/architecture/requirements/requirements.03_data_platform.json" "samples/architecture/infra/infra_spec.03_node_data_platform.json"
run_one "04" "samples/architecture/requirements/requirements.04_lms_campus.json" "samples/architecture/infra/infra_spec.04_django_lms.json"
run_one "05" "samples/architecture/requirements/requirements.05_finance_internal.json" "samples/architecture/infra/infra_spec.05_egov_finance_internal.json"

echo ""
echo "전체 샘플 생성 완료"
