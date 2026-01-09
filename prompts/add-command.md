Add support for the '$COMMAND' CLI command following the process in prompts/adding-commands.md.
$HANDLER_LINE

Reference materials:
- tldr pages are at ~/tldr/pages/common/, ~/tldr/pages/linux/, ~/tldr/pages/osx/
- Man pages: run `man $COMMAND` or `man $COMMAND-<subcommand>`
- Help: run `$COMMAND --help`

Steps:
1. Read the tldr page and man page to understand safe vs unsafe operations
2. Determine the right approach:
   - If ALWAYS safe (read-only, no destructive flags): add to SIMPLE_SAFE in src/dippy/core/patterns.py
   - If safety depends on subcommands/flags: create a handler in src/dippy/cli/$COMMAND.py
3. Create tests in tests/cli/test_$COMMAND.py (even for SIMPLE_SAFE additions)
4. Run `just test` and fix issues until tests pass

When tests pass:
5. Run `just lint --fix`
6. Run `just fmt --fix`

IMPORTANT: `just check` MUST PASS before you are done.

RESTRICTIONS:
- ONLY modify files directly related to $COMMAND
- For SIMPLE_SAFE: only touch src/dippy/core/patterns.py and tests/cli/test_$COMMAND.py
- For handlers: only touch src/dippy/cli/$COMMAND.py and tests/cli/test_$COMMAND.py
- Do NOT refactor, rename, or "improve" existing code
- Do NOT modify other handlers or test files
- Do NOT touch src/dippy/dippy.py, src/dippy/cli/__init__.py, or core files unless absolutely necessary

Do not create a git commit or PR.
