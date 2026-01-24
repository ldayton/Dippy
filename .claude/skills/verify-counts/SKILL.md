---
name: verify-counts
description: Verify numerical claims in documentation are still accurate
---

Verify all count assertions in documentation against actual values.

## Claims to Verify

| Location | Claim | Verification |
|----------|-------|--------------|
| `README.md:14` | 14,000+ tests | Dippy + Parable combined |
| `../Dippy.wiki/Reference/Security-Model.md:79` | Over 200 read-only commands | SIMPLE_SAFE count |
| `../Dippy.wiki/Reference/Security-Model.md:94` | Over 45 tools | CLI handler count |
| `../Dippy.wiki/Reference/Handler-Model.md:210` | 50+ handlers | CLI handler count |

## Verification Commands

**Dippy tests:**
```bash
uv run pytest --collect-only -q 2>/dev/null | tail -1
```

**Parable tests:** Check table in `/Users/lily/source/Parable/tests/README.md`

**SIMPLE_SAFE count:**
```bash
uv run python -c "from src.dippy.core.allowlists import SIMPLE_SAFE; print(len(SIMPLE_SAFE))"
```

**CLI handlers:**
```bash
ls -1 src/dippy/cli/*.py | grep -v __init__ | wc -l
```

## Output

Report each claim with:
- Documented value
- Actual value
- Status (PASS/FAIL/STALE)

### Status Criteria

- **PASS**: Actual value is within ~10% of documented value
- **STALE**: Claim is technically true but significantly outdated (e.g., "50+" when actual is 77)
- **FAIL**: Claim is false

If any claim is STALE or FAIL, note which file(s) need updating.
