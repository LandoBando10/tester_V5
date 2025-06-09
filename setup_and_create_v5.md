# Steps to Create tester_V5 Repository

## 1. First, check if you're logged in to GitHub CLI:
Open PowerShell and run:
```powershell
gh auth status
```

If you're not logged in, run:
```powershell
gh auth login
```
- Choose "GitHub.com"
- Choose "HTTPS"
- Authenticate with your browser or paste an authentication token

## 2. Run the creation script:
Navigate to the tester-V4 directory and run:
```powershell
cd "C:\Users\ldev2\OneDrive\Documents\od\OneDrive\Desktop\New folder\tester-V4"
.\create_tester_v5_with_gh.ps1
```

The script will:
- Copy your project to a new folder called `tester_V5`
- Remove the old git history
- Initialize a new git repository
- Create an initial commit
- Create the repository on GitHub
- Push all files to GitHub
- Optionally open the repository in your browser

## 3. If the script fails, you can do it manually:
```powershell
# From the parent directory
cd "C:\Users\ldev2\OneDrive\Documents\od\OneDrive\Desktop\New folder"
cp -r tester-V4 tester_V5
cd tester_V5

# Remove old git and reinitialize
Remove-Item -Recurse -Force .git
git init
git add .
git commit -m "Initial commit - Tester V5 with programming UI for SMT testing"

# Create and push with gh CLI
gh repo create tester_V5 --public --source=. --push
```

## What's New in V5:
- Enhanced SMT widget with integrated programming UI
- Programming progress bar and status tracking
- Programming results table with pass/fail indicators
- Improved PCB panel visualization with color-coded results
- Removed excessive debug logging
- Better separation of programming and power validation results