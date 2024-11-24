$PROJECT = "test-studentllmabot"
kubectl delete ns $PROJECT
helm delete redis-k8s --namespace default