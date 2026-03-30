# Kubernetes Manifests

## Directory Structure

```
k8s/
├── namespace.yaml
├── ingress.yaml
├── postgres/
│   ├── secret.yaml
│   ├── configmap.yaml      # Init SQL — update with your actual ./postgres/init scripts
│   ├── pvc.yaml
│   └── deployment.yaml
├── auth-service/
│   └── deployment.yaml
├── lobby-service/
│   └── deployment.yaml
├── chess-service/
│   └── deployment.yaml
└── frontend/
    └── deployment.yaml
```

## Before Applying

1. **Replace `YOUR_GITHUB_USERNAME`** in all deployment.yaml files with your actual GitHub username.

2. **Update `postgres/configmap.yaml`** with the actual contents of your `./postgres/init` SQL files.

3. **Update `postgres/secret.yaml`** with real credentials if deploying anywhere beyond localhost.
   For production, consider sealing the secret with `kubeseal` or using an external secrets manager.

4. **Image pull secret** — if your ghcr.io packages are private, create a pull secret:
   ```bash
   kubectl create secret docker-registry ghcr-secret \
     --docker-server=ghcr.io \
     --docker-username=YOUR_GITHUB_USERNAME \
     --docker-password=YOUR_GITHUB_PAT \
     --namespace=microservices
   ```
   Then add `imagePullSecrets: [{name: ghcr-secret}]` to each deployment's pod spec.

5. **Health endpoints** — the readiness probes on the backend services assume a `/health`
   endpoint exists. Adjust the path if yours differs (e.g. `/`, `/healthz`, `/api/health`).

6. **Vite env vars** — if your frontend uses `VITE_` prefixed env vars for backend URLs,
   note that Vite bakes these in at build time. Set them as build args in your GitHub
   Actions workflow, not as runtime env vars in the deployment.

## Apply Order

```bash
kubectl apply -f k8s/namespace.yaml

# Postgres
kubectl apply -f k8s/postgres/secret.yaml
kubectl apply -f k8s/postgres/configmap.yaml
kubectl apply -f k8s/postgres/pvc.yaml
kubectl apply -f k8s/postgres/deployment.yaml

# Wait for postgres to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n microservices --timeout=60s

# Services
kubectl apply -f k8s/auth-service/deployment.yaml
kubectl apply -f k8s/lobby-service/deployment.yaml
kubectl apply -f k8s/chess-service/deployment.yaml
kubectl apply -f k8s/frontend/deployment.yaml

# Ingress (requires nginx ingress controller to be installed)
kubectl apply -f k8s/ingress.yaml
```

## Ingress Controller

If you don't have the nginx ingress controller installed yet:

```bash
# minikube
minikube addons enable ingress

# kind
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# generic (cloud or bare metal)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
```
