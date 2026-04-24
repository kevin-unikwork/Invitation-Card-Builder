# Easy way to run the Gujarati invitation template

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$templatePath = Join-Path $scriptDir "sample_gujarati_template.json"
$outputDir = Join-Path $scriptDir ".." "output"
$outputPath = Join-Path $outputDir "gujarati_invitation.png"

# Create output directory if needed
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

# Run the renderer
Write-Host "🎨 Running Gujarati Invitation Renderer..." -ForegroundColor Cyan
Write-Host ""

python "$scriptDir\render_json_template.py" "$templatePath" --output "$outputPath"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Invitation rendered successfully!" -ForegroundColor Green
    Write-Host "📁 Output: $outputPath" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "❌ Error rendering invitation" -ForegroundColor Red
    exit 1
}
