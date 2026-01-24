# Local Man Page Command Classification

Grouping commands into handler-style families.

Families:
- **safe**: No handler needed, SIMPLE_SAFE material
- **done**: Already handled (SIMPLE_SAFE, WRAPPER_COMMANDS, or has handler)
- **n/a**: Not applicable
- **delegate**: Wraps/executes other commands, extract inner command
- **subcommand**: Multi-level CLI, check subcommand against safe/unsafe lists
- **flag-check**: Safe by default, specific flags make it unsafe
- **arg-count**: Safety depends on argument count
- **ask**: Always requires confirmation, no safe mode

| Command          | Family     | OS  | Notes                                     |
| ---------------- | ---------- | --- | ----------------------------------------- |
| banner           | done       | mac | Already in SIMPLE_SAFE                    |
| apropos          | done       | mac | Already in SIMPLE_SAFE                    |
| whatis           | done       | mac | Already in SIMPLE_SAFE                    |
| arch             | done       | mac | Has handler (delegate)                    |
| getopt           | done       | mac | Already in SIMPLE_SAFE                    |
| logname          | done       | mac | Already in SIMPLE_SAFE                    |
| ioreg            | done       | mac | Already in SIMPLE_SAFE                    |
| say              | done       | mac | Has handler (flag-check: -o writes)       |
| getopts          | done       | mac | Already in SIMPLE_SAFE                    |
| printenv         | done       | mac | Already in SIMPLE_SAFE                    |
| yes              | done       | mac | Already in SIMPLE_SAFE                    |
| pathchk          | done       | mac | Already in SIMPLE_SAFE                    |
| nohup            | done       | mac | Already in WRAPPER_COMMANDS               |
| env              | done       | mac | Has handler (delegate)                    |
| xargs            | done       | mac | Has handler (delegate)                    |
| test             | done       | mac | Already in SIMPLE_SAFE                    |
| [                | n/a        | mac | Handled as AST visitation                 |
| mktemp           | done       | mac | Has handler (flag-check: -u dry run)      |
| dirname          | done       | mac | Already in SIMPLE_SAFE                    |
| basename         | done       | mac | Already in SIMPLE_SAFE                    |
| logger           | done       | mac | Defaults to ask (writes to system log)    |
| uuidgen          | done       | mac | Already in SIMPLE_SAFE                    |
| csplit           | done       | mac | Defaults to ask (creates output files)    |
| tabs             | done       | mac | Already in SIMPLE_SAFE                    |
| locale           | done       | mac | Already in SIMPLE_SAFE                    |
| plutil           | done       | mac | Has handler (flag-check: -convert writes) |
| defaults         | done       | mac | Has handler (subcommand)                  |
| pbcopy           | done       | mac | Defaults to ask (modifies clipboard)      |
| pbpaste          | done       | mac | Already in SIMPLE_SAFE                    |
| open             | done       | mac | Has handler (flag-check: -R safe)         |
| sw_vers          | done       | mac | Already in SIMPLE_SAFE                    |
| xxd              | done       | mac | Has handler (flag-check: -r writes)       |
| lipo             | done       | mac | Has handler (flag-check: -create writes)  |
| pstree           | n/a        | mac | Not available on macOS                    |
| osascript        | done       | mac | Defaults to ask (executes scripts)        |
| textutil         | done       | mac | Has handler (flag-check: -convert writes) |
| dscl             | done       | mac | Has handler (subcommand)                  |
| scutil           | done       | mac | Has handler (subcommand)                  |
| ditto            | done       | mac | Defaults to ask (copies/archives)         |
| getconf          | done       | mac | Already in SIMPLE_SAFE                    |
| afplay           | done       | mac | Already in SIMPLE_SAFE                    |
| fmt              | done       | mac | Already in SIMPLE_SAFE                    |
| xattr            | done       | mac | Has handler (flag-check: -w/-d/-c modify) |
| rev              | done       | mac | Already in SIMPLE_SAFE                    |
| tac              | done       | mac | Already in SIMPLE_SAFE                    |
| codesign         | done       | mac | Has handler (flag-check: -s signs)        |
| spctl            | done       | mac | Has handler (subcommand)                  |
| caffeinate       | done       | mac | Has handler (delegate)                    |
| sqlite3          | subcommand | mac | Query safe, .dump/.import varies          |
| qlmanage         | done       | mac | Has handler (flag-check: -r resets)       |
| mdimport         | done       | mac | Has handler (flag-check: -t/-L/-A/-X)     |
| diskutil         | done       | mac | Has handler (subcommand)                  |
| hdiutil          | done       | mac | Has handler (subcommand)                  |
| sips             | done       | mac | Has handler (flag-check: -s/-o modify)    |
| networksetup     | done       | mac | Has handler (subcommand)                  |
| ifconfig         | done       | mac | Has handler (arg-count)                   |
| openssl          | done       | mac | Has handler (subcommand)                  |
| otool            | done       | mac | Already in SIMPLE_SAFE                    |
| launchctl        | subcommand | mac | list/print safe, load/start unsafe        |
| security         | subcommand | mac | find-* safe, add-*/delete-* unsafe        |
| tmutil           | subcommand | mac | listbackups safe, restore unsafe          |
| osacompile       | done       | mac | Defaults to ask (creates output files)    |
| pkgutil          | done       | mac | Has handler (subcommand: --forget unsafe) |
| lsbom            | done       | mac | Already in SIMPLE_SAFE                    |
| fuser            | done       | mac | Already in SIMPLE_SAFE                    |
| bc               | done       | mac | Already in SIMPLE_SAFE                    |
| asr              | done       | mac | Defaults to ask (restores/copies)         |
| sysctl           | done       | mac | Has handler (arg-count)                   |
| system_profiler  | done       | mac | Already in SIMPLE_SAFE                    |
| mdfind           | done       | mac | Already in SIMPLE_SAFE                    |
| mdls             | done       | mac | Already in SIMPLE_SAFE                    |
| profiles         | subcommand | mac | show safe, remove/renew unsafe            |
| units            | done       | mac | Already in SIMPLE_SAFE                    |
| column           | done       | mac | Already in SIMPLE_SAFE                    |
| cal              | done       | mac | Already in SIMPLE_SAFE                    |
| ncal             | done       | mac | Already in SIMPLE_SAFE                    |
| look             | done       | mac | Already in SIMPLE_SAFE                    |
| rs               | done       | mac | Already in SIMPLE_SAFE                    |
| vis              | done       | mac | Already in SIMPLE_SAFE                    |
| dwarfdump        | done       | mac | Already in SIMPLE_SAFE                    |
| nm               | done       | mac | Already in SIMPLE_SAFE                    |
| strings          | done       | mac | Already in SIMPLE_SAFE                    |
| unvis            | done       | mac | Already in SIMPLE_SAFE                    |
| colrm            | done       | mac | Already in SIMPLE_SAFE                    |
| size             | done       | mac | Already in SIMPLE_SAFE                    |
| osalang          | done       | mac | Already in SIMPLE_SAFE                    |
| compression_tool | done       | mac | Has handler (flag-check: -o writes)       |
| leaks            | done       | mac | Already in SIMPLE_SAFE                    |
| heap             | done       | mac | Already in SIMPLE_SAFE                    |
| atos             | done       | mac | Already in SIMPLE_SAFE                    |
| hexdump          | done       | mac | Already in SIMPLE_SAFE                    |
| binhex           | done       | mac | Has handler (flag-check: encode/decode)   |
| sample           | done       | mac | Has handler (flag-check: -file writes)    |
| vmmap            | done       | mac | Already in SIMPLE_SAFE                    |
| symbols          | done       | mac | Has handler (flag-check: -saveSignature)  |
| pagestuff        | done       | mac | Already in SIMPLE_SAFE                    |
| machine          | done       | mac | Already in SIMPLE_SAFE                    |
| awk              | done       | mac | Has handler (flag-check: > redirections)  |
| sed              | done       | mac | Has handler (flag-check: -i modifies)     |
| od               | done       | mac | Already in SIMPLE_SAFE                    |
