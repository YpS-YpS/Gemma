# -*- coding: utf-8 -*-
"""
Device registry for tracking SUT devices and their states
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum

try:
    from ..core.events import event_bus, EventType
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from core.events import event_bus, EventType

logger = logging.getLogger(__name__)


class SUTStatus(Enum):
    """SUT status enumeration"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class SUTDevice:
    """SUT device information"""
    ip: str
    port: int
    unique_id: str
    hostname: str = ""
    status: SUTStatus = SUTStatus.UNKNOWN
    capabilities: List[str] = field(default_factory=list)
    last_seen: datetime = field(default_factory=datetime.now)
    first_discovered: datetime = field(default_factory=datetime.now)
    current_task: Optional[str] = None
    error_count: int = 0
    total_pings: int = 0
    successful_pings: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate ping success rate"""
        if self.total_pings == 0:
            return 0.0
        return self.successful_pings / self.total_pings
        
    @property
    def is_online(self) -> bool:
        """Check if device is considered online"""
        return self.status == SUTStatus.ONLINE
        
    @property
    def age_seconds(self) -> int:
        """Get age of device discovery in seconds"""
        return int((datetime.now() - self.first_discovered).total_seconds())
        
    @property
    def last_seen_seconds(self) -> int:
        """Get seconds since last seen"""
        return int((datetime.now() - self.last_seen).total_seconds())


class DeviceRegistry:
    """Registry for managing SUT devices"""
    
    def __init__(self, offline_timeout: int = 30):
        self.devices: Dict[str, SUTDevice] = {}  # Key: unique_id
        self.ip_to_id_mapping: Dict[str, str] = {}  # Key: ip, Value: unique_id
        self.offline_timeout = offline_timeout  # Seconds to consider device offline
        self._lock = None  # Will be set by controller
        
    def register_device(self, ip: str, port: int, unique_id: str, capabilities: List[str] = None, hostname: str = "") -> SUTDevice:
        """Register or update a SUT device"""
        capabilities = capabilities or []
        
        # Check if device already exists
        if unique_id in self.devices:
            device = self.devices[unique_id]
            old_status = device.status
            
            # Update existing device
            device.ip = ip  # IP might have changed
            device.port = port
            device.hostname = hostname
            device.capabilities = capabilities
            device.last_seen = datetime.now()
            device.successful_pings += 1
            device.total_pings += 1
            
            # Update status if it was offline
            if device.status == SUTStatus.OFFLINE:
                device.status = SUTStatus.ONLINE
                device.error_count = 0
                logger.info(f"SUT {unique_id} came back online at {ip}:{port}")
                event_bus.emit(EventType.SUT_ONLINE, {
                    "device_id": unique_id,
                    "ip": ip,
                    "port": port,
                    "hostname": hostname
                })
            elif old_status != device.status:
                event_bus.emit(EventType.SUT_STATUS_CHANGED, {
                    "device_id": unique_id,
                    "old_status": old_status.value,
                    "new_status": device.status.value,
                    "ip": ip,
                    "port": port
                })
        else:
            # Create new device
            device = SUTDevice(
                ip=ip,
                port=port,
                unique_id=unique_id,
                hostname=hostname,
                status=SUTStatus.ONLINE,
                capabilities=capabilities,
                successful_pings=1,
                total_pings=1
            )
            
            self.devices[unique_id] = device
            logger.info(f"New SUT discovered: {unique_id} at {ip}:{port} with hostname '{hostname}'")
            event_bus.emit(EventType.SUT_DISCOVERED, {
                "device_id": unique_id,
                "ip": ip,
                "port": port,
                "hostname": hostname,
                "capabilities": capabilities
            })
            
        # Update IP mapping
        self.ip_to_id_mapping[ip] = unique_id
        
        return device
        
    def update_device_ping_fail(self, unique_id: str):
        """Update device when ping fails"""
        if unique_id in self.devices:
            device = self.devices[unique_id]
            device.error_count += 1
            device.total_pings += 1
            
            # Mark as offline if too many failures or timeout
            if (device.error_count >= 3 or 
                (datetime.now() - device.last_seen).total_seconds() > self.offline_timeout):
                
                if device.status != SUTStatus.OFFLINE:
                    old_status = device.status
                    device.status = SUTStatus.OFFLINE
                    logger.warning(f"SUT {unique_id} marked as offline (errors: {device.error_count})")
                    event_bus.emit(EventType.SUT_OFFLINE, {
                        "device_id": unique_id,
                        "ip": device.ip,
                        "port": device.port,
                        "error_count": device.error_count
                    })
                    
    def get_device_by_id(self, unique_id: str) -> Optional[SUTDevice]:
        """Get device by unique ID"""
        return self.devices.get(unique_id)
        
    def get_device_by_ip(self, ip: str) -> Optional[SUTDevice]:
        """Get device by IP address"""
        unique_id = self.ip_to_id_mapping.get(ip)
        return self.devices.get(unique_id) if unique_id else None
        
    def get_online_devices(self) -> List[SUTDevice]:
        """Get all online devices"""
        return [device for device in self.devices.values() if device.status == SUTStatus.ONLINE]
        
    def get_all_devices(self) -> List[SUTDevice]:
        """Get all devices"""
        return list(self.devices.values())
        
    def set_device_busy(self, unique_id: str, task: str = None):
        """Mark device as busy"""
        if unique_id in self.devices:
            device = self.devices[unique_id]
            old_status = device.status
            device.status = SUTStatus.BUSY
            device.current_task = task
            
            if old_status != SUTStatus.BUSY:
                event_bus.emit(EventType.SUT_STATUS_CHANGED, {
                    "device_id": unique_id,
                    "old_status": old_status.value,
                    "new_status": SUTStatus.BUSY.value,
                    "task": task
                })
                
    def set_device_online(self, unique_id: str):
        """Mark device as online and available"""
        if unique_id in self.devices:
            device = self.devices[unique_id]
            old_status = device.status
            device.status = SUTStatus.ONLINE
            device.current_task = None
            
            if old_status != SUTStatus.ONLINE:
                event_bus.emit(EventType.SUT_STATUS_CHANGED, {
                    "device_id": unique_id,
                    "old_status": old_status.value,
                    "new_status": SUTStatus.ONLINE.value
                })
                
    def cleanup_stale_devices(self):
        """Remove devices that haven't been seen for a long time"""
        stale_threshold = timedelta(minutes=10)  # 10 minutes
        current_time = datetime.now()
        stale_devices = []
        
        for unique_id, device in self.devices.items():
            if current_time - device.last_seen > stale_threshold:
                stale_devices.append(unique_id)
                
        for unique_id in stale_devices:
            device = self.devices[unique_id]
            logger.info(f"Removing stale device: {unique_id} (last seen: {device.last_seen})")
            
            # Remove from IP mapping
            if device.ip in self.ip_to_id_mapping:
                del self.ip_to_id_mapping[device.ip]
                
            del self.devices[unique_id]
            
    def get_device_stats(self) -> Dict[str, any]:
        """Get registry statistics"""
        online_count = len(self.get_online_devices())
        total_count = len(self.devices)
        
        return {
            "total_devices": total_count,
            "online_devices": online_count,
            "offline_devices": total_count - online_count,
            "discovery_rate": f"{online_count}/{total_count}" if total_count > 0 else "0/0"
        }