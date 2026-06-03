$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:JAVA_HOME = Join-Path $ProjectRoot ".tools\jdk-11"
$env:PATH = "$env:JAVA_HOME\bin;$ProjectRoot\.venv\Scripts;$env:PATH"
$env:PYFLINK_CLIENT_EXECUTABLE = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$env:PYFLINK_PYTHON = $env:PYFLINK_CLIENT_EXECUTABLE

Write-Host "Task 3 CEP environment activated."
Write-Host "JAVA_HOME=$env:JAVA_HOME"
Write-Host "Python=$ProjectRoot\.venv\Scripts\python.exe"
