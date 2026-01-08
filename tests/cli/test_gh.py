"""Test cases for GitHub CLI (gh)."""

import pytest

from conftest import is_approved, needs_confirmation

# ==========================================================================
# GitHub CLI (gh)
# ==========================================================================
#
# gh uses second_token parser: gh <resource> <action>
# Safe actions: list, view, status, diff, checks, search, download, watch, verify
# Unsafe actions: create, delete, edit, merge, close, reopen, comment, review, etc.
#

TESTS = [
    #
    # --- gh pr (pull requests) ---
    # gh pr - safe (read-only)
    ("gh pr list", True),
    ("gh pr list --state open", True),
    ("gh pr list --state closed", True),
    ("gh pr list --limit 50", True),
    ("gh pr list -L 10", True),
    ("gh pr list --author @me", True),
    ("gh pr list --label bug", True),
    ("gh pr list --base main", True),
    ("gh pr list --head feature", True),
    ("gh pr view", True),
    ("gh pr view 123", True),
    ("gh pr view 123 --json title,body", True),
    ("gh pr view 123 --web", True),
    ("gh pr view --comments", True),
    ("gh pr status", True),
    ("gh pr diff", True),
    ("gh pr diff 123", True),
    ("gh pr diff --patch", True),
    ("gh pr checks", True),
    ("gh pr checks 123", True),
    ("gh pr checks --watch", True),
    ("gh pr checks --required", True),
    ("gh -R owner/repo pr list", True),
    ("gh --repo owner/repo pr view 123", True),
    ("gh pr list -R cli/cli", True),
    # gh pr - unsafe (mutations)
    ("gh pr create", False),
    ("gh pr create --title 'Fix bug'", False),
    ("gh pr create --fill", False),
    ("gh pr create --draft", False),
    ("gh pr create --web", False),
    ("gh pr checkout 123", False),
    ("gh pr close 123", False),
    ("gh pr close 123 --comment 'Closing'", False),
    ("gh pr reopen 123", False),
    ("gh pr merge", False),
    ("gh pr merge 123", False),
    ("gh pr merge --auto", False),
    ("gh pr merge --squash", False),
    ("gh pr merge --rebase", False),
    ("gh pr merge --delete-branch", False),
    ("gh pr edit 123", False),
    ("gh pr edit 123 --title 'New title'", False),
    ("gh pr edit --add-label bug", False),
    ("gh pr comment 123", False),
    ("gh pr comment 123 --body 'LGTM'", False),
    ("gh pr review 123", False),
    ("gh pr review 123 --approve", False),
    ("gh pr review 123 --request-changes", False),
    ("gh pr review --comment --body 'Nice'", False),
    ("gh pr ready 123", False),
    ("gh pr lock 123", False),
    ("gh pr unlock 123", False),
    ("gh pr revert 123", False),
    ("gh pr update-branch 123", False),
    #
    # --- gh issue ---
    # gh issue - safe (read-only)
    ("gh issue list", True),
    ("gh issue list --state open", True),
    ("gh issue list --state closed", True),
    ("gh issue list --state all", True),
    ("gh issue list --limit 100", True),
    ("gh issue list -L 50", True),
    ("gh issue list --author @me", True),
    ("gh issue list --assignee @me", True),
    ("gh issue list --label bug", True),
    ("gh issue list --label 'help wanted'", True),
    ("gh issue list --milestone v1.0", True),
    ("gh issue view 123", True),
    ("gh issue view 123 --json title,body,labels", True),
    ("gh issue view 123 --web", True),
    ("gh issue view 123 --comments", True),
    ("gh issue status", True),
    ("gh -R owner/repo issue list", True),
    ("gh issue list -R cli/cli", True),
    # gh issue - unsafe (mutations)
    ("gh issue create", False),
    ("gh issue create --title 'Bug report'", False),
    ("gh issue create --body 'Steps to reproduce'", False),
    ("gh issue create --label bug", False),
    ("gh issue create --web", False),
    ("gh issue close 123", False),
    ("gh issue close 123 --comment 'Fixed'", False),
    ("gh issue close 123 --reason completed", False),
    ("gh issue reopen 123", False),
    ("gh issue delete 123", False),
    ("gh issue delete 123 --yes", False),
    ("gh issue edit 123", False),
    ("gh issue edit 123 --title 'Updated title'", False),
    ("gh issue edit 123 --add-label enhancement", False),
    ("gh issue comment 123", False),
    ("gh issue comment 123 --body 'Working on it'", False),
    ("gh issue lock 123", False),
    ("gh issue unlock 123", False),
    ("gh issue pin 123", False),
    ("gh issue unpin 123", False),
    ("gh issue transfer 123 owner/other-repo", False),
    ("gh issue develop 123", False),
    ("gh issue develop 123 --checkout", False),
    #
    # --- gh repo ---
    # gh repo - safe (read-only)
    ("gh repo list", True),
    ("gh repo list owner", True),
    ("gh repo list --limit 50", True),
    ("gh repo list -L 100", True),
    ("gh repo list --source", True),
    ("gh repo list --fork", True),
    ("gh repo list --language python", True),
    ("gh repo list --topic cli", True),
    ("gh repo view", True),
    ("gh repo view owner/repo", True),
    ("gh repo view --web", True),
    ("gh repo view --json name,description", True),
    # gh repo - unsafe (mutations)
    ("gh repo create", False),
    ("gh repo create my-project", False),
    ("gh repo create --public", False),
    ("gh repo create --private", False),
    ("gh repo create --clone", False),
    ("gh repo clone owner/repo", False),
    ("gh repo clone cli/cli", False),
    ("gh repo fork owner/repo", False),
    ("gh repo fork --clone", False),
    ("gh repo delete owner/repo", False),
    ("gh repo delete owner/repo --yes", False),
    ("gh repo edit owner/repo", False),
    ("gh repo edit --visibility public", False),
    ("gh repo archive owner/repo", False),
    ("gh repo unarchive owner/repo", False),
    ("gh repo rename owner/repo new-name", False),
    ("gh repo sync owner/repo", False),
    ("gh repo set-default owner/repo", False),
    #
    # --- gh run (workflow runs) ---
    # gh run - safe (read-only)
    ("gh run list", True),
    ("gh run list --limit 20", True),
    ("gh run list -L 50", True),
    ("gh run list --workflow build.yml", True),
    ("gh run list --branch main", True),
    ("gh run list --status completed", True),
    ("gh run list --json status,conclusion", True),
    ("gh run view", True),
    ("gh run view 12345", True),
    ("gh run view 12345 --log", True),
    ("gh run view 12345 --log-failed", True),
    ("gh run view --job 67890", True),
    ("gh run view 12345 --json jobs", True),
    ("gh run view 12345 --web", True),
    ("gh run view 12345 --exit-status", True),
    ("gh run watch", True),
    ("gh run watch 12345", True),
    ("gh run watch --exit-status", True),
    ("gh run download", True),
    ("gh run download 12345", True),
    ("gh run download 12345 --name artifact-name", True),
    ("gh run download 12345 --dir ./artifacts", True),
    ("gh -R owner/repo run list", True),
    # gh run - unsafe (mutations)
    ("gh run cancel 12345", False),
    ("gh run delete 12345", False),
    ("gh run rerun 12345", False),
    ("gh run rerun 12345 --failed", False),
    ("gh run rerun 12345 --job job-id", False),
    #
    # --- gh workflow ---
    # gh workflow - safe (read-only)
    ("gh workflow list", True),
    ("gh workflow list --all", True),
    ("gh workflow list --limit 50", True),
    ("gh workflow list --json name,state", True),
    ("gh workflow view", True),
    ("gh workflow view build.yml", True),
    ("gh workflow view 12345", True),
    ("gh workflow view --yaml", True),
    ("gh workflow view --ref main", True),
    ("gh workflow view --web", True),
    ("gh -R owner/repo workflow list", True),
    # gh workflow - unsafe (mutations)
    ("gh workflow run build.yml", False),
    ("gh workflow run build.yml --ref main", False),
    ("gh workflow run build.yml -f param=value", False),
    ("gh workflow enable build.yml", False),
    ("gh workflow disable build.yml", False),
    #
    # --- gh release ---
    # gh release - safe (read-only)
    ("gh release list", True),
    ("gh release list --limit 30", True),
    ("gh release list -L 10", True),
    ("gh release list --exclude-drafts", True),
    ("gh release list --exclude-pre-releases", True),
    ("gh release view", True),
    ("gh release view v1.0.0", True),
    ("gh release view v1.0.0 --json tagName,body", True),
    ("gh release view --web", True),
    ("gh release download", True),
    ("gh release download v1.0.0", True),
    ("gh release download v1.0.0 --pattern '*.tar.gz'", True),
    ("gh release download v1.0.0 --dir ./downloads", True),
    ("gh release download --skip-existing", True),
    ("gh release verify v1.0.0", True),
    ("gh release verify-asset v1.0.0", True),
    ("gh -R owner/repo release list", True),
    # gh release - unsafe (mutations)
    ("gh release create v1.0.0", False),
    ("gh release create v1.0.0 --title 'Release v1.0.0'", False),
    ("gh release create v1.0.0 --notes 'Release notes'", False),
    ("gh release create v1.0.0 --draft", False),
    ("gh release create v1.0.0 --prerelease", False),
    ("gh release create v1.0.0 ./dist/*", False),
    ("gh release delete v1.0.0", False),
    ("gh release delete v1.0.0 --yes", False),
    ("gh release delete-asset v1.0.0 asset.tar.gz", False),
    ("gh release edit v1.0.0", False),
    ("gh release edit v1.0.0 --title 'New title'", False),
    ("gh release upload v1.0.0 ./dist/*", False),
    #
    # --- gh gist ---
    # gh gist - safe (read-only)
    ("gh gist list", True),
    ("gh gist list --limit 50", True),
    ("gh gist list -L 10", True),
    ("gh gist list --public", True),
    ("gh gist list --secret", True),
    ("gh gist view abc123", True),
    ("gh gist view abc123 --raw", True),
    ("gh gist view abc123 --web", True),
    ("gh gist view abc123 --files", True),
    ("gh gist view abc123 --filename file.txt", True),
    # gh gist - unsafe (mutations)
    ("gh gist create file.txt", False),
    ("gh gist create file.txt --public", False),
    ("gh gist create file.txt --desc 'My gist'", False),
    ("gh gist create --web file.txt", False),
    ("gh gist edit abc123", False),
    ("gh gist edit abc123 --add file.txt", False),
    ("gh gist delete abc123", False),
    ("gh gist clone abc123", False),
    ("gh gist rename abc123 old.txt new.txt", False),
    #
    # --- gh search ---
    # gh search - all safe (read-only)
    ("gh search repos cli", True),
    ("gh search repos cli --owner github", True),
    ("gh search repos --language python", True),
    ("gh search repos --topic cli --limit 50", True),
    ("gh search issues 'bug label:bug'", True),
    ("gh search issues --state open", True),
    ("gh search issues --assignee @me", True),
    ("gh search prs 'fix in:title'", True),
    ("gh search prs --state merged", True),
    ("gh search prs --author @me", True),
    ("gh search commits 'fix bug'", True),
    ("gh search commits --author user", True),
    ("gh search code 'func main'", True),
    ("gh search code 'import os' --language python", True),
    ("gh search code --repo owner/repo 'pattern'", True),
    ("gh search repos --web cli", True),
    #
    # --- gh cache (GitHub Actions caches) ---
    # gh cache - safe (read-only)
    ("gh cache list", True),
    ("gh cache list --limit 100", True),
    ("gh cache list --key npm-", True),
    ("gh cache list --ref refs/heads/main", True),
    ("gh cache list --sort last_accessed_at", True),
    ("gh cache list --order asc", True),
    ("gh cache list --json key,size", True),
    ("gh -R owner/repo cache list", True),
    # gh cache - unsafe (mutations)
    ("gh cache delete 12345", False),
    ("gh cache delete cache-key", False),
    ("gh cache delete --all", False),
    #
    # --- gh secret ---
    # gh secret - safe (read-only)
    ("gh secret list", True),
    ("gh secret list -e production", True),
    ("gh secret list --org myorg", True),
    ("gh secret list -R owner/repo", True),
    ("gh secret list --json name,updatedAt", True),
    # gh secret - unsafe (mutations)
    ("gh secret set MY_SECRET", False),
    ("gh secret set MY_SECRET --body value", False),
    ("gh secret set MY_SECRET < file.txt", False),
    ("gh secret delete MY_SECRET", False),
    ("gh secret delete MY_SECRET --org myorg", False),
    #
    # --- gh variable ---
    # gh variable - safe (read-only)
    ("gh variable list", True),
    ("gh variable list -e production", True),
    ("gh variable list --org myorg", True),
    ("gh variable list --json name,value", True),
    ("gh variable get MY_VAR", True),
    ("gh variable get MY_VAR -e production", True),
    # gh variable - unsafe (mutations)
    ("gh variable set MY_VAR", False),
    ("gh variable set MY_VAR --body value", False),
    ("gh variable delete MY_VAR", False),
    #
    # --- gh label ---
    # gh label - safe (read-only)
    ("gh label list", True),
    ("gh label list --limit 100", True),
    ("gh label list --json name,color", True),
    ("gh label list --search bug", True),
    ("gh label list --web", True),
    ("gh -R owner/repo label list", True),
    # gh label - unsafe (mutations)
    ("gh label create bug", False),
    ("gh label create bug --color ff0000", False),
    ("gh label create bug --description 'Bug report'", False),
    ("gh label edit bug", False),
    ("gh label edit bug --name bugfix", False),
    ("gh label delete bug", False),
    ("gh label delete bug --yes", False),
    ("gh label clone owner/other-repo", False),
    #
    # --- gh auth ---
    # gh auth - safe (read-only)
    ("gh auth status", True),
    ("gh auth status --hostname github.com", True),
    ("gh auth token", True),
    ("gh auth token --hostname github.com", True),
    # gh auth - unsafe (mutations)
    ("gh auth login", False),
    ("gh auth login --web", False),
    ("gh auth login --with-token", False),
    ("gh auth login --hostname github.enterprise.com", False),
    ("gh auth logout", False),
    ("gh auth refresh", False),
    ("gh auth refresh --scopes repo", False),
    ("gh auth setup-git", False),
    ("gh auth switch", False),
    #
    # --- gh config ---
    # gh config - safe (read-only)
    ("gh config get git_protocol", True),
    ("gh config get editor", True),
    ("gh config list", True),
    ("gh config list --host github.com", True),
    # gh config - unsafe (mutations)
    ("gh config set git_protocol ssh", False),
    ("gh config set editor vim", False),
    ("gh config set prompt disabled", False),
    ("gh config clear-cache", False),
    #
    # --- gh codespace ---
    # gh codespace - safe (read-only)
    ("gh codespace list", True),
    ("gh codespace list --limit 50", True),
    ("gh codespace list --json name,state", True),
    ("gh codespace view", True),
    ("gh codespace view --json name,state", True),
    ("gh codespace logs", True),
    ("gh codespace logs -c codespace-name", True),
    ("gh codespace ports", True),
    ("gh codespace ports -c codespace-name", True),
    ("gh cs list", True),  # alias
    ("gh cs view", True),
    # gh codespace - unsafe (mutations)
    ("gh codespace create", False),
    ("gh codespace create --repo owner/repo", False),
    ("gh codespace delete", False),
    ("gh codespace delete -c codespace-name", False),
    ("gh codespace delete --all", False),
    ("gh codespace stop", False),
    ("gh codespace stop -c codespace-name", False),
    ("gh codespace edit", False),
    ("gh codespace ssh", False),
    ("gh codespace ssh -c codespace-name", False),
    ("gh codespace code", False),
    ("gh codespace code -c codespace-name", False),
    ("gh codespace cp file.txt remote:", False),
    ("gh codespace jupyter", False),
    ("gh codespace rebuild", False),
    ("gh cs create", False),
    ("gh cs delete", False),
    #
    # --- gh extension ---
    # gh extension - safe (read-only)
    ("gh extension list", True),
    ("gh extension search cli", True),
    ("gh extension search --limit 50", True),
    ("gh ext list", True),  # alias
    # gh extension - unsafe (mutations)
    ("gh extension install owner/gh-ext", False),
    ("gh extension upgrade ext-name", False),
    ("gh extension upgrade --all", False),
    ("gh extension remove ext-name", False),
    ("gh extension create ext-name", False),
    ("gh extension exec ext-name", False),
    ("gh extension browse", False),
    ("gh ext install owner/gh-ext", False),
    #
    # --- gh alias ---
    # gh alias - safe (read-only)
    ("gh alias list", True),
    # gh alias - unsafe (mutations)
    ("gh alias set co 'pr checkout'", False),
    ("gh alias delete co", False),
    ("gh alias import aliases.yml", False),
    #
    # --- gh ssh-key ---
    # gh ssh-key - safe (read-only)
    ("gh ssh-key list", True),
    ("gh ssh-key list --json key,title", True),
    # gh ssh-key - unsafe (mutations)
    ("gh ssh-key add ~/.ssh/id_rsa.pub", False),
    ("gh ssh-key add ~/.ssh/id_rsa.pub --title 'My key'", False),
    ("gh ssh-key delete 12345", False),
    #
    # --- gh gpg-key ---
    # gh gpg-key - safe (read-only)
    ("gh gpg-key list", True),
    # gh gpg-key - unsafe (mutations)
    ("gh gpg-key add key.pub", False),
    ("gh gpg-key delete 12345", False),
    #
    # --- gh project ---
    # gh project - safe (read-only)
    ("gh project list", True),
    ("gh project list --owner myorg", True),
    ("gh project list --limit 50", True),
    ("gh project list --json title,number", True),
    ("gh project view 1", True),
    ("gh project view 1 --owner myorg", True),
    ("gh project view 1 --web", True),
    ("gh project field-list 1", True),
    ("gh project field-list 1 --owner myorg", True),
    ("gh project item-list 1", True),
    ("gh project item-list 1 --owner myorg", True),
    ("gh project item-list 1 --limit 100", True),
    # gh project - unsafe (mutations)
    ("gh project create", False),
    ("gh project create --title 'My Project'", False),
    ("gh project delete 1", False),
    ("gh project edit 1", False),
    ("gh project edit 1 --title 'New Title'", False),
    ("gh project close 1", False),
    ("gh project copy 1", False),
    ("gh project link 1", False),
    ("gh project unlink 1", False),
    ("gh project item-add 1 --url issue-url", False),
    ("gh project item-create 1", False),
    ("gh project item-delete 1 --id item-id", False),
    ("gh project item-edit --id item-id", False),
    ("gh project item-archive 1 --id item-id", False),
    ("gh project field-create 1", False),
    ("gh project field-delete 1 --id field-id", False),
    ("gh project mark-template 1", False),
    #
    # --- gh org ---
    # gh org - safe (read-only)
    ("gh org list", True),
    ("gh org list --limit 50", True),
    #
    # --- gh ruleset ---
    # gh ruleset - safe (read-only)
    ("gh ruleset list", True),
    ("gh ruleset list --org myorg", True),
    ("gh ruleset list --limit 50", True),
    ("gh ruleset view 1", True),
    ("gh ruleset view 1 --web", True),
    ("gh ruleset check branch-name", True),
    ("gh rs list", True),  # alias
    ("gh rs view 1", True),
    #
    # --- gh attestation ---
    # gh attestation - safe (read-only/verification)
    ("gh attestation verify artifact.tar.gz", True),
    ("gh attestation verify artifact.tar.gz --owner myorg", True),
    ("gh attestation download artifact.tar.gz", True),
    ("gh attestation trusted-root", True),
    ("gh at verify artifact.tar.gz", True),  # alias
    #
    # --- gh status ---
    # gh status - safe (read-only)
    ("gh status", True),
    ("gh status --org myorg", True),
    ("gh status --exclude owner/repo", True),
    ("gh status -e owner/repo1 -e owner/repo2", True),
    #
    # --- gh browse ---
    # gh browse - safe (opens browser, no mutations)
    ("gh browse", True),
    ("gh browse 123", True),
    ("gh browse --projects", True),
    ("gh browse --releases", True),
    ("gh browse --settings", True),
    ("gh browse --wiki", True),
    ("gh browse --branch main", True),
    ("gh browse src/main.go", True),
    ("gh browse src/main.go:42", True),
    ("gh browse --no-browser", True),
    ("gh browse -n", True),
    ("gh -R owner/repo browse", True),
    #
    # --- gh api ---
    # gh api - safe (GET requests)
    ("gh api repos/owner/repo", True),
    ("gh api repos/{owner}/{repo}/pulls", True),
    ("gh api /user", True),
    ("gh api -X GET repos/owner/repo", True),
    ("gh api --method GET repos/owner/repo", True),
    ("gh api --method=GET repos/owner/repo", True),
    ("gh api -XGET repos/owner/repo", True),
    (
        "gh api -X GET search/issues -f q='repo:cli/cli'",
        True,
    ),  # -f ok with explicit GET
    (
        "gh api -f q='repo:cli/cli' -X GET search/issues",
        True,
    ),  # -X GET after -f is still safe
    ("gh api --paginate repos/owner/repo/issues", True),
    ("gh api -q '.[] | .name' repos/owner/repo", True),
    ("gh api graphql -f query='query { viewer { login } }'", True),  # read-only query
    # gh api - unsafe (mutations)
    ("gh api repos/owner/repo --raw-field=foo=bar", False),  # --flag=value form
    ("gh api repos/owner/repo --field=foo=bar", False),
    ("gh api repos/owner/repo/issues -f title='bug'", False),  # -f implies POST
    ("gh api repos/owner/repo/issues -F body=@file.txt", False),  # -F implies POST
    ("gh api repos/owner/repo/issues --field title=bug", False),
    ("gh api -X POST repos/owner/repo/issues", False),
    ("gh api -X DELETE repos/owner/repo/issues/1", False),
    ("gh api --method POST repos/owner/repo/hooks", False),
    ("gh api --method=PATCH repos/owner/repo", False),
    ("gh api -XPOST repos/owner/repo/issues", False),
    ("gh api repos/owner/repo --input payload.json", False),
    ("gh api graphql -f query='mutation { ... }'", False),
    #
    # --- gh help/version flags ---
    ("gh --help", True),
    ("gh -h", True),
    ("gh --version", True),
    ("gh pr --help", True),
    ("gh issue --help", True),
    ("gh repo --help", True),
    ("gh api --help", True),
    ("gh api repos --help", True),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
