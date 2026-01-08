"""Test cases for xargs."""

import pytest

from conftest import is_approved, needs_confirmation

#
# ==========================================================================
# xargs
# ==========================================================================
#
TESTS = [
    ("xargs ls", True),
    ("xargs cat", True),
    ("xargs grep pattern", True),
    ("xargs rg -l pattern", True),
    ("xargs head -5", True),
    ("xargs tail -n 10", True),
    ("xargs wc -l", True),
    ("xargs file", True),
    ("xargs stat", True),
    ("xargs md5sum", True),
    ("xargs sha256sum", True),
    ("xargs du -sh", True),
    ("xargs ls -la", True),
    ("xargs diff", True),
    ("xargs basename", True),
    ("xargs dirname", True),
    ("xargs realpath", True),
    ("xargs readlink", True),
    # xargs with pipeline input (safe)
    ("find . -name '*.py' | xargs grep TODO", True),
    ("fd -t f | xargs head -5", True),
    ("ls | xargs -I {} stat {}", True),
    ("git ls-files | xargs wc -l", True),
    ("git ls-files '*.conf' | xargs cat", True),
    ("echo 'file.txt' | xargs cat", True),
    # xargs with -0/--null (null-terminated input)
    ("xargs -0 cat", True),
    ("xargs --null cat", True),
    ("find . -print0 | xargs -0 grep pattern", True),
    ("find . -print0 | xargs --null wc -l", True),
    ("git ls-files -z | xargs -0 head -1", True),
    # xargs with -I/--replace (replacement string)
    ("xargs -I {} cat {}", True),
    ("xargs -i cat {}", True),
    ("xargs --replace={} cat {}", True),
    ("xargs -I FILE head FILE", True),
    ("xargs -I % grep pattern %", True),
    ("xargs -I {} -P 4 head -10 {}", True),
    ("xargs -I{} cat {}", True),  # no space after -I
    # xargs with -n/--max-args (items per command)
    ("xargs -n 1 ls", True),
    ("xargs -n 5 cat", True),
    ("xargs --max-args=10 grep pattern", True),
    ("xargs -n1 head", True),  # no space after -n
    # xargs with -P/--max-procs (parallel execution)
    ("xargs -P 4 grep pattern", True),
    ("xargs --max-procs=8 cat", True),
    ("xargs -P4 wc -l", True),  # no space after -P
    ("xargs -P 0 head -5", True),  # 0 means as many as possible
    # xargs with -L/--max-lines (lines per command)
    ("xargs -L 1 head", True),
    ("xargs --max-lines=5 cat", True),
    ("xargs -L1 grep pattern", True),
    # xargs with -d/--delimiter
    ("xargs -d '\\n' cat", True),
    ("xargs --delimiter='\\n' cat", True),
    ("xargs -d ',' wc -l", True),
    ("xargs --delimiter=: head", True),
    # xargs with -a/--arg-file
    ("xargs -a files.txt cat", True),
    ("xargs --arg-file=list.txt head", True),
    ("xargs -a /dev/stdin grep pattern", True),
    # xargs with -E/--eof (end of file string)
    ("xargs -E EOF cat", True),
    ("xargs -e STOP head", True),
    ("xargs --eof=END wc -l", True),
    # xargs with -s/--max-chars (max command line length)
    ("xargs -s 1024 cat", True),
    ("xargs --max-chars=2048 grep pattern", True),
    # xargs with --process-slot-var
    ("xargs --process-slot-var=SLOT cat", True),
    # xargs BSD-specific flags
    ("xargs -J % cp -Rp % destdir", False),  # cp is unsafe
    ("xargs -J % cat %", True),
    ("xargs -I {} -R 5 cat {}", True),  # -R limits replacements
    ("xargs -I {} -S 255 cat {}", True),  # -S limits replacement size
    ("xargs -I {} -R 5 -S 255 head {}", True),
    # xargs with multiple flags combined
    ("xargs -0 -n 1 -P 4 cat", True),
    ("xargs --null --max-args=1 --max-procs=4 grep pattern", True),
    ("xargs -I {} -P 4 -n 1 head {}", True),
    ("xargs -0 -I {} -P 8 cat {}", True),
    ("xargs -d '\\n' -n 5 -P 2 wc -l", True),
    ("xargs -a files.txt -0 -n 1 cat", True),
    # xargs with -- (end of flags)
    ("xargs -- cat", True),
    ("xargs -0 -- rg pattern", True),
    ("xargs -0 -I {} -- cat {}", True),
    ("xargs -P 4 -n 1 -- grep pattern", True),
    ("xargs -I {} -- head -5 {}", True),
    # xargs with safe git commands
    ("xargs git status", True),
    ("xargs git log --oneline", True),
    ("xargs git diff", True),
    ("xargs git show", True),
    ("git ls-files | xargs git blame", True),
    # xargs with safe aws commands
    ("xargs aws s3 ls", True),
    ("xargs aws ec2 describe-instances", True),
    # xargs with safe kubectl commands
    ("xargs kubectl get pods", True),
    ("xargs kubectl describe pod", True),
    # xargs - unsafe (inner command is unsafe)
    ("xargs rm", False),
    ("xargs rm -rf", False),
    ("xargs rm -f", False),
    ("xargs unlink", False),
    ("xargs mv", False),
    ("xargs cp", False),
    ("xargs chmod 777", False),
    ("xargs chown root", False),
    ("xargs chgrp wheel", False),
    ("xargs ln -s", False),
    ("xargs mkdir", False),
    ("xargs rmdir", False),
    ("xargs touch", False),
    ("xargs truncate -s 0", False),
    ("xargs shred", False),
    ("xargs dd", False),
    # xargs with pipeline (unsafe inner command)
    ("find . | xargs rm", False),
    ("ls | xargs rm -f", False),
    ("git ls-files | xargs rm", False),
    # xargs with flags but unsafe inner command
    ("xargs -0 rm", False),
    ("xargs --null rm -rf", False),
    ("xargs -I {} rm {}", False),
    ("xargs -n 1 rm", False),
    ("xargs -P 4 rm", False),
    ("xargs -L 1 rm", False),
    ("xargs -d '\\n' rm", False),
    ("xargs -a files.txt rm", False),
    ("xargs -- rm", False),
    ("xargs -0 -n 1 -P 4 rm", False),
    # xargs with unsafe git commands
    ("xargs git push", False),
    ("xargs git add", False),
    ("xargs git commit", False),
    ("xargs git reset --hard", False),
    ("xargs git checkout", False),
    ("git ls-files | xargs git rm", False),
    # xargs with unsafe aws commands
    ("xargs aws s3 rm", False),
    ("xargs aws ec2 terminate-instances", False),
    # xargs with unsafe kubectl commands
    ("xargs kubectl delete", False),
    ("xargs kubectl apply", False),
    # xargs - no command (must defer, can't approve)
    ("xargs", False),
    ("xargs -0", False),
    ("xargs -I {}", False),
    ("xargs -n 1", False),
    ("xargs -P 4", False),
    ("xargs --null", False),
    ("xargs -0 -n 1 -P 4", False),
    ("xargs --", False),
    ("xargs -0 --", False),
    # xargs with shell -c (delegates to check_shell_c)
    ("xargs -I {} sh -c 'echo {}'", True),
    ("xargs -I {} bash -c 'cat {}'", True),
    ("xargs -I {} zsh -c 'head {}'", True),
    ("xargs sh -c 'echo hello'", True),
    ("xargs bash -c 'git status'", True),
    ("xargs -0 sh -c 'cat'", True),
    ("xargs -I {} sh -c 'rm {}'", False),
    ("xargs -I {} bash -c 'echo {} && rm {}'", False),
    ("xargs sh -c 'rm foo'", False),
    ("xargs bash -c 'git push'", False),
    # xargs with env wrapper
    ("xargs env cat", True),
    ("xargs env FOO=bar cat", True),
    ("xargs env rm", False),
    # xargs with time wrapper
    ("xargs time cat", True),
    ("xargs time rm", False),
    # xargs edge cases - flags that look like commands
    ("xargs -r cat", True),  # -r is --no-run-if-empty
    ("xargs --no-run-if-empty cat", True),
    ("xargs -t cat", True),  # -t is --verbose
    ("xargs --verbose cat", True),
    ("xargs -p cat", False),  # -p is --interactive, prompts user
    ("xargs --interactive cat", False),
    ("xargs -o cat", False),  # -o is --open-tty, allows interactive input
    ("xargs --open-tty cat", False),
    ("xargs -x cat", True),  # -x is --exit
    ("xargs --exit cat", True),
    ("xargs -r -t cat", True),
    ("xargs -rt cat", True),  # combined short flags
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_xargs(check, command: str, expected: bool) -> None:
    """Test command safety."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
