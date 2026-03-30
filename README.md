# Multiplayer Chess with Microservices

### Setup (minikube)

**1. Install kubectl and minikube**
```bash
# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
sudo install kubectl /usr/local/bin/kubectl
```

**2. Start the cluster**
```bash
minikube start
```

**3. Enable the ingress addon**
```bash
minikube addons enable ingress
```
This installs the nginx ingress controller `ingress.yaml` expects.

**4. Deploy**
```bash
make deploy
```

**5. Access the frontend**

minikube doesn't expose `localhost` directly, leave this running in a separate terminal:
```bash
minikube tunnel
```
Then visit `http://localhost` in your browser.

---

### Useful commands

```bash
minikube status                                   # Check cluster is running
kubectl get pods -n microservices                 # See all your pods
kubectl logs <pod-name> -n microservices          # Logs for a pod
kubectl describe pod <pod-name> -n microservices  # Debug a stuck pod
minikube dashboard                                # Visual UI in your browser
minikube stop                                     # Pause the cluster
minikube delete                                   # Wipe everything and start fresh
```