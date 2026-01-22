"""
Comprehensive tests for ip CLI handler.

The ip command is safe for viewing, but modification commands need confirmation.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Viewing network info ===
    ("ip addr", True),
    ("ip address", True),
    ("ip a", True),  # common alias
    ("ip addr show", True),
    ("ip addr show dev eth0", True),
    ("ip addr show up", True),  # only active interfaces
    ("ip -4 addr", True),
    ("ip -6 addr", True),
    #
    # === SAFE: Link layer ===
    ("ip link", True),
    ("ip l", True),  # alias
    ("ip link show", True),
    ("ip link show eth0", True),
    ("ip link show up", True),  # only active
    ("ip -s link", True),  # with stats
    ("ip -s -s link", True),  # more stats
    #
    # === SAFE: Routing ===
    ("ip route", True),
    ("ip r", True),
    ("ip route show", True),
    ("ip route get 8.8.8.8", True),
    ("ip route get 2001:db8::1", True),
    ("ip -6 route", True),
    ("ip route list", True),
    ("ip route list table main", True),
    ("ip route show table all", True),
    #
    # === SAFE: Rules ===
    ("ip rule", True),
    ("ip ru", True),  # alias
    ("ip rule show", True),
    ("ip rule list", True),
    #
    # === SAFE: Neighbor/ARP ===
    ("ip neigh", True),
    ("ip neighbor", True),
    ("ip n", True),  # alias
    ("ip neigh show", True),
    ("ip neigh show dev eth0", True),
    ("ip neigh get 192.168.1.1 dev eth0", True),  # lookup
    #
    # === SAFE: Tunnel/TUN/TAP ===
    ("ip tunnel", True),
    ("ip tunnel show", True),
    ("ip tuntap", True),
    ("ip tunt", True),  # alias
    ("ip tuntap show", True),
    ("ip tuntap list", True),
    #
    # === SAFE: Multicast ===
    ("ip maddr", True),
    ("ip maddress", True),
    ("ip m", True),  # alias
    ("ip maddr show", True),
    ("ip maddr show dev eth0", True),
    ("ip mroute", True),
    ("ip mroute show", True),
    #
    # === SAFE: Monitor ===
    ("ip monitor", True),
    ("ip mo", True),  # alias
    ("ip monitor all", True),
    ("ip monitor link", True),
    ("ip monitor address", True),
    ("ip monitor route", True),
    ("ip monitor neigh", True),
    #
    # === SAFE: Netns (viewing) ===
    ("ip netns", True),
    ("ip netns list", True),
    ("ip netns identify", True),
    ("ip netns identify 1234", True),
    ("ip netns pids testns", True),
    #
    # === SAFE: Netconf ===
    ("ip netconf", True),
    ("ip netc", True),  # alias
    ("ip netconf show", True),
    ("ip netconf show dev eth0", True),
    ("ip -4 netconf", True),
    ("ip -6 netconf", True),
    #
    # === SAFE: Stats ===
    ("ip stats", True),
    ("ip st", True),  # alias
    ("ip stats show", True),
    ("ip stats show dev eth0", True),
    ("ip stats show group link", True),
    ("ip stats show group offload", True),
    #
    # === SAFE: Global flags ===
    ("ip -j addr", True),  # JSON output
    ("ip -br addr", True),  # brief
    ("ip --brief addr", True),
    ("ip -c addr", True),  # color
    ("ip -o addr", True),  # one-line
    ("ip -d link", True),  # details
    ("ip -h link", True),  # human readable
    ("ip --human-readable link", True),
    ("ip -p route", True),  # pretty
    ("ip -rc route", True),  # color + resolve
    ("ip -n testns addr", True),  # namespace
    ("ip -netns testns addr", True),
    ("ip -all netns exec ip addr", False),  # exec is still unsafe
    #
    # === UNSAFE: Modifying addresses ===
    ("ip addr add 192.168.1.100/24 dev eth0", False),
    ("ip a add 192.168.1.100/24 dev eth0", False),
    ("ip addr del 192.168.1.100/24 dev eth0", False),
    ("ip addr delete 192.168.1.100/24 dev eth0", False),
    ("ip addr change 192.168.1.100/24 dev eth0", False),
    ("ip addr replace 192.168.1.100/24 dev eth0", False),
    ("ip addr flush dev eth0", False),
    ("ip -4 addr flush dev eth0", False),
    #
    # === UNSAFE: Modifying links ===
    ("ip link set eth0 up", False),
    ("ip link set eth0 down", False),
    ("ip l set eth0 up", False),
    ("ip link add veth0 type veth peer name veth1", False),
    ("ip link add br0 type bridge", False),
    ("ip link del veth0", False),
    ("ip link delete veth0", False),
    ("ip link set eth0 address 00:11:22:33:44:55", False),
    ("ip link set eth0 mtu 9000", False),
    ("ip link set eth0 promisc on", False),
    #
    # === UNSAFE: Modifying routes ===
    ("ip route add default via 192.168.1.1", False),
    ("ip r add 10.0.0.0/8 via 192.168.1.1", False),
    ("ip route del default", False),
    ("ip route delete 10.0.0.0/8", False),
    ("ip route change 10.0.0.0/8 via 192.168.1.2", False),
    ("ip route replace default via 192.168.1.1", False),
    ("ip route flush", False),
    ("ip route flush table main", False),
    #
    # === UNSAFE: Modifying rules ===
    ("ip rule add from 192.168.1.0/24 table 100", False),
    ("ip ru add from all lookup 100", False),
    ("ip rule del from 192.168.1.0/24", False),
    ("ip rule delete priority 100", False),
    ("ip rule flush", False),
    #
    # === UNSAFE: Modifying neighbor ===
    ("ip neigh add 192.168.1.1 lladdr 00:11:22:33:44:55 dev eth0", False),
    ("ip n add 192.168.1.1 lladdr 00:11:22:33:44:55 dev eth0", False),
    ("ip neigh del 192.168.1.1 dev eth0", False),
    ("ip neigh delete 192.168.1.1 dev eth0", False),
    ("ip neigh change 192.168.1.1 lladdr 00:11:22:33:44:66 dev eth0", False),
    ("ip neigh replace 192.168.1.1 lladdr 00:11:22:33:44:66 dev eth0", False),
    ("ip neigh flush dev eth0", False),
    #
    # === UNSAFE: Modifying netns ===
    ("ip netns add testns", False),
    ("ip netns del testns", False),
    ("ip netns delete testns", False),
    ("ip netns exec testns ip addr", False),  # exec runs commands
    ("ip netns exec testns bash", False),
    #
    # === UNSAFE: Modifying tunnel/tuntap ===
    ("ip tunnel add tun0 mode gre", False),
    ("ip tunnel del tun0", False),
    ("ip tunnel delete tun0", False),
    ("ip tunnel change tun0 mode ipip", False),
    ("ip tuntap add dev tun0 mode tun", False),
    ("ip tuntap del dev tun0 mode tun", False),
    ("ip tunt add dev tap0 mode tap", False),
    #
    # === UNSAFE: Modifying multicast ===
    ("ip maddr add 33:33:00:00:00:02 dev eth0", False),
    ("ip maddr del 33:33:00:00:00:02 dev eth0", False),
    ("ip maddress add 33:33:00:00:00:02 dev eth0", False),
    ("ip maddress delete 33:33:00:00:00:02 dev eth0", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
