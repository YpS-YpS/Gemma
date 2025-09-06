"""
Simple test without external dependencies to verify basic functionality
"""

import sys
import os
import time
import logging

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Test that our modules can be imported"""
    print("🧪 Testing module imports...")
    
    try:
        from core.config import BackendConfig, ConfigManager
        print("✅ Config module imported successfully")
        
        from core.events import EventBus, EventType, Event
        print("✅ Events module imported successfully")
        
        from discovery.device_registry import DeviceRegistry, SUTDevice, SUTStatus
        print("✅ Device registry module imported successfully")
        
        # Test configuration
        config = ConfigManager.load_config()
        print(f"✅ Configuration loaded: host={config.host}, port={config.port}")
        
        # Test device registry
        registry = DeviceRegistry()
        print("✅ Device registry created successfully")
        
        # Test event system
        event_bus = EventBus()
        print("✅ Event bus created successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_device_registry():
    """Test device registry functionality"""
    print("\n📱 Testing device registry...")
    
    try:
        from discovery.device_registry import DeviceRegistry, SUTDevice, SUTStatus
        
        registry = DeviceRegistry()
        
        # Test device registration
        device = registry.register_device(
            ip="192.168.1.100",
            port=8080,
            unique_id="test_sut_001",
            capabilities=["basic_clicks", "screenshots"],
            hostname="test-machine"
        )
        
        print(f"✅ Device registered: {device.unique_id} at {device.ip}")
        
        # Test device retrieval
        retrieved = registry.get_device_by_id("test_sut_001")
        if retrieved and retrieved.unique_id == "test_sut_001":
            print("✅ Device retrieval by ID works")
        else:
            print("❌ Device retrieval failed")
            return False
        
        # Test device retrieval by IP
        retrieved_by_ip = registry.get_device_by_ip("192.168.1.100")
        if retrieved_by_ip and retrieved_by_ip.unique_id == "test_sut_001":
            print("✅ Device retrieval by IP works")
        else:
            print("❌ Device retrieval by IP failed")
            return False
        
        # Test device stats
        stats = registry.get_device_stats()
        print(f"✅ Device stats: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ Device registry test failed: {e}")
        return False

def test_events():
    """Test event system"""
    print("\n🔔 Testing event system...")
    
    try:
        from core.events import EventBus, EventType, Event
        
        event_bus = EventBus()
        received_events = []
        
        # Define event handler
        def test_handler(event):
            received_events.append(event)
            print(f"  📨 Received event: {event.event_type.value}")
        
        # Subscribe to events
        event_bus.subscribe(EventType.SUT_DISCOVERED, test_handler)
        
        # Emit test event
        event_bus.emit(EventType.SUT_DISCOVERED, {
            "device_id": "test_device",
            "ip": "192.168.1.100"
        })
        
        # Check if event was received
        if len(received_events) == 1:
            print("✅ Event system working correctly")
            return True
        else:
            print("❌ Event system failed")
            return False
            
    except Exception as e:
        print(f"❌ Event system test failed: {e}")
        return False

def test_discovery_logic():
    """Test discovery service logic without network calls"""
    print("\n🔍 Testing discovery logic...")
    
    try:
        from discovery.device_registry import DeviceRegistry
        
        registry = DeviceRegistry()
        
        # Simulate discovering multiple devices
        devices = [
            {"ip": "192.168.1.100", "id": "sut_001", "hostname": "gaming-pc-01"},
            {"ip": "192.168.1.101", "id": "sut_002", "hostname": "gaming-pc-02"},
            {"ip": "192.168.1.102", "id": "sut_003", "hostname": "gaming-pc-03"}
        ]
        
        for device_info in devices:
            registry.register_device(
                ip=device_info["ip"],
                port=8080,
                unique_id=device_info["id"],
                capabilities=["basic_clicks", "advanced_clicks", "gaming_optimizations"],
                hostname=device_info["hostname"]
            )
        
        print(f"✅ Registered {len(devices)} devices")
        
        # Test getting online devices
        online_devices = registry.get_online_devices()
        print(f"✅ Online devices: {len(online_devices)}")
        
        # Test device status changes
        registry.set_device_busy("sut_001", "Running automation")
        busy_device = registry.get_device_by_id("sut_001")
        
        if busy_device.current_task == "Running automation":
            print("✅ Device status change works")
        else:
            print("❌ Device status change failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Discovery logic test failed: {e}")
        return False

def main():
    """Run simple tests"""
    print("🚀 Starting Simple Backend Test Suite")
    print("=" * 50)
    
    success_count = 0
    total_tests = 4
    
    # Test 1: Module imports
    if test_imports():
        success_count += 1
    
    # Test 2: Device registry
    if test_device_registry():
        success_count += 1
    
    # Test 3: Event system
    if test_events():
        success_count += 1
    
    # Test 4: Discovery logic
    if test_discovery_logic():
        success_count += 1
    
    print("\n" + "=" * 50)
    print(f"🎯 Test Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("🎉 All basic functionality tests passed!")
        print("\n📋 Next steps:")
        print("1. Install missing dependencies:")
        print("   sudo apt install python3-pip")
        print("   pip3 install flask flask-socketio flask-cors requests psutil")
        print("2. Run the full backend: python3 run_backend.py")
        print("3. Run SUT service: python3 gemma_sut_service.py")
    else:
        print("❌ Some tests failed. Check the output above for details.")
    
    return success_count == total_tests

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)