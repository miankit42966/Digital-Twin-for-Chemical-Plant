param([switch]$Fetch)
$ErrorActionPreference = 'Stop'
if ($Fetch) {
  py -m ml.ingestion.fetch_ai4i
  py -m ml.ingestion.fetch_tep
}
py -m ml.ingestion.ingest_ai4i
py -m ml.ingestion.ingest_tep
py -m ml.eda.ai4i_eda
py -m ml.eda.tep_eda
