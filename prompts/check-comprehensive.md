# Check Comprehensive CLI Handler Coverage

Given a CLI tool name, ensure its handler and tests provide comprehensive coverage.

## Input

Tool name (e.g., `brew`, `git`, `aws`)

## Workflow

### 1. Gather Documentation

First, find documentation for the tool. You need at least one source to proceed:

**Check tldr:**
```bash
ls ~/source/tldr/pages/*/<tool>*.md
cat ~/source/tldr/pages/*/<tool>.md
```

**Check local CLI docs:**
```bash
<tool> --help
<tool> -h
man <tool>
```

**Stop if neither source exists.** The tool must be installed locally and/or documented in tldr.

### 2. Explore Subcommands Recursively

For tools with subcommands, recursively explore:

```bash
<tool> <subcommand> --help
<tool> help <subcommand>
```

Build a mental model of:
- All subcommands and their actions
- Which operations are read-only (safe)
- Which operations mutate state (unsafe)
- Global flags that affect parsing
- Edge cases (flags that look safe but aren't, or vice versa)

### 3. Review Existing Tests

Read the test file:
```
tests/cli/test_<tool>.py
```

Check for:
- Coverage of all subcommands
- Both safe and unsafe variants of each action
- Global flag handling
- Edge cases from the docs
- Common real-world usage patterns

### 4. Add Missing Tests (Aspirational)

Add test cases for anything missing. These tests are **aspirational** - they define the desired behavior and will likely fail initially.

Follow the existing test format:
```python
TESTS = [
    # --- Subcommand group ---
    ("<tool> <subcommand> <safe-action>", True),
    ("<tool> <subcommand> <unsafe-action>", False),
    ...
]
```

Group tests logically with comments. Include:
- Every subcommand discovered
- Safe and unsafe variants
- Flag combinations
- Edge cases noted in docs

### 5. Iterate Until Tests Pass

Run the tests:
```bash
just test
```

For each failure:
1. Determine if the test expectation is correct
2. If yes, update the handler in `src/dippy/cli/<tool>.py`
3. If no, fix the test

Repeat until all tests pass.

### 6. Verify Full Suite

Run all Python versions before committing:
```bash
just test-all
```

## Output

- Updated `tests/cli/test_<tool>.py` with comprehensive coverage
- Updated `src/dippy/cli/<tool>.py` handler if needed
- All tests passing

## Example

For `brew`:

1. Check `~/source/tldr/pages/common/brew.md` and `brew --help`
2. Discover subcommands: `install`, `uninstall`, `upgrade`, `list`, `search`, `info`, `update`, `cleanup`, `doctor`, `tap`, `untap`, `services`, `bundle`, etc.
3. For each, check `brew <cmd> --help` to find actions
4. Review `tests/cli/test_brew.py` for gaps
5. Add missing cases (e.g., `brew services list` vs `brew services start`)
6. Run tests, fix handler, repeat
