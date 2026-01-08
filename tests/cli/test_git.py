"""Test cases for git."""

import pytest

from conftest import is_approved, needs_confirmation

#
# ==========================================================================
# Git
# ==========================================================================
#
TESTS = [
    ("git status", True),
    ("git status -s", True),
    ("git status --short", True),
    ("git status --porcelain", True),
    ("git status -b", True),
    ("git log", True),
    ("git log -10", True),
    ("git log --oneline", True),
    ("git log --oneline -5", True),
    ("git log --graph", True),
    ("git log --graph --oneline --all", True),
    ("git log --stat", True),
    ("git log -p", True),
    ("git log --patch", True),
    ("git log --author='John'", True),
    ("git log --since='2 weeks ago'", True),
    ("git log --grep='fix'", True),
    ("git log main..feature", True),
    ("git log HEAD~5..HEAD", True),
    ("git diff", True),
    ("git diff HEAD", True),
    ("git diff --staged", True),
    ("git diff --cached", True),
    ("git diff main..feature", True),
    ("git diff HEAD~1", True),
    ("git diff --stat", True),
    ("git diff --name-only", True),
    ("git diff --name-status", True),
    ("git diff file.txt", True),
    ("git show", True),
    ("git show HEAD", True),
    ("git show HEAD:file.txt", True),
    ("git show --stat", True),
    ("git show v1.0", True),
    ("git show abc123", True),
    ("git blame file.txt", True),
    ("git blame -L 10,20 file.txt", True),
    ("git blame --date=short file.txt", True),
    ("git shortlog", True),
    ("git shortlog -sn", True),
    ("git shortlog --summary --numbered", True),
    ("git reflog", True),
    ("git reflog show", True),
    ("git reflog show HEAD", True),
    ("git branch", True),
    ("git branch -a", True),
    ("git branch --all", True),
    ("git branch -v", True),
    ("git branch -vv", True),
    ("git branch --list", True),
    ("git branch --list 'feature/*'", True),
    ("git branch --show-current", True),
    ("git branch -r", True),
    ("git branch --remote", True),
    ("git branch --contains abc123", True),
    ("git branch --merged", True),
    ("git branch --no-merged", True),
    ("git tag", True),
    ("git tag -l", True),
    ("git tag --list", True),
    ("git tag -l 'v1.*'", True),
    ("git tag --contains abc123", True),
    ("git tag -n", True),
    ("git remote", True),
    ("git remote -v", True),
    ("git remote --verbose", True),
    ("git remote show origin", True),
    ("git remote get-url origin", True),
    ("git ls-files", True),
    ("git ls-files -s", True),
    ("git ls-files --cached", True),
    ("git ls-files --modified", True),
    ("git ls-files --others", True),
    ("git ls-tree HEAD", True),
    ("git ls-tree -r HEAD", True),
    ("git ls-remote", True),
    ("git ls-remote origin", True),
    ("git ls-remote --tags origin", True),
    ("git config --get user.name", True),
    ("git config --get user.email", True),
    ("git config --get-all user.name", True),
    ("git config --list", True),
    ("git config -l", True),
    ("git config --list --global", True),
    ("git config --list --local", True),
    ("git config --show-origin user.name", True),
    ("git stash list", True),
    ("git stash show", True),
    ("git stash show -p", True),
    ("git stash show --patch stash@{0}", True),
    ("git describe", True),
    ("git describe --tags", True),
    ("git describe --always", True),
    ("git rev-parse HEAD", True),
    ("git rev-parse --short HEAD", True),
    ("git rev-parse --abbrev-ref HEAD", True),
    ("git rev-parse --show-toplevel", True),
    ("git rev-list HEAD", True),
    ("git rev-list --count HEAD", True),
    ("git rev-list main..feature", True),
    ("git name-rev HEAD", True),
    ("git name-rev abc123", True),
    ("git merge-base main feature", True),
    ("git merge-base --is-ancestor main feature", True),
    ("git cat-file -t HEAD", True),
    ("git cat-file -p HEAD", True),
    ("git cat-file -s HEAD", True),
    ("git check-ignore file.txt", True),
    ("git check-ignore -v file.txt", True),
    ("git cherry main", True),
    ("git cherry -v main feature", True),
    ("git for-each-ref", True),
    ("git for-each-ref --sort=-committerdate", True),
    ("git for-each-ref refs/heads/", True),
    ("git grep pattern", True),
    ("git grep -n pattern", True),
    ("git grep --count pattern", True),
    ("git grep -i pattern", True),
    ("git count-objects", True),
    ("git count-objects -v", True),
    ("git fsck", True),
    ("git fsck --full", True),
    ("git verify-commit HEAD", True),
    ("git verify-tag v1.0", True),
    ("git notes list", True),
    ("git notes show", True),
    ("git worktree list", True),
    ("git fetch", True),
    ("git fetch origin", True),
    ("git fetch --all", True),
    ("git fetch --tags", True),
    ("git fetch --prune", True),
    ("git fetch origin main", True),
    # git - safe (with flags)
    ("git -C /some/path status", True),
    ("git -C /some/path log --oneline -5", True),
    ("git --git-dir=/some/.git status", True),
    ("git -c core.editor=vim log", True),
    ("git --no-pager log -5", True),
    ("git --paginate diff", True),
    ("git --help", True),
    ("git -h", True),
    ("git status --help", True),
    ("git --version", True),
    # git - unsafe (mutations)
    ("git add file.txt", False),
    ("git add .", False),
    ("git add -A", False),
    ("git add --all", False),
    ("git add -p", False),
    ("git add --patch", False),
    ("git commit", False),
    ("git commit -m 'message'", False),
    ("git commit -am 'message'", False),
    ("git commit --amend", False),
    ("git commit --amend --no-edit", False),
    ("git commit --fixup HEAD", False),
    ("git push", False),
    ("git push origin main", False),
    ("git push -u origin feature", False),
    ("git push --force", False),
    ("git push --force-with-lease", False),
    ("git push --tags", False),
    ("git push origin --delete feature", False),
    ("git pull", False),
    ("git pull origin main", False),
    ("git pull --rebase", False),
    ("git pull --ff-only", False),
    ("git merge feature", False),
    ("git merge --no-ff feature", False),
    ("git merge --squash feature", False),
    ("git merge --abort", False),
    ("git rebase main", False),
    ("git rebase -i HEAD~3", False),
    ("git rebase --interactive main", False),
    ("git rebase --continue", False),
    ("git rebase --abort", False),
    ("git rebase --skip", False),
    ("git cherry-pick abc123", False),
    ("git cherry-pick --continue", False),
    ("git cherry-pick --abort", False),
    ("git checkout feature", False),
    ("git checkout -b new-branch", False),
    ("git checkout -- file.txt", False),
    ("git checkout HEAD~1 -- file.txt", False),
    ("git switch feature", False),
    ("git switch -c new-branch", False),
    ("git switch --create new-branch", False),
    ("git restore file.txt", False),
    ("git restore --staged file.txt", False),
    ("git restore --source=HEAD~1 file.txt", False),
    # git - unsafe (branch/tag mutations)
    ("git branch new-branch", False),
    ("git branch -d feature", False),
    ("git branch -D feature", False),
    ("git branch --delete feature", False),
    ("git branch -m old new", False),
    ("git branch -M old new", False),
    ("git branch --move old new", False),
    ("git branch --set-upstream-to=origin/main", False),
    ("git tag v1.0", False),
    ("git tag -a v1.0 -m 'Version 1.0'", False),
    ("git tag -d v1.0", False),
    ("git tag --delete v1.0", False),
    # git - unsafe (remote mutations)
    ("git remote add origin https://github.com/user/repo.git", False),
    ("git remote remove origin", False),
    ("git remote rm origin", False),
    ("git remote rename origin upstream", False),
    ("git remote set-url origin https://new-url.git", False),
    ("git remote prune origin", False),
    # git - unsafe (config mutations)
    ("git config user.name 'John Doe'", False),
    ("git config --global user.email 'john@example.com'", False),
    ("git config --unset user.name", False),
    ("git config --edit", False),
    ("git config -e", False),
    ("git config --global --edit", False),
    # git - unsafe (stash mutations)
    ("git stash", False),
    ("git stash push", False),
    ("git stash push -m 'message'", False),
    ("git stash -u", False),
    ("git stash --include-untracked", False),
    ("git stash pop", False),
    ("git stash pop stash@{0}", False),
    ("git stash apply", False),
    ("git stash apply stash@{1}", False),
    ("git stash drop", False),
    ("git stash drop stash@{0}", False),
    ("git stash clear", False),
    ("git stash branch new-branch", False),
    # git - unsafe (history rewriting)
    ("git reset HEAD~1", False),
    ("git reset --soft HEAD~1", False),
    ("git reset --hard HEAD~1", False),
    ("git reset --mixed HEAD~1", False),
    ("git reset file.txt", False),
    ("git revert HEAD", False),
    ("git revert abc123", False),
    ("git revert --no-commit HEAD", False),
    ("git clean -f", False),
    ("git clean -fd", False),
    ("git clean -fx", False),
    ("git clean --force", False),
    ("git clean -n", False),  # dry-run but still marks files for deletion
    # git - unsafe (repository management)
    ("git init", False),
    ("git init --bare", False),
    ("git clone https://github.com/user/repo.git", False),
    ("git clone --depth 1 https://github.com/user/repo.git", False),
    ("git submodule add https://github.com/user/lib.git", False),
    ("git submodule update", False),
    ("git submodule update --init", False),
    ("git submodule update --init --recursive", False),
    ("git submodule init", False),
    ("git gc", False),
    ("git gc --aggressive", False),
    ("git prune", False),
    # git - unsafe (notes mutations)
    ("git notes add -m 'note'", False),
    ("git notes edit", False),
    ("git notes remove", False),
    # git - unsafe (worktree mutations)
    ("git worktree add ../new-worktree feature", False),
    ("git worktree remove ../old-worktree", False),
    ("git worktree prune", False),
    # git - unsafe (with force flag)
    ("git -C /tmp push --force", False),
    #
    # === Additional commands from tldr ===
    #
    # git rm (remove files)
    ("git rm file.txt", False),
    ("git rm -r path/to/directory", False),
    ("git rm --cached file.txt", False),  # removes from index only, still modifies
    ("git rm -f file.txt", False),
    #
    # git mv (move/rename files)
    ("git mv old.txt new.txt", False),
    ("git mv path/to/file path/to/destination", False),
    ("git mv -f old.txt new.txt", False),
    #
    # git archive (create archive - safe, read-only export)
    ("git archive HEAD", True),
    ("git archive --format=zip HEAD", True),
    ("git archive -o file.tar HEAD", True),
    ("git archive --output=file.zip HEAD", True),
    ("git archive -v HEAD", True),
    ("git archive --prefix=project/ HEAD", True),
    ("git archive HEAD:path/to/dir", True),
    ("git archive --remote=origin HEAD", True),
    #
    # git apply (apply patches - modifies working tree)
    ("git apply patch.diff", False),
    ("git apply --index patch.diff", False),
    ("git apply --cached patch.diff", False),
    ("git apply -R patch.diff", False),
    ("git apply --reverse patch.diff", False),
    ("git apply --stat patch.diff", False),  # just stats but still modifies
    ("git apply --check patch.diff", True),  # dry-run check only
    #
    # git am (apply patches as commits)
    ("git am patch.patch", False),
    ("git am --abort", False),
    ("git am --continue", False),
    ("git am --skip", False),
    ("git am --reject patch.patch", False),
    #
    # git format-patch (create patches - safe, read-only)
    ("git format-patch origin", True),
    ("git format-patch HEAD~3", True),
    ("git format-patch -3", True),
    ("git format-patch main..feature", True),
    ("git format-patch -o patches/ HEAD~5", True),
    #
    # git bisect (comprehensive)
    ("git bisect log", True),
    ("git bisect visualize", True),
    ("git bisect view", True),
    ("git bisect start", False),
    ("git bisect start HEAD HEAD~10", False),
    ("git bisect bad", False),
    ("git bisect good", False),
    ("git bisect good abc123", False),
    ("git bisect skip", False),
    ("git bisect reset", False),
    ("git bisect run ./test.sh", False),
    #
    # git whatchanged (read-only)
    ("git whatchanged", True),
    ("git whatchanged -p", True),
    ("git whatchanged --since='2 weeks ago'", True),
    #
    # git diff-tree, diff-files, diff-index (read-only)
    ("git diff-tree HEAD", True),
    ("git diff-tree -r HEAD", True),
    ("git diff-tree --stat HEAD", True),
    ("git diff-files", True),
    ("git diff-files -p", True),
    ("git diff-index HEAD", True),
    ("git diff-index --cached HEAD", True),
    #
    # git range-diff (read-only)
    ("git range-diff main..feature main..other", True),
    ("git range-diff HEAD~5..HEAD~2 HEAD~3..HEAD", True),
    #
    # git sparse-checkout (modifies checkout)
    ("git sparse-checkout init", False),
    ("git sparse-checkout set path/to/dir", False),
    ("git sparse-checkout add path/to/dir", False),
    ("git sparse-checkout disable", False),
    ("git sparse-checkout list", True),  # listing is safe
    ("git sparse-checkout reapply", False),
    #
    # git bundle (read operations safe, create needs confirmation)
    ("git bundle create repo.bundle HEAD", False),
    ("git bundle verify repo.bundle", True),
    ("git bundle list-heads repo.bundle", True),
    ("git bundle unbundle repo.bundle", False),
    #
    # git lfs (large file storage)
    ("git lfs install", False),
    ("git lfs track '*.psd'", False),
    ("git lfs untrack '*.psd'", False),
    ("git lfs pull", False),
    ("git lfs push origin main", False),
    ("git lfs fetch", True),  # fetch is read-only
    ("git lfs ls-files", True),
    ("git lfs status", True),
    ("git lfs env", True),
    #
    # git subtree
    ("git subtree add --prefix=lib repo main", False),
    ("git subtree pull --prefix=lib repo main", False),
    ("git subtree push --prefix=lib repo main", False),
    ("git subtree merge --prefix=lib main", False),
    ("git subtree split --prefix=lib", False),
    #
    # git maintenance
    ("git maintenance start", False),
    ("git maintenance stop", False),
    ("git maintenance run", False),
    ("git maintenance register", False),
    ("git maintenance unregister", False),
    #
    # git repack (modifies object store)
    ("git repack", False),
    ("git repack -a", False),
    ("git repack -d", False),
    #
    # git update-index (modifies index)
    ("git update-index --assume-unchanged file.txt", False),
    ("git update-index --no-assume-unchanged file.txt", False),
    ("git update-index --skip-worktree file.txt", False),
    ("git update-index --refresh", False),
    #
    # git hash-object (can modify with -w)
    ("git hash-object file.txt", True),  # just compute hash
    ("git hash-object -w file.txt", False),  # writes to object store
    ("git hash-object --stdin", True),
    #
    # git show-ref (read-only)
    ("git show-ref", True),
    ("git show-ref --heads", True),
    ("git show-ref --tags", True),
    ("git show-ref --verify refs/heads/main", True),
    #
    # git show-branch (read-only)
    ("git show-branch", True),
    ("git show-branch main feature", True),
    ("git show-branch --all", True),
    #
    # git symbolic-ref (read vs write)
    ("git symbolic-ref HEAD", True),  # reading
    ("git symbolic-ref HEAD refs/heads/main", False),  # writing
    #
    # git var (read-only)
    ("git var -l", True),
    ("git var GIT_AUTHOR_IDENT", True),
    ("git var GIT_COMMITTER_IDENT", True),
    #
    # git send-email (sends email - needs confirmation)
    ("git send-email patches/", False),
    ("git send-email --to=foo@bar.com HEAD~3", False),
    #
    # git request-pull (generates text - read-only)
    ("git request-pull origin/main https://example.com/repo main", True),
    #
    # git replace (modifies replacement refs)
    ("git replace abc123 def456", False),
    ("git replace -d abc123", False),
    ("git replace -l", True),  # listing is safe
    #
    # git rerere (modifies rerere cache)
    ("git rerere", True),  # status/info
    ("git rerere status", True),
    ("git rerere diff", True),
    ("git rerere clear", False),
    ("git rerere forget path/to/file", False),
    #
    # git instaweb (starts web server)
    ("git instaweb", False),
    ("git instaweb --start", False),
    ("git instaweb --stop", False),
    #
    # git daemon (starts server)
    ("git daemon", False),
    #
    # git mergetool (modifies files)
    ("git mergetool", False),
    ("git mergetool file.txt", False),
    #
    # git difftool (read-only viewing)
    ("git difftool", True),
    ("git difftool HEAD~1", True),
    ("git difftool main..feature", True),
    #
    # git annotate (alias for blame - read-only)
    ("git annotate file.txt", True),
    ("git annotate -L 10,20 file.txt", True),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_git(check, command: str, expected: bool) -> None:
    """Test command safety."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
