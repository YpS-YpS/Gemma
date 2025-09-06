"""
Test script for the new modular backend system
"""

import sys
import time
import logging
import threading
from backend.core.config import ConfigManager
from backend.core.controller import BackendController

# Simple test configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_backend_initialization():
    """Test basic backend initialization"""
    print("🧪 Testing Backend Initialization...")
    
    config = ConfigManager.load_config()
    # Use a different port for testing
    config.port = 5001
    config.discovery_interval = 5.0  # Faster for testing
    
    controller = BackendController(config)
    
    print("✅ Backend controller created successfully")
    return controller


def test_discovery_service(controller):
    """Test discovery service"""
    print("\n🔍 Testing Discovery Service...")
    
    # Start services
    controller.start()
    
    # Wait a bit for discovery to run
    print("⏳ Waiting for discovery scan...")
    time.sleep(8)
    
    # Check discovered devices
    devices = controller.get_all_devices()
    print(f"📱 Discovered {len(devices)} devices:")
    
    for device in devices:
        print(f"  - {device.unique_id} at {device.ip}:{device.port} ({device.status.value})")
        print(f"    Hostname: {device.hostname}")
        print(f"    Capabilities: {len(device.capabilities)} features")
        print(f"    Last seen: {device.last_seen_seconds}s ago")
        print()
        
    return len(devices) > 0


def test_websocket_system(controller):
    """Test WebSocket system"""
    print("\n🌐 Testing WebSocket System...")
    
    client_count = controller.websocket_handler.get_connected_clients_count()
    print(f"📡 Connected WebSocket clients: {client_count}")
    
    # Test broadcasting a message
    test_message = {"test": "message", "timestamp": time.time()}
    controller.websocket_handler.broadcast_message("test_event", test_message)
    print("📤 Broadcast test message sent")
    
    return True


def test_system_status(controller):
    """Test system status"""
    print("\n📊 Testing System Status...")
    
    status = controller.get_system_status()
    
    print("Backend Status:")
    print(f"  Running: {status['backend']['running']}")
    print(f"  Version: {status['backend']['version']}")
    print(f"  WebSocket Clients: {status['backend']['websocket_clients']}")
    
    print("Discovery Status:")
    print(f"  Running: {status['discovery']['running']}")
    print(f"  Target IPs: {status['discovery']['target_ips']}")
    print(f"  Interval: {status['discovery']['discovery_interval']}s")
    
    print("Device Stats:")
    print(f"  Total: {status['devices']['total_devices']}")
    print(f"  Online: {status['devices']['online_devices']}")
    
    print("Omniparser Status:")
    print(f"  Status: {status['omniparser']['status']}")
    print(f"  URL: {status['omniparser'].get('url', 'N/A')}")
    
    return True


def main():
    """Run the backend test suite"""
    print("🚀 Starting Modular Backend Test Suite")
    print("=" * 50)
    
    controller = None
    
    try:
        # Test 1: Initialization
        controller = test_backend_initialization()
        
        # Test 2: Discovery Service
        has_devices = test_discovery_service(controller)
        
        # Test 3: WebSocket System
        test_websocket_system(controller)
        
        # Test 4: System Status
        test_system_status(controller)
        
        print("\n" + "=" * 50)
        print("🎉 All tests completed!")
        
        if has_devices:
            print("✅ Discovery is working - SUTs found!")
        else:
            print("⚠️  No SUTs discovered - make sure gemma_sut_service.py is running")
            
        print("\nTo test the full system:")
        print("1. Run 'python gemma_sut_service.py' on SUT machines")
        print("2. Run 'python -m backend.main' to start the backend")
        print("3. Connect a frontend to ws://localhost:5000")
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if controller:
            print("\n🔧 Cleaning up...")
            controller.stop()
            print("✅ Cleanup complete")


if __name__ == '__main__':
    main()