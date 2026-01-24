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
| banner           | safe       | mac | Prints ASCII art to stdout                |
| apropos          | safe       | mac | Searches man page database                |
| whatis           | safe       | mac | Searches man page database                |
| arch             | delegate   | mac | With args runs programs                   |
| getopt           | safe       | mac | Parses command options, pure output       |
| logname          | done       | mac | Already in SIMPLE_SAFE                    |
| ioreg            | done       | mac | Already in SIMPLE_SAFE                    |
| say              | flag-check | mac | -o writes audio files                     |
| getopts          | safe       | mac | Shell builtin for option parsing          |
| printenv         | done       | mac | Already in SIMPLE_SAFE                    |
| yes              | safe       | mac | Outputs text forever, pure output         |
| pathchk          | safe       | mac | Checks pathname validity                  |
| nohup            | done       | mac | Already in WRAPPER_COMMANDS               |
| env              | done       | mac | Has handler (delegate)                    |
| xargs            | done       | mac | Has handler (delegate)                    |
| test             | safe       | mac | Evaluates conditions, exit status only    |
| [                | n/a        | mac | Handled as AST visitation                 |
| mktemp           | ask        | mac | Always creates files/directories          |
| dirname          | done       | mac | Already in SIMPLE_SAFE                    |
| basename         | done       | mac | Already in SIMPLE_SAFE                    |
| logger           | ask        | mac | Always writes to system log               |
| uuidgen          | safe       | mac | Generates UUIDs, pure output              |
| csplit           | ask        | mac | Always creates output files               |
| tabs             | safe       | mac | Sets terminal tab stops                   |
| locale           | done       | mac | Already in SIMPLE_SAFE                    |
| plutil           | flag-check | mac | -convert/-o writes, -p prints             |
| defaults         | subcommand | mac | read safe, write/delete unsafe            |
| pbcopy           | ask        | mac | Always modifies clipboard                 |
| pbpaste          | safe       | mac | Reads clipboard to stdout                 |
| open             | delegate   | mac | Launches applications/URLs                |
| sw_vers          | done       | mac | Already in SIMPLE_SAFE                    |
| xxd              | done       | mac | Has handler (flag-check: -r writes)       |
| lipo             | flag-check | mac | -create/-output writes, -info/-archs safe |
| pstree           | n/a        | mac | Not available on macOS                    |
| osascript        | ask        | mac | Executes arbitrary scripts                |
| textutil         | flag-check | mac | -convert -output writes                   |
| dscl             | subcommand | mac | read/list safe, create/delete unsafe      |
| scutil           | subcommand | mac | --get safe, --set unsafe                  |
| ditto            | ask        | mac | Always copies/archives                    |
| getconf          | done       | mac | Already in SIMPLE_SAFE                    |
| afplay           | safe       | mac | Plays audio to default output             |
| fmt              | done       | mac | Already in SIMPLE_SAFE                    |
| xattr            | flag-check | mac | -p/-l safe, -w/-d/-c modify               |
| rev              | done       | mac | Already in SIMPLE_SAFE                    |
| tac              | done       | mac | Already in SIMPLE_SAFE                    |
| codesign         | flag-check | mac | -d/-v safe, -s signs                      |
| spctl            | subcommand | mac | --assess safe, --enable/--add unsafe      |
| caffeinate       | delegate   | mac | Can run utilities with args               |
| sqlite3          | subcommand | mac | Query safe, .dump/.import varies          |
| qlmanage         | flag-check | mac | -p previews, -r resets server             |
| mdimport         | ask        | mac | Always imports to Spotlight               |
| diskutil         | subcommand | mac | list/info safe, mount/erase unsafe        |
| hdiutil          | subcommand | mac | info/verify safe, create/attach unsafe    |
| sips             | flag-check | mac | -g safe, -s/-o modify                     |
| networksetup     | subcommand | mac | -get* safe, -set* unsafe                  |
| ifconfig         | done       | mac | Has handler (arg-count)                   |
| openssl          | done       | mac | Has handler (subcommand)                  |
| otool            | done       | mac | Already in SIMPLE_SAFE                    |
| launchctl        | subcommand | mac | list/print safe, load/start unsafe        |
| security         | subcommand | mac | find-* safe, add-*/delete-* unsafe        |
| tmutil           | subcommand | mac | listbackups safe, restore unsafe          |
| osacompile       | ask        | mac | Always creates output files               |
| pkgutil          | flag-check | mac | --pkgs/--files safe, --learn modifies     |
| lsbom            | safe       | mac | Lists BOM contents                        |
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
| ncal             | safe       | mac | Calendar display                          |
| look             | done       | mac | Already in SIMPLE_SAFE                    |
| rs               | done       | mac | Already in SIMPLE_SAFE                    |
| vis              | done       | mac | Already in SIMPLE_SAFE                    |
| dwarfdump        | done       | mac | Already in SIMPLE_SAFE                    |
| nm               | done       | mac | Already in SIMPLE_SAFE                    |
| strings          | done       | mac | Already in SIMPLE_SAFE                    |
| unvis            | done       | mac | Already in SIMPLE_SAFE                    |
| colrm            | done       | mac | Already in SIMPLE_SAFE                    |
| size             | done       | mac | Already in SIMPLE_SAFE                    |
| osalang          | safe       | mac | Prints OSA language info                  |
| compression_tool | flag-check | mac | -encode/-decode with output               |
| leaks            | done       | mac | Already in SIMPLE_SAFE                    |
| heap             | done       | mac | Already in SIMPLE_SAFE                    |
| atos             | done       | mac | Already in SIMPLE_SAFE                    |
| hexdump          | done       | mac | Already in SIMPLE_SAFE                    |
| binhex           | flag-check | mac | Encode/decode with output files           |
| sample           | done       | mac | Has handler (flag-check: -file writes)    |
| vmmap            | done       | mac | Already in SIMPLE_SAFE                    |
| symbols          | flag-check | mac | -saveSignature writes                     |
| pagestuff        | safe       | mac | Mach-O page analysis                      |
| machine          | done       | mac | Already in SIMPLE_SAFE                    |
| awk              | done       | mac | Has handler (flag-check: > redirections)  |
| sed              | done       | mac | Has handler (flag-check: -i modifies)     |
| od               | done       | mac | Already in SIMPLE_SAFE                    |
