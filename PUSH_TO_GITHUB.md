# Push this assignment from VS Code

1. Extract the ZIP and open the `CSA08-1924260076-Assignment5` folder in VS Code.
2. Open **Terminal → New Terminal**. Confirm that the terminal is at the project root.
3. Create a GitHub repository named `CSA08-1924260076-Assignment5`. Choose Public, or choose Private and add your faculty as a collaborator. Do not initialise the GitHub repository with a README or .gitignore.
4. Run the commands below one at a time. Replace the Git name/email and `YOUR_USERNAME` with your own details.

```powershell
git config --global user.name "Your GitHub Name"
git config --global user.email "your-email@example.com"
git init
git branch -M main

git add README.md requirements.txt .gitignore PUSH_TO_GITHUB.md TaskA
git commit -m "Add Part A design and project setup"

git add TaskB1
git commit -m "Complete Task B1 cleaning pipeline"

git add TaskB2
git commit -m "Complete Task B2 adversarial data tests"

git add TaskB3
git commit -m "Complete Task B3 loops pandas and SQL comparison"

git add TaskB4
git commit -m "Complete Task B4 sentiment and production decision"

git add outputs
git commit -m "Add execution results charts and profiling evidence"

git remote add origin https://github.com/YOUR_USERNAME/CSA08-1924260076-Assignment5.git
git push -u origin main
```

If Git says `nothing to commit`, check `git status`; there may be no new changes for that commit. If `git` is not recognised, install Git for Windows, restart VS Code and run `git --version`.

Verify with:
```powershell
git status
git log --oneline
```

The status should show a clean working tree after all changes are committed. Refresh the GitHub page and check that all task folders and outputs are present.
