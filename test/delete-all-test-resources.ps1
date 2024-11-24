$PROJECT = "test-studentllmabot"
kubectl config use docker-desktop
kubectl delete ns $PROJECT
helm delete redis-k8s --namespace default
# docker system prune -af