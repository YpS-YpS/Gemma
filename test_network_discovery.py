#!/usr/bin/env python3
"""
Test script for the new dynamic network discovery system
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backend.discovery.network_utils import NetworkDiscovery
import json

def main():
    print("=" * 60)
    print("Dynamic Network Discovery Test")
    print("=" * 60)
    
    # Test host IP detection
    print("\n1. Host IP Detection:")
    host_ip = NetworkDiscovery.get_host_ip()
    print(f"   Detected host IP: {host_ip}")
    
    # Test network range discovery
    print("\n2. Network Range Discovery:")
    network_ranges = NetworkDiscovery.get_local_network_ranges()
    for i, network in enumerate(network_ranges, 1):
        print(f"   {i}. {network}")
    
    # Test comprehensive network info
    print("\n3. Comprehensive Network Info:")
    network_info = NetworkDiscovery.get_network_info()
    print(f"   Host IP: {network_info['host_ip']}")
    print(f"   Network Ranges: {len(network_info['network_ranges'])}")
    print(f"   Active Interfaces: {len(network_info['interfaces'])}")
    
    print("\n4. Active Network Interfaces:")
    for interface in network_info['interfaces']:
        if interface['is_up']:
            print(f"   Interface: {interface['name']} (UP)")
            for addr in interface['addresses']:
                print(f"     IP: {addr['ip']}/{addr['netmask']}")
    
    # Test subnet detection for user's IPs
    print("\n5. Subnet Detection for User's IPs:")
    test_ips = ["192.168.0.106", "192.168.0.101"]
    for ip in test_ips:
        subnet = NetworkDiscovery.get_subnet_for_ip(ip)
        print(f"   {ip} -> {subnet}")
    
    # Test port reachability
    print("\n6. Port Reachability Test:")
    test_targets = [
        ("192.168.0.106", 5000),
        ("192.168.0.101", 8080),
        ("127.0.0.1", 5000),
        ("8.8.8.8", 53)  # DNS
    ]
    
    for ip, port in test_targets:
        reachable = NetworkDiscovery.is_ip_reachable(ip, port, timeout=2.0)
        status = "✓ REACHABLE" if reachable else "✗ UNREACHABLE"
        print(f"   {ip}:{port} - {status}")
    
    print("\n" + "=" * 60)
    print("Network Discovery Test Complete")
    print("=" * 60)
    
    # Check if user's network is discovered
    user_network = "192.168.0.0/24"
    if user_network in network_ranges:
        print(f"\n✅ SUCCESS: Your network ({user_network}) is auto-discovered!")
    else:
        print(f"\n⚠️  WARNING: Your network ({user_network}) was not auto-discovered.")
        print("   This might happen if the host system is not on the 192.168.0.x network.")
        print("   The discovery system will scan networks based on active interfaces.")

if __name__ == '__main__':
    main()