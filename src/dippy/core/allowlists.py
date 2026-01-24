"""
Allowlists for Dippy - known safe commands and transparent wrappers.
"""

from __future__ import annotations

# === Simple Safe Commands ===
# These are always safe regardless of arguments (except output redirects)

SIMPLE_SAFE = frozenset(
    {
        # === File Content Viewing ===
        "cat",  # concatenate and print files
        "head",  # print first lines of file
        "tail",  # print last lines of file
        "less",  # pager for viewing files
        "more",  # pager for viewing files
        "bat",  # cat clone with syntax highlighting
        "tac",  # print file in reverse
        "od",  # octal dump of file
        "hexdump",  # hex dump of file
        "strings",  # print printable strings from binary
        # Compressed file viewers
        "bzcat",  # decompress bz2 to stdout
        "bzmore",  # view bz2 compressed files
        "funzip",  # extract first member of zip to stdout
        "lz4cat",  # decompress lz4 to stdout
        "xzcat",  # decompress xz to stdout
        "xzless",  # view xz compressed files
        "xzmore",  # view xz compressed files
        "zcat",  # decompress gzip to stdout
        "zless",  # view gzip compressed files
        "zmore",  # view gzip compressed files
        "zstdcat",  # decompress zstd to stdout
        "zstdless",  # view zstd compressed files
        # Archive inspection
        "zipinfo",  # list zip archive contents
        # === Binary Analysis ===
        "dwarfdump",  # dump DWARF debug info
        "dyld_info",  # display dyld information
        "ldd",  # print shared library dependencies
        "nm",  # list symbols from object files
        "objdump",  # display object file information
        "otool",  # display Mach-O file information
        "readelf",  # display ELF file information
        "size",  # display section sizes
        # === Directory Listing ===
        "ls",  # list directory contents
        "ll",  # long listing alias
        "la",  # list all alias
        "tree",  # list directory tree
        "exa",  # modern ls replacement
        "eza",  # modern ls replacement
        "dir",  # list directory contents
        "vdir",  # verbose directory listing
        # === File & Disk Information ===
        "stat",  # display file status
        "file",  # determine file type
        "wc",  # word, line, byte count
        "du",  # disk usage of files
        "df",  # disk free space
        # === Path Utilities ===
        "basename",  # strip directory from path
        "dirname",  # strip filename from path
        "pwd",  # print working directory
        "cd",  # change directory
        "readlink",  # resolve symbolic link
        "realpath",  # resolve canonical path
        # === Search & Find ===
        "grep",  # search text patterns
        "rg",  # ripgrep search tool
        "ripgrep",  # fast search tool
        "ag",  # the silver searcher
        "ack",  # grep-like search tool
        "locate",  # find files by name
        "look",  # find lines starting with prefix
        "mdfind",  # Spotlight search
        "mdls",  # list file metadata attributes
        # === Text Processing ===
        "uniq",  # filter duplicate lines
        "cut",  # extract columns from text
        "col",  # filter reverse line feeds
        "colrm",  # remove columns from text
        "column",  # format text into columns
        "comm",  # compare sorted files line by line
        "cmp",  # compare files byte by byte
        "diff",  # compare files line by line
        "diff3",  # three-way file comparison
        "diffstat",  # histogram of diff changes
        "expand",  # convert tabs to spaces
        "fmt",  # simple text formatter
        "fold",  # wrap lines to fit width
        "jot",  # print sequential or random data
        "join",  # join lines on common field
        "lam",  # laminate files side by side
        "nl",  # number lines
        "paste",  # merge lines of files
        "pr",  # paginate text for printing
        "rev",  # reverse characters in lines
        "rs",  # reshape data array
        "seq",  # print number sequence
        "tr",  # translate characters
        "tsort",  # topological sort
        "ul",  # underline text for terminal
        "unexpand",  # convert spaces to tabs
        "unvis",  # decode vis encoding
        "vis",  # encode non-printable characters
        "what",  # show SCCS identification strings
        # Calculators
        "bc",  # arbitrary precision calculator
        "dc",  # reverse polish calculator
        "expr",  # evaluate expression
        "units",  # unit conversion calculator
        # === Structured Data ===
        "jq",  # JSON processor
        "xq",  # XML/HTML beautifier and extractor
        # === Encoding & Checksums ===
        "base64",  # base64 encode/decode
        "md5sum",  # compute MD5 checksum
        "sha1sum",  # compute SHA1 checksum
        "sha256sum",  # compute SHA256 checksum
        "sha512sum",  # compute SHA512 checksum
        "b2sum",  # compute BLAKE2 checksum
        "cksum",  # compute CRC checksum
        "md5",  # compute MD5 checksum (macOS)
        "shasum",  # compute SHA checksum
        "sum",  # compute BSD checksum
        # === User & System Information ===
        "whoami",  # print current username
        "hostname",  # print system hostname
        "hostinfo",  # display host information
        "uname",  # print system information
        "sw_vers",  # print macOS version
        "id",  # print user and group IDs
        "finger",  # user information lookup
        "groups",  # print group memberships
        "last",  # list login history
        "locale",  # display locale settings
        "logname",  # print login name
        "users",  # list logged-in users
        "w",  # show who is logged in
        "who",  # show who is logged in
        "klist",  # list Kerberos credentials
        # Date & time
        "date",  # print or set date/time
        "cal",  # display calendar
        "uptime",  # system uptime and load
        # System configuration
        "getconf",  # get system configuration values
        "machine",  # print machine type
        "pagesize",  # print system page size
        # === Process & Resource Monitoring ===
        "atos",  # convert addresses to symbols
        "btop",  # resource monitor
        "footprint",  # display memory footprint
        "free",  # display memory usage
        "fs_usage",  # report filesystem activity
        "fuser",  # list processes using files
        "heap",  # list heap allocations
        "htop",  # interactive process viewer
        "ioreg",  # display I/O Kit registry
        "iostat",  # I/O statistics
        "ipcs",  # report IPC status
        "leaks",  # search for memory leaks
        "lskq",  # display kqueue state
        "lsmp",  # display mach ports
        "lsof",  # list open files
        "lsvfs",  # list installed filesystems
        "lpstat",  # printer status
        "nettop",  # display network usage
        "pgrep",  # find processes by name
        "powermetrics",  # power and performance metrics
        "ps",  # list processes
        "sample",  # profile a process
        "system_profiler",  # system hardware/software report
        "top",  # display process activity
        "vm_stat",  # virtual memory statistics
        "vmmap",  # display process memory map
        "vmstat",  # virtual memory statistics
        # === Environment & Output ===
        "printenv",  # print environment variables
        "echo",  # print arguments
        "printf",  # formatted print
        # === Network Diagnostics ===
        "ping",  # send ICMP echo requests
        "host",  # DNS lookup
        "dig",  # DNS lookup tool
        "nslookup",  # DNS lookup tool
        "traceroute",  # trace packet route
        "mtr",  # traceroute and ping combined
        "netstat",  # network statistics
        "ss",  # socket statistics
        "arp",  # display ARP table
        "route",  # display routing table
        "whois",  # domain registration lookup
        # === Command Lookup & Help ===
        "which",  # locate a command
        "whereis",  # locate binary, source, manual
        "type",  # describe command type
        "command",  # run command ignoring functions
        "hash",  # remember command locations
        "man",  # display manual pages
        "help",  # display shell help
        "info",  # display info documentation
        "tldr",  # simplified man pages
        # === Code Quality & Linting ===
        "cloc",  # count lines of code
        "flake8",  # Python linter
        "mypy",  # Python type checker
        # === Media & Image Info ===
        "afinfo",  # audio file information
        "ffprobe",  # multimedia stream analyzer
        "heif-info",  # HEIF image information
        "identify",  # describe image format
        "opj_dump",  # JPEG 2000 file information
        "rdjpgcom",  # display JPEG comments
        "sndfile-info",  # sound file information
        "tiffdump",  # TIFF file information
        "tiffinfo",  # TIFF file information
        "webpinfo",  # WebP file information
        # === Shell Builtins & Utilities ===
        "true",  # return success
        "false",  # return failure
        "shopt",  # set/unset shell options (session-local)
        "sleep",  # delay for specified time
        "read",  # read line from stdin
        # === Terminal ===
        "clear",  # clear terminal screen
        "reset",  # reset terminal state
        "tput",  # terminal capability interface
        "tty",  # print terminal name
    }
)


# === Transparent Wrappers ===
# Commands that wrap other commands - we analyze the inner command instead

WRAPPER_COMMANDS = frozenset(
    {
        "time",  # measure command execution time
        "timeout",  # run command with time limit
        "nice",  # run command with altered priority
        "nohup",  # run command immune to hangups
        "strace",  # trace system calls
        "ltrace",  # trace library calls
        "command",  # run command ignoring functions
        "builtin",  # run shell builtin
    }
)
