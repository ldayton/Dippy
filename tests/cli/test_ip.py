"""
Comprehensive tests for ip CLI handler.

The ip command is safe for viewing, but modification commands need confirmation.
"""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Viewing network info ===
    ("ip addr", True),
    ("ip address", True),
    ("ip a", True),  # common alias
    ("ip addr show", True),
    ("ip addr show dev eth0", True),
    ("ip -4 addr", True),
    ("ip -6 addr", True),
    ("ip link", True),
    ("ip link show", True),
    ("ip link show eth0", True),
    ("ip -s link", True),  # with stats
    ("ip route", True),
    ("ip r", True),
    ("ip route show", True),
    ("ip route get 8.8.8.8", True),
    ("ip -6 route", True),
    ("ip rule", True),
    ("ip rule show", True),
    ("ip rule list", True),
    ("ip neigh", True),
    ("ip neighbor", True),
    ("ip neigh show", True),
    ("ip tunnel", True),
    ("ip tunnel show", True),
    ("ip tuntap", True),
    ("ip tuntap show", True),
    ("ip maddr", True),
    ("ip maddress", True),
    ("ip mroute", True),
    ("ip monitor", True),
    ("ip netns", True),
    ("ip netns list", True),
    ("ip -j addr", True),  # JSON output
    ("ip -br addr", True),  # brief
    ("ip --brief addr", True),
    ("ip -c addr", True),  # color
    ("ip -o addr", True),  # one-line
    #
    # === UNSAFE: Modifying network config ===
    ("ip addr add 192.168.1.100/24 dev eth0", False),
    ("ip addr del 192.168.1.100/24 dev eth0", False),
    ("ip addr delete 192.168.1.100/24 dev eth0", False),
    ("ip addr change 192.168.1.100/24 dev eth0", False),
    ("ip addr replace 192.168.1.100/24 dev eth0", False),
    ("ip addr flush dev eth0", False),
    ("ip link set eth0 up", False),
    ("ip link set eth0 down", False),
    ("ip link add veth0 type veth peer name veth1", False),
    ("ip link del veth0", False),
    ("ip link delete veth0", False),
    ("ip route add default via 192.168.1.1", False),
    ("ip route del default", False),
    ("ip route delete 10.0.0.0/8", False),
    ("ip route change 10.0.0.0/8 via 192.168.1.2", False),
    ("ip route replace default via 192.168.1.1", False),
    ("ip route flush", False),
    ("ip rule add from 192.168.1.0/24 table 100", False),
    ("ip rule del from 192.168.1.0/24", False),
    ("ip neigh add 192.168.1.1 lladdr 00:11:22:33:44:55 dev eth0", False),
    ("ip neigh del 192.168.1.1 dev eth0", False),
    ("ip neigh flush dev eth0", False),
    ("ip netns add testns", False),
    ("ip netns del testns", False),
    ("ip netns delete testns", False),
    ("ip netns exec testns ip addr", False),  # exec runs commands
    ("ip tunnel add tun0 mode gre", False),
    ("ip tunnel del tun0", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
