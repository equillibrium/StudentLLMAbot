$PROJECT = "test-studentllmabot"
$IMAGE = "ghcr.io/equillibrium/studentllmabot"
$COMMIT_MESSAGE = "Fix redis url"

function Base64Decode
{
    param(
        [string]$EncodedString
    )

    if ( [string]::IsNullOrEmpty($EncodedString))
    {
        Write-Warning "Input string is null or empty. Returning null."
        return $null
    }

    try
    {
        $bytes = [System.Convert]::FromBase64String($EncodedString)
        [System.Text.Encoding]::UTF8.GetString($bytes) #Directly converts bytes to string using UTF8 encoding
    }
    catch
    {
        Write-Error "Error decoding Base64 string: $_"
        return $null
    }
}

if (-not (Get-Process 'Docker Desktop')) {
    . "C:\Program Files\Docker\Docker\Docker Desktop.exe"
}

$KubeStatus = . kubectl.exe get nodes
while (-not $KubeStatus) {
    $KubeStatus
    Start-Sleep -Seconds 3
    $KubeStatus = . kubectl.exe get nodes
}

kubectl config use-context docker-desktop

kubectl create ns $PROJECT

kubectl create secret generic $PROJECT -n $PROJECT --from-env-file="..\.env" `
  --dry-run=client -o yaml | kubectl apply -n $PROJECT -f -

$EncUser = kubectl get secret $PROJECT -n $PROJECT -o jsonpath="{.data.GITHUB_USERNAME}"
$EncPAT = kubectl get secret $PROJECT -n $PROJECT -o jsonpath="{.data.GITHUB_PAT}"
$EncMAIL = kubectl get secret $PROJECT -n $PROJECT -o jsonpath="{.data.GITHUB_EMAIL}"

$GITHUB_USERNAME = Base64Decode($EncUser)
$GITHUB_PAT = Base64Decode($EncPAT)
$GITHUB_EMAIL = Base64Decode($EncMAIL)

kubectl create secret docker-registry ghcr `
            -n "$PROJECT" `
            --docker-server=ghcr.io `
            --docker-username=$GITHUB_USERNAME `
            --docker-password=$GITHUB_PAT `
            --docker-email=$GITHUB_EMAIL `
            --dry-run=client -o=yaml | kubectl apply -n $PROJECT -f -

kubectl create serviceaccount "$PROJECT" -n "$PROJECT" `
            --dry-run=client -o=yaml | kubectl apply -n $PROJECT -f -

kubectl patch serviceaccount $PROJECT -n $PROJECT -p '{\"imagePullSecrets\":[{\"name\":\"ghcr\"}]}'

helm upgrade --install --namespace default redis-k8s oci://registry-1.docker.io/bitnamicharts/redis `
            --set=architecture=standalone --set=auth.enabled=false

"$GITHUB_PAT" | docker login "ghcr.io" -u $GITHUB_USERNAME --password-stdin
docker build -t "$IMAGE`:test" ..\.
docker push "$IMAGE`:test"

(Get-Content ..\k8s\deployment.yaml).Replace("`${PROJECT}", "$PROJECT").Replace("`${IMAGE}:latest",
        "$IMAGE`:test").Replace("`${COMMIT_MESSAGE}", "$COMMIT_MESSAGE") | `
        kubectl apply -f -