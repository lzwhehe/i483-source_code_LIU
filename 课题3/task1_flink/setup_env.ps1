$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$JarDir = Join-Path $ProjectRoot ".tools\jars"
$JdkDir = Join-Path $ProjectRoot ".tools\jdk-11"
$JarPath = Join-Path $JarDir "flink-sql-connector-kafka-3.0.2-1.18.jar"
$JdkZip = Join-Path $ProjectRoot ".tools\temurin11.zip"

New-Item -ItemType Directory -Force $JarDir | Out-Null

if (!(Test-Path (Join-Path $ProjectRoot ".venv"))) {
    python -m venv (Join-Path $ProjectRoot ".venv")
}

& (Join-Path $ProjectRoot ".venv\Scripts\python.exe") -m pip install --upgrade pip wheel
& (Join-Path $ProjectRoot ".venv\Scripts\python.exe") -m pip install -r (Join-Path $ProjectRoot "requirements.txt")

if (!(Test-Path $JdkDir)) {
    New-Item -ItemType Directory -Force (Join-Path $ProjectRoot ".tools") | Out-Null
    Invoke-WebRequest `
        -Uri "https://api.adoptium.net/v3/binary/latest/11/ga/windows/x64/jdk/hotspot/normal/eclipse?project=jdk" `
        -OutFile $JdkZip
    Expand-Archive -Path $JdkZip -DestinationPath (Join-Path $ProjectRoot ".tools\jdk11_tmp") -Force
    $ExtractedJdk = Get-ChildItem (Join-Path $ProjectRoot ".tools\jdk11_tmp") -Directory | Select-Object -First 1
    Move-Item -LiteralPath $ExtractedJdk.FullName -Destination $JdkDir
    Remove-Item (Join-Path $ProjectRoot ".tools\jdk11_tmp") -Recurse -Force
    Remove-Item $JdkZip -Force
}

if (!(Test-Path $JarPath)) {
    Invoke-WebRequest `
        -Uri "https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.0.2-1.18/flink-sql-connector-kafka-3.0.2-1.18.jar" `
        -OutFile $JarPath
}

Write-Host "Task 1 environment is ready."
Write-Host "Run with: .\run_task1.ps1"
