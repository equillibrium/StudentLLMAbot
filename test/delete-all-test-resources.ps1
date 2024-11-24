$PROJECT = "test-studentllmabot"
kubectl config use docker-desktop
if ($LASTEXITCODE -eq 1) { throw "Can't find context" }
kubectl delete ns $PROJECT
helm delete redis-k8s --namespace default
# docker system prune -af