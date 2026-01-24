"""Test cases for networksetup."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # List operations - safe
    ("networksetup -listnetworkserviceorder", True),
    ("networksetup -listallnetworkservices", True),
    ("networksetup -listallhardwareports", True),
    ("networksetup -listpreferredwirelessnetworks en0", True),
    ("networksetup -listvalidMTUrange en0", True),
    ("networksetup -listvalidmedia en0", True),
    ("networksetup -listVLANs", True),
    ("networksetup -listdevicesthatsupportVLAN", True),
    ("networksetup -listBonds", True),
    ("networksetup -listpppoeservices", True),
    ("networksetup -listlocations", True),
    # Get operations - safe
    ("networksetup -getmacaddress en0", True),
    ("networksetup -getcomputername", True),
    ("networksetup -getinfo Wi-Fi", True),
    ("networksetup -getadditionalroutes Wi-Fi", True),
    ("networksetup -getv6additionalroutes Wi-Fi", True),
    ("networksetup -getdnsservers Wi-Fi", True),
    ("networksetup -getsearchdomains Wi-Fi", True),
    ("networksetup -getwebproxy Wi-Fi", True),
    ("networksetup -getsecurewebproxy Wi-Fi", True),
    ("networksetup -getsocksfirewallproxy Wi-Fi", True),
    ("networksetup -getproxybypassdomains Wi-Fi", True),
    ("networksetup -getproxyautodiscovery Wi-Fi", True),
    ("networksetup -getautoproxyurl Wi-Fi", True),
    ("networksetup -getairportnetwork en0", True),
    ("networksetup -getairportpower en0", True),
    ("networksetup -getnetworkserviceenabled Wi-Fi", True),
    ("networksetup -getMTU en0", True),
    ("networksetup -getmedia en0", True),
    ("networksetup -getcurrentlocation", True),
    # Show operations - safe
    ("networksetup -showBondStatus bond0", True),
    ("networksetup -showpppoestatus MyPPPoE", True),
    # Other safe operations
    ("networksetup -isBondSupported en0", True),
    ("networksetup -version", True),
    ("networksetup -help", True),
    ("networksetup -printcommands", True),
    # Set operations - unsafe
    ("networksetup -setcomputername MyMac", False),
    ("networksetup -setmanual Wi-Fi 192.168.1.100 255.255.255.0 192.168.1.1", False),
    ("networksetup -setdhcp Wi-Fi", False),
    ("networksetup -setdnsservers Wi-Fi 8.8.8.8 8.8.4.4", False),
    ("networksetup -setairportnetwork en0 MyNetwork password", False),
    ("networksetup -setairportpower en0 on", False),
    ("networksetup -setwebproxy Wi-Fi proxy.example.com 8080 off", False),
    ("networksetup -setMTU en0 1500", False),
    # Create operations - unsafe
    ("networksetup -createnetworkservice MyService en0", False),
    ("networksetup -createVLAN MyVLAN en0 100", False),
    ("networksetup -createBond MyBond en0 en1", False),
    ("networksetup -createlocation Office", False),
    ("networksetup -createpppoeservice en0 MyPPPoE user pass", False),
    # Delete/remove operations - unsafe
    ("networksetup -removenetworkservice MyService", False),
    ("networksetup -removepreferredwirelessnetwork en0 OldNetwork", False),
    ("networksetup -deleteVLAN MyVLAN en0 100", False),
    ("networksetup -deleteBond bond0", False),
    ("networksetup -deletelocation Office", False),
    # Other modifying operations - unsafe
    ("networksetup -detectnewhardware", False),
    ("networksetup -renamenetworkservice Wi-Fi WiFi", False),
    ("networksetup -duplicatenetworkservice Wi-Fi Wi-Fi2", False),
    ("networksetup -ordernetworkservices Wi-Fi Ethernet", False),
    ("networksetup -addpreferredwirelessnetworkatindex en0 MyNet 0 WPA2", False),
    ("networksetup -addDeviceToBond en2 bond0", False),
    ("networksetup -connectpppoeservice MyPPPoE", False),
    ("networksetup -disconnectpppoeservice MyPPPoE", False),
    ("networksetup -switchtolocation Office", False),
    # No arguments - unsafe
    ("networksetup", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
