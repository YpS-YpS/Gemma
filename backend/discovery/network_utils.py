# -*- coding: utf-8 -*-
"""
Network utilities for dynamic network interface discovery
"""

import logging
import socket
import ipaddress
import platform
import subprocess
from typing import List, Set, Tuple
import psutil

logger = logging.getLogger(__name__)


class NetworkDiscovery:
    """Dynamic network discovery utility"""
    
    @staticmethod
    def get_local_network_ranges() -> List[str]:
        """Automatically discover local network ranges based on active interfaces"""
        network_ranges = []
        
        try:
            # Get all network interfaces
            interfaces = psutil.net_if_addrs()
            
            for interface_name, addresses in interfaces.items():
                # Skip loopback and virtual interfaces
                if (interface_name.startswith('lo') or 
                    interface_name.startswith('docker') or
                    interface_name.startswith('veth') or
                    interface_name.startswith('br-')):
                    continue
                
                for addr in addresses:
                    if addr.family == socket.AF_INET:  # IPv4
                        ip = addr.address
                        netmask = addr.netmask
                        
                        # Skip localhost
                        if ip.startswith('127.'):
                            continue
                            
                        # Calculate network range
                        try:
                            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                            network_range = str(network.network_address) + f"/{network.prefixlen}"
                            
                            # Only include networks with reasonable size (up to /16)
                            if network.prefixlen >= 16:
                                network_ranges.append(network_range)
                                logger.info(f"Discovered network range: {network_range} on interface {interface_name}")
                                
                        except Exception as e:
                            logger.debug(f"Error processing interface {interface_name} ({ip}/{netmask}): {e}")
                            
        except Exception as e:
            logger.error(f"Error discovering network interfaces: {e}")
            
        # Fallback to common private network ranges if nothing found
        if not network_ranges:
            logger.warning("No network interfaces found, using fallback ranges")
            network_ranges = [
                "192.168.1.0/24",
                "192.168.0.0/24",
                "10.0.0.0/24",
                "172.16.0.0/24"
            ]
            
        # Always add localhost for testing
        network_ranges.append("127.0.0.1/32")
        
        return network_ranges
    
    @staticmethod
    def get_host_ip() -> str:
        """Get the primary host IP address"""
        try:
            # Connect to a remote address to determine which local interface is used
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Use Google's DNS as a reference point
                s.connect(("8.8.8.8", 80))
                host_ip = s.getsockname()[0]
                logger.info(f"Detected host IP: {host_ip}")
                return host_ip
        except Exception as e:
            logger.error(f"Error detecting host IP: {e}")
            return "127.0.0.1"
    
    @staticmethod
    def get_subnet_for_ip(ip: str) -> str:
        """Get the subnet for a given IP address"""
        try:
            # Find the interface that has this IP
            interfaces = psutil.net_if_addrs()
            
            for interface_name, addresses in interfaces.items():
                for addr in addresses:
                    if addr.family == socket.AF_INET and addr.address == ip:
                        network = ipaddress.IPv4Network(f"{ip}/{addr.netmask}", strict=False)
                        return str(network.supernet())
                        
        except Exception as e:
            logger.error(f"Error finding subnet for IP {ip}: {e}")
            
        # Fallback: assume /24 network
        try:
            ip_obj = ipaddress.IPv4Address(ip)
            # Create a /24 network
            network = ipaddress.IPv4Network(f"{ip}/24", strict=False)
            return str(network.supernet())
        except Exception:
            return f"{ip}/32"
    
    @staticmethod
    def is_ip_reachable(ip: str, port: int, timeout: float = 1.0) -> bool:
        """Quick check if an IP:port is reachable"""
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except (socket.error, OSError):
            return False
    
    @staticmethod
    def scan_network_for_services(network_range: str, port: int, timeout: float = 1.0) -> List[str]:
        """Scan a network range for services on a specific port"""
        reachable_ips = []
        
        try:
            network = ipaddress.ip_network(network_range, strict=False)
            
            # Limit scanning to reasonable subnet sizes
            if network.num_addresses > 256:
                logger.warning(f"Network {network_range} too large, skipping")
                return reachable_ips
                
            for ip in network.hosts():
                if NetworkDiscovery.is_ip_reachable(str(ip), port, timeout):
                    reachable_ips.append(str(ip))
                    logger.debug(f"Found service at {ip}:{port}")
                    
        except Exception as e:
            logger.error(f"Error scanning network {network_range}: {e}")
            
        return reachable_ips
    
    @staticmethod
    def get_network_info() -> dict:
        """Get comprehensive network information"""
        info = {
            "host_ip": NetworkDiscovery.get_host_ip(),
            "network_ranges": NetworkDiscovery.get_local_network_ranges(),
            "interfaces": []
        }
        
        try:
            interfaces = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            
            for interface_name, addresses in interfaces.items():
                interface_stats = stats.get(interface_name) if stats else None
                interface_info = {
                    "name": interface_name,
                    "is_up": interface_stats.isup if interface_stats else False,
                    "addresses": []
                }
                
                for addr in addresses:
                    if addr.family == socket.AF_INET:  # IPv4
                        interface_info["addresses"].append({
                            "ip": addr.address,
                            "netmask": addr.netmask,
                            "broadcast": getattr(addr, 'broadcast', None)
                        })
                        
                if interface_info["addresses"]:  # Only include interfaces with IPv4
                    info["interfaces"].append(interface_info)
                    
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
            
        return info