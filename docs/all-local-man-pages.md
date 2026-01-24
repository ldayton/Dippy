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
| mktemp           | ask        | mac | Always creates files/directories          |
| dirname          | done       | mac | Already in SIMPLE_SAFE                    |
| basename         | done       | mac | Already in SIMPLE_SAFE                    |
| logger           | ask        | mac | Always writes to system log               |
| uuidgen          | done       | mac | Already in SIMPLE_SAFE                    |
| csplit           | ask        | mac | Always creates output files               |
| tabs             | done       | mac | Already in SIMPLE_SAFE                    |
| locale           | done       | mac | Already in SIMPLE_SAFE                    |
| plutil           | done       | mac | Has handler (flag-check: -convert writes) |
| defaults         | subcommand | mac | read safe, write/delete unsafe            |
| pbcopy           | ask        | mac | Always modifies clipboard                 |
| pbpaste          | done       | mac | Already in SIMPLE_SAFE                    |
| open             | done       | mac | Has handler (flag-check: -R safe)         |
| sw_vers          | done       | mac | Already in SIMPLE_SAFE                    |
| xxd              | done       | mac | Has handler (flag-check: -r writes)       |
| lipo             | done       | mac | Has handler (flag-check: -create writes)  |
| pstree           | n/a        | mac | Not available on macOS                    |
| osascript        | ask        | mac | Executes arbitrary scripts                |
| textutil         | done       | mac | Has handler (flag-check: -convert writes) |
| dscl             | subcommand | mac | read/list safe, create/delete unsafe      |
| scutil           | subcommand | mac | --get safe, --set unsafe                  |
| ditto            | ask        | mac | Always copies/archives                    |
| getconf          | done       | mac | Already in SIMPLE_SAFE                    |
| afplay           | done       | mac | Already in SIMPLE_SAFE                    |
| fmt              | done       | mac | Already in SIMPLE_SAFE                    |
| xattr            | done       | mac | Has handler (flag-check: -w/-d/-c modify) |
| rev              | done       | mac | Already in SIMPLE_SAFE                    |
| tac              | done       | mac | Already in SIMPLE_SAFE                    |
| codesign         | done       | mac | Has handler (flag-check: -s signs)        |
| spctl            | subcommand | mac | --assess safe, --enable/--add unsafe      |
| caffeinate       | done       | mac | Has handler (delegate)                    |
| sqlite3          | subcommand | mac | Query safe, .dump/.import varies          |
| qlmanage         | done       | mac | Has handler (flag-check: -r resets)       |
| mdimport         | ask        | mac | Always imports to Spotlight               |
| diskutil         | subcommand | mac | list/info safe, mount/erase unsafe        |
| hdiutil          | subcommand | mac | info/verify safe, create/attach unsafe    |
| sips             | done       | mac | Has handler (flag-check: -s/-o modify)    |
| networksetup     | subcommand | mac | -get* safe, -set* unsafe                  |
| ifconfig         | done       | mac | Has handler (arg-count)                   |
| openssl          | done       | mac | Has handler (subcommand)                  |
| otool            | done       | mac | Already in SIMPLE_SAFE                    |
| launchctl        | subcommand | mac | list/print safe, load/start unsafe        |
| security         | subcommand | mac | find-* safe, add-*/delete-* unsafe        |
| tmutil           | subcommand | mac | listbackups safe, restore unsafe          |
| osacompile       | ask        | mac | Always creates output files               |
| pkgutil          | done       | mac | Has handler (subcommand: --forget unsafe) |
| lsbom            | done       | mac | Already in SIMPLE_SAFE                    |
| fuser            | done       | mac | Already in SIMPLE_SAFE                    |
| bc               | done       | mac | Already in SIMPLE_SAFE                    |
| asr              | ask        | mac | Always restores/copies                    |
| sysctl           | arg-count  | mac | name reads, name=value writes             |
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
