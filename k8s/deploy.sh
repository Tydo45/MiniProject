#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
# Configuration — update these
# ─────────────────────────────────────────────
GITHUB_USERNAME="tydo45"
NAMESPACE="microservices"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMAGES=(
  "ghcr.io/${GITHUB_USERNAME}/auth-service:latest"
  "ghcr.io/${GITHUB_USERNAME}/lobby-service:latest"
  "ghcr.io/${GITHUB_USERNAME}/chess-service:latest"
  "ghcr.io/${GITHUB_USERNAME}/frontend:latest"
)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}${BOLD}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}${BOLD}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}${BOLD}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}${BOLD}[ERROR]${NC} $*" >&2; }
die()     { error "$*"; exit 1; }

# ─────────────────────────────────────────────
# Step 1: Confirm kubectl context
# ─────────────────────────────────────────────
confirm_context() {
  local current_context
  current_context=$(kubectl config current-context 2>/dev/null) \
    || die "kubectl is not configured or no context is set."

  echo ""
  echo -e "${BOLD}Current kubectl context:${NC} ${YELLOW}${current_context}${NC}"
  echo ""
  read -r -p "Deploy to this context? [y/N] " confirm
  [[ "${confirm}" =~ ^[Yy]$ ]] || die "Aborted by user."
  echo ""
}

# ─────────────────────────────────────────────
# Step 2: Verify images exist on ghcr.io
# ─────────────────────────────────────────────
verify_images() {
  info "Verifying images on ghcr.io..."

  local failed=0
  for image in "${IMAGES[@]}"; do
    if docker manifest inspect "${image}" > /dev/null 2>&1; then
      success "${image}"
    else
      error "Not found: ${image}"
      failed=1
    fi
  done

  [[ "${failed}" -eq 0 ]] || die "One or more images could not be found. Ensure your GitHub Actions build has completed."
  echo ""
}

# ─────────────────────────────────────────────
# Step 3: Apply manifests in order
# ─────────────────────────────────────────────
apply_manifests() {
  info "Applying manifests..."

  kubectl apply -f "${SCRIPT_DIR}/namespace.yaml"

  kubectl apply -f "${SCRIPT_DIR}/postgres/secret.yaml"
  kubectl apply -f "${SCRIPT_DIR}/postgres/configmap.yaml"
  kubectl apply -f "${SCRIPT_DIR}/postgres/pvc.yaml"
  kubectl apply -f "${SCRIPT_DIR}/postgres/deployment.yaml"

  success "Postgres manifests applied."
  echo ""
}

# ─────────────────────────────────────────────
# Step 4: Wait for postgres to be ready
# ─────────────────────────────────────────────
wait_for_postgres() {
  info "Waiting for Postgres to be ready..."

  kubectl wait \
    --for=condition=ready pod \
    --selector=app=postgres \
    --namespace="${NAMESPACE}" \
    --timeout=120s \
    || die "Postgres did not become ready in time. Check: kubectl logs -l app=postgres -n ${NAMESPACE}"

  success "Postgres is ready."
  echo ""
}

# ─────────────────────────────────────────────
# Step 5: Apply services and frontend
# ─────────────────────────────────────────────
apply_services() {
  info "Applying services..."

  kubectl apply -f "${SCRIPT_DIR}/auth-service/deployment.yaml"
  kubectl apply -f "${SCRIPT_DIR}/auth-service/secret.yaml"
  kubectl apply -f "${SCRIPT_DIR}/lobby-service/deployment.yaml"
  kubectl apply -f "${SCRIPT_DIR}/lobby-service/secret.yaml"
  kubectl apply -f "${SCRIPT_DIR}/chess-service/deployment.yaml"
  kubectl apply -f "${SCRIPT_DIR}/chess-service/secret.yaml"
  kubectl apply -f "${SCRIPT_DIR}/frontend/deployment.yaml"
  kubectl apply -f "${SCRIPT_DIR}/ingress.yaml"

  success "All service manifests applied."
  echo ""
}

# ─────────────────────────────────────────────
# Step 6: Rollout restart to re-pull latest images
# ─────────────────────────────────────────────
rollout_restart() {
  info "Triggering rollout restart to pull latest images..."

  local deployments=(auth-service lobby-service chess-service frontend)
  for dep in "${deployments[@]}"; do
    kubectl rollout restart deployment/"${dep}" -n "${NAMESPACE}"
    success "Restarted ${dep}"
  done
  echo ""

  info "Waiting for rollouts to complete..."
  for dep in "${deployments[@]}"; do
    kubectl rollout status deployment/"${dep}" -n "${NAMESPACE}" --timeout=120s \
      || warn "${dep} rollout did not complete cleanly — check: kubectl describe deployment/${dep} -n ${NAMESPACE}"
  done
  echo ""
}

# ─────────────────────────────────────────────
# Step 7: Summary
# ─────────────────────────────────────────────
print_summary() {
  echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}${BOLD}  Deploy complete!${NC}"
  echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo -e "${BOLD}Pods:${NC}"
  kubectl get pods -n "${NAMESPACE}"
  echo ""
  echo -e "${BOLD}Ingress:${NC}"
  kubectl get ingress -n "${NAMESPACE}"
  echo ""
  echo -e "  Frontend → ${CYAN}http://localhost${NC}"
  echo ""
}

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
main() {
  echo ""
  echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
  echo -e "${BOLD}║       Microservices Deploy Script        ║${NC}"
  echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
  echo ""

  confirm_context
  verify_images
  apply_manifests
  wait_for_postgres
  apply_services
  rollout_restart
  print_summary
}

main "$@"