param(
    [int]$Port = 8080
)

$repositoryRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$testDataRoot = Join-Path $repositoryRoot 'test_data'
$stateRoot = Join-Path $testDataRoot 'label_studio\state'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker Desktop is required. Install and start Docker Desktop, then rerun this script.'
}

New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null

docker run --rm -it `
    -p "${Port}:8080" `
    -v "${stateRoot}:/label-studio/data" `
    -v "${testDataRoot}:/label-studio/files" `
    --env LOCAL_FILES_SERVING_ENABLED=true `
    --env LOCAL_FILES_DOCUMENT_ROOT=/label-studio/files `
    heartexlabs/label-studio:latest
