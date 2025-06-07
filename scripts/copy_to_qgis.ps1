# PowerShell script to copy vgridtools to QGIS plugins directory

# Define source and destination paths
$sourcePath = Join-Path $PSScriptRoot ".."
$destPath = "C:\Users\TECHCRAFT-QDThang\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\vgridtools"

# Create destination directory if it doesn't exist
if (-not (Test-Path $destPath)) {
    New-Item -ItemType Directory -Path $destPath -Force
    Write-Host "Created destination directory: $destPath"
}

# Define files and directories to exclude
$excludeItems = @(
    ".git",
    "__pycache__",
    ".vscode",
    "test",
    "scripts",
    ".gitignore",
    ".gitattributes",
    "error.md"
)

# Create a filter for the Copy-Item command
$excludeFilter = $excludeItems | ForEach-Object { "-$_" }

# Copy files and directories
Write-Host "Copying files to QGIS plugins directory..."
Copy-Item -Path "$sourcePath\*" -Destination $destPath -Recurse -Force -Exclude $excludeItems

# Verify the copy
$sourceFiles = Get-ChildItem -Path $sourcePath -Recurse -File | Where-Object { $excludeItems -notcontains $_.Directory.Name }
$destFiles = Get-ChildItem -Path $destPath -Recurse -File

Write-Host "`nCopy completed!"
Write-Host "Source files count: $($sourceFiles.Count)"
Write-Host "Destination files count: $($destFiles.Count)"

# Check if QGIS is running
$qgisProcess = Get-Process -Name "qgis" -ErrorAction SilentlyContinue
if ($qgisProcess) {
    Write-Host "`nQGIS is currently running. Please restart QGIS to load the updated plugin."
} else {
    Write-Host "`nQGIS is not running. You can start QGIS to use the updated plugin."
} 