param([switch]$Fetch)
$ErrorActionPreference = 'Stop'
$repoPath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonPath = Join-Path $repoPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
  throw 'Project Python environment missing. Create .venv and install backend/ML requirements first.'
}
function Invoke-DataModule([string]$Module) {
  & $pythonPath -m $Module
  if ($LASTEXITCODE -ne 0) { throw "$Module failed with exit code $LASTEXITCODE. Pipeline stopped." }
}
Push-Location -LiteralPath $repoPath
try {
  if ($Fetch) {
    Invoke-DataModule 'ml.ingestion.fetch_ai4i'
    Invoke-DataModule 'ml.ingestion.fetch_tep'
  }
  Invoke-DataModule 'ml.ingestion.ingest_ai4i'
  Invoke-DataModule 'ml.ingestion.ingest_tep'
  Invoke-DataModule 'ml.eda.ai4i_eda'
  Invoke-DataModule 'ml.eda.tep_eda'
} finally { Pop-Location }
