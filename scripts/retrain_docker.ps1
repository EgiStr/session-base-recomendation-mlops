# One-command retrain against the docker MLflow server.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/retrain_docker.ps1
# Optional overrides: $env:SESSIONS, $env:HOLDOUT_DAYS
$ErrorActionPreference = "Stop"
$env:MLFLOW_TRACKING_URI = "http://localhost:5000"
# MLflow prints a runner emoji on run close; force UTF-8 stdout so the
# retrain doesn't die with UnicodeEncodeError on cp1252 consoles.
$env:PYTHONUTF8 = "1"
$sessions = if ($env:SESSIONS) { $env:SESSIONS } else { "200000" }
$holdout = if ($env:HOLDOUT_DAYS) { $env:HOLDOUT_DAYS } else { "7" }
python -m src.training.train_real --sessions $sessions --holdout-days $holdout
Write-Output "Run URL: http://localhost:5000/#/experiments/0"
