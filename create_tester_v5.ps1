# PowerShell script to create tester_V5 repository
# Run this from PowerShell with: .\create_tester_v5.ps1

Write-Host "Creating tester_V5 repository..." -ForegroundColor Green

# Get the parent directory
$parentDir = Split-Path -Parent $PSScriptRoot
Set-Location $parentDir

# Copy the project
Write-Host "Copying project files..." -ForegroundColor Yellow
Copy-Item -Path "tester-V4" -Destination "tester_V5" -Recurse

# Navigate to the new directory
Set-Location "tester_V5"

# Remove old git history
Write-Host "Removing old git history..." -ForegroundColor Yellow
Remove-Item -Path ".git" -Recurse -Force -ErrorAction SilentlyContinue

# Initialize new repository
Write-Host "Initializing new git repository..." -ForegroundColor Yellow
git init

# Add all files
Write-Host "Adding files to git..." -ForegroundColor Yellow
git add .

# Commit
Write-Host "Creating initial commit..." -ForegroundColor Yellow
git commit -m "Initial commit - Tester V5 with programming UI for SMT testing"

Write-Host "`nRepository created locally!" -ForegroundColor Green
Write-Host "`nNow you need to:" -ForegroundColor Cyan
Write-Host "1. Go to https://github.com/new" -ForegroundColor White
Write-Host "2. Create a new repository named 'tester_V5'" -ForegroundColor White
Write-Host "3. Don't initialize with README, .gitignore, or license" -ForegroundColor White
Write-Host "4. After creating, run these commands:" -ForegroundColor White
Write-Host ""
Write-Host "git remote add origin https://github.com/YOUR_USERNAME/tester_V5.git" -ForegroundColor Yellow
Write-Host "git branch -M main" -ForegroundColor Yellow
Write-Host "git push -u origin main" -ForegroundColor Yellow