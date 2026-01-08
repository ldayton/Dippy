"""
Comprehensive tests for ifconfig CLI handler.

Ifconfig is safe for viewing, but modification commands need confirmation.
"""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Viewing network interfaces ===
    ("ifconfig", True),
    ("ifconfig -a", True),  # all interfaces
    ("ifconfig eth0", True),  # specific interface
    ("ifconfig en0", True),
    ("ifconfig lo0", True),
    ("ifconfig -s", True),  # short format
    ("ifconfig -v", True),  # verbose
    #
    # === UNSAFE: Modifying interfaces ===
    ("ifconfig eth0 up", False),
    ("ifconfig eth0 down", False),
    ("ifconfig eth0 192.168.1.100", False),  # set IP
    ("ifconfig eth0 192.168.1.100 netmask 255.255.255.0", False),
    ("ifconfig eth0 broadcast 192.168.1.255", False),
    ("ifconfig eth0 mtu 1500", False),
    ("ifconfig eth0 arp", False),  # enable ARP
    ("ifconfig eth0 -arp", False),  # disable ARP
    ("ifconfig eth0 promisc", False),  # enable promiscuous
    ("ifconfig eth0 -promisc", False),  # disable promiscuous
    ("ifconfig eth0 allmulti", False),  # enable multicast
    ("ifconfig eth0 -allmulti", False),
    ("ifconfig eth0 hw ether 00:11:22:33:44:55", False),  # set MAC
    ("ifconfig eth0 ether 00:11:22:33:44:55", False),
    ("ifconfig eth0 add 2001:db8::1/64", False),  # add IPv6
    ("ifconfig eth0 del 2001:db8::1/64", False),  # remove IPv6
    ("ifconfig eth0 pointopoint 10.0.0.1", False),
    ("ifconfig eth0 txqueuelen 1000", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
