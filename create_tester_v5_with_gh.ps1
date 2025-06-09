# PowerShell script to create tester_V5 repository using GitHub CLI
# Run this from PowerShell with: .\create_tester_v5_with_gh.ps1

Write-Host "Creating tester_V5 repository with GitHub CLI..." -ForegroundColor Green

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

# Create repository on GitHub using gh CLI
Write-Host "`nCreating repository on GitHub..." -ForegroundColor Green
$description = "Diode Dynamics Production Test System V5 - Enhanced SMT testing with programming UI"

# Ask user for visibility preference
$visibility = Read-Host "Make repository public or private? (public/private)"
if ($visibility -ne "private") {
    $visibility = "public"
}

try {
    # Create the repository and push
    gh repo create tester_V5 --$visibility --source=. --description="$description" --push
    
    Write-Host "`nSuccess! Repository created and pushed to GitHub!" -ForegroundColor Green
    Write-Host "View your repository at: https://github.com/YOUR_USERNAME/tester_V5" -ForegroundColor Cyan
    
    # Open in browser
    $openInBrowser = Read-Host "`nOpen repository in browser? (y/n)"
    if ($openInBrowser -eq "y") {
        gh repo view --web
    }
} catch {
    Write-Host "`nError creating repository. Make sure you're logged in to GitHub CLI." -ForegroundColor Red
    Write-Host "Run 'gh auth login' to authenticate with GitHub." -ForegroundColor Yellow
}