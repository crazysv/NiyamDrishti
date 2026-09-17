param(
    [string]$RawRoot = (Join-Path (Split-Path $PSScriptRoot -Parent | Split-Path -Parent) 'test_data\benchmark_raw'),
    [string]$OutputPath = (Join-Path (Split-Path $PSScriptRoot -Parent | Split-Path -Parent) 'test_data\label_studio\tasks_raw.json')
)

$imageExtensions = @('.jpg', '.jpeg', '.png')
$rawRootResolved = (Resolve-Path -LiteralPath $RawRoot).Path
$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

$tasks = Get-ChildItem -LiteralPath $rawRootResolved -Directory |
    Sort-Object Name |
    ForEach-Object {
        $sampleId = $_.Name
        Get-ChildItem -LiteralPath $_.FullName -File |
            Where-Object { $imageExtensions -contains $_.Extension.ToLowerInvariant() } |
            Sort-Object Name |
            ForEach-Object {
                $relativePath = $_.FullName.Substring($rawRootResolved.Length).TrimStart('\') -replace '\\', '/'
                $imageRole = switch -Regex ($_.BaseName.ToLowerInvariant()) {
                    '^front' { 'front_pdp'; break }
                    '^back' { 'back_panel'; break }
                    '^side' { 'side_panel'; break }
                    '^mrp|^sticker' { 'sticker'; break }
                    default { 'other' }
                }

                [ordered]@{
                    data = [ordered]@{
                        image = "/data/local-files/?d=benchmark_raw/$relativePath"
                        sample_id = $sampleId
                        image_role = $imageRole
                        source_filename = $_.Name
                    }
                }
            }
    }

if (-not $tasks -or @($tasks).Count -eq 0) {
    throw "No JPG, JPEG, or PNG benchmark images were found under $rawRootResolved"
}

@($tasks) | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Output "Created $(@($tasks).Count) Label Studio tasks: $OutputPath"
