# -*- coding: utf-8 -*-
"""
Main backend controller - orchestrates all communication between components
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS

from .config import BackendConfig
from .events import event_bus, EventType
from ..discovery.device_registry import DeviceRegistry
from ..discovery.sut_discovery import SUTDiscoveryService
from ..communication.websocket_handler import WebSocketHandler
from ..communication.sut_client import SUTClient
from ..communication.omniparser_client import OmniparserClient
from ..api.routes import APIRoutes
from .game_manager import GameConfigManager

logger = logging.getLogger(__name__)


class BackendController:
    """Main controller for the backend system"""
    
    def __init__(self, config: BackendConfig):
        self.config = config
        self.running = False
        self._shutdown_event = threading.Event()
        
        # Initialize Flask app and SocketIO
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = config.secret_key
        CORS(self.app, origins="*")
        
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins="*",
            async_mode='threading',
            logger=config.debug,
            engineio_logger=config.debug
        )
        
        # Initialize core components
        self.device_registry = DeviceRegistry(offline_timeout=30)
        self.discovery_service = SUTDiscoveryService(config, self.device_registry)
        self.game_manager = GameConfigManager()
        self.websocket_handler = WebSocketHandler(self.socketio, self.device_registry, self.game_manager)
        
        # Initialize communication clients
        self.sut_client = SUTClient(timeout=config.discovery_timeout)
        self.omniparser_client = OmniparserClient(
            api_url=config.omniparser_url,
            timeout=60.0
        )
        
        # Initialize run manager and automation orchestrator
        from .run_manager import RunManager
        from .automation_orchestrator import AutomationOrchestrator
        
        self.automation_orchestrator = AutomationOrchestrator(
            self.game_manager,
            self.device_registry, 
            self.omniparser_client
        )
        self.run_manager = RunManager(
            max_concurrent_runs=5, 
            orchestrator=self.automation_orchestrator
        )
        
        # Set up run manager callbacks for WebSocket events
        self.run_manager.on_run_started = self._on_run_started
        self.run_manager.on_run_progress = self._on_run_progress
        self.run_manager.on_run_completed = self._on_run_completed
        self.run_manager.on_run_failed = self._on_run_failed

        # Initialize API routes
        self.api_routes = APIRoutes(
            self.device_registry,
            self.discovery_service,
            self.sut_client,
            self.omniparser_client,
            self.websocket_handler,
            self.game_manager
        )
        
        # Pass run manager to API routes
        self.api_routes.run_manager = self.run_manager
        
        # Register API routes with Flask app
        self.api_routes.register_routes(self.app)
        
        # Background services
        self.monitor_thread: Optional[threading.Thread] = None
        
        logger.info("Backend controller initialized")
        
    def start(self):
        """Start all backend services"""
        if self.running:
            logger.warning("Backend controller is already running")
            return
            
        logger.info("Starting backend controller...")
        self.running = True
        self._shutdown_event.clear()
        
        # Start discovery service
        self.discovery_service.start()
        
        # Start run manager
        self.run_manager.start()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="BackendMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        # Test Omniparser connection
        self._test_omniparser_connection()
        
        logger.info("Backend controller started successfully")
        logger.info(f"WebSocket clients: {self.websocket_handler.get_connected_clients_count()}")
        logger.info(f"Discovery targets: {len(self.discovery_service.target_ips)} IPs")
        
    def stop(self):
        """Stop all backend services"""
        if not self.running:
            return
            
        logger.info("Stopping backend controller...")
        self.running = False
        self._shutdown_event.set()
        
        try:
            # Stop run manager first (most important)
            if hasattr(self, 'run_manager'):
                self.run_manager.stop()
            
            # Stop discovery service
            if hasattr(self, 'discovery_service'):
                self.discovery_service.stop()
            
            # Wait for monitor thread with timeout
            if self.monitor_thread and self.monitor_thread.is_alive():
                logger.info("Waiting for monitor thread to finish...")
                self.monitor_thread.join(timeout=3)
                if self.monitor_thread.is_alive():
                    logger.warning("Monitor thread did not shut down gracefully")
                
            # Close communication clients
            try:
                if hasattr(self, 'sut_client'):
                    self.sut_client.close()
            except Exception as e:
                logger.error(f"Error closing SUT client: {e}")
                
            try:
                if hasattr(self, 'omniparser_client'):
                    self.omniparser_client.close()
            except Exception as e:
                logger.error(f"Error closing Omniparser client: {e}")
                
            # Force close SocketIO connections
            try:
                if hasattr(self, 'socketio'):
                    logger.info("Closing SocketIO connections...")
                    # Disconnect all clients first
                    self.socketio.emit('disconnect')
                    # Stop the server
                    self.socketio.stop()
                    logger.info("SocketIO stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping SocketIO: {e}")
                
            # Additional cleanup - force close any remaining threads
            import threading
            active_threads = threading.active_count()
            if active_threads > 1:
                logger.warning(f"Still have {active_threads} active threads after shutdown")
        
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        logger.info("Backend controller stopped")
    
    # WebSocket event callbacks for run management
    def _on_run_started(self, run_id: str, run_data: Dict[str, Any]):
        """Callback when a run starts"""
        logger.info(f"Run started: {run_id}")
        self.websocket_handler.broadcast_message('run_started', {
            'run_id': run_id,
            'run': run_data
        })
        
        # Also emit runs_update
        runs_data = self.run_manager.get_all_runs()
        self.websocket_handler.broadcast_message('runs_update', runs_data)
    
    def _on_run_progress(self, run_id: str, run_data: Dict[str, Any]):
        """Callback when run progress updates"""
        self.websocket_handler.broadcast_message('run_progress', {
            'run_id': run_id,
            'run': run_data
        })
        
        # Also emit runs_update for consistency
        runs_data = self.run_manager.get_all_runs()
        self.websocket_handler.broadcast_message('runs_update', runs_data)
    
    def _on_run_completed(self, run_id: str, run_data: Dict[str, Any]):
        """Callback when a run completes successfully"""
        logger.info(f"Run completed: {run_id}")
        self.websocket_handler.broadcast_message('run_completed', {
            'run_id': run_id,
            'run': run_data
        })
        
        # Emit updated runs data
        runs_data = self.run_manager.get_all_runs()
        self.websocket_handler.broadcast_message('runs_update', runs_data)
    
    def _on_run_failed(self, run_id: str, run_data: Dict[str, Any]):
        """Callback when a run fails"""
        logger.warning(f"Run failed: {run_id}")
        
        # Emit run failed event
        self.websocket_handler.broadcast_message('run_failed', {
            'run_id': run_id,
            'run': run_data
        })
        
        # Emit specific error notification for better UX
        error_message = run_data.get('error_message', 'Unknown error')
        error_type = 'automation_error'
        
        # Determine error type based on error message
        if error_message and isinstance(error_message, str):
            error_lower = error_message.lower()
            if 'file not found' in error_lower or 'executable not found' in error_lower:
                error_type = 'file_not_found'
            elif 'launch failed' in error_lower or 'failed to launch' in error_lower:
                error_type = 'launch_failed'
            elif 'connection' in error_lower or 'timeout' in error_lower:
                error_type = 'connection_error'
        
        self.websocket_handler.broadcast_message('error_notification', {
            'type': error_type,
            'title': 'Automation Run Failed',
            'message': error_message,
            'run_id': run_id,
            'game_name': run_data.get('game_name'),
            'sut_ip': run_data.get('sut_ip'),
            'timestamp': datetime.now().isoformat()
        })
        
        # Emit updated runs data
        runs_data = self.run_manager.get_all_runs()
        self.websocket_handler.broadcast_message('runs_update', runs_data)
        
    def run_server(self, host: str = None, port: int = None, debug: bool = None):
        """Run the Flask-SocketIO server"""
        host = host or self.config.host
        port = port or self.config.port
        debug = debug if debug is not None else self.config.debug
        
        try:
            self.start()
            logger.info(f"Starting server on {host}:{port} (debug={debug})")
            self.socketio.run(self.app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
        except KeyboardInterrupt:
            logger.info("Server interrupted by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
        finally:
            self.stop()
            
    def _monitor_loop(self):
        """Background monitoring loop"""
        logger.info("Monitor loop started")
        
        while self.running and not self._shutdown_event.wait(30):  # Check every 30 seconds
            try:
                self._perform_health_checks()
                self._emit_system_status()
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                
        logger.info("Monitor loop ended")
        
    def _perform_health_checks(self):
        """Perform periodic health checks"""
        # Check Omniparser status
        omniparser_status = self.omniparser_client.get_server_status()
        
        # Check device registry health
        device_stats = self.device_registry.get_device_stats()
        
        # Check discovery service health
        discovery_status = self.discovery_service.get_discovery_status()
        
        logger.debug(f"Health check - Omniparser: {omniparser_status['status']}, "
                    f"Devices: {device_stats['online_devices']}/{device_stats['total_devices']}, "
                    f"Discovery: {discovery_status['running']}")
                    
    def _emit_system_status(self):
        """Emit system status to WebSocket clients"""
        status = self.get_system_status()
        self.websocket_handler.broadcast_message('system_status', status)
        
    def _test_omniparser_connection(self):
        """Test connection to Omniparser on startup"""
        if self.omniparser_client.test_connection():
            logger.info("[OK] Omniparser connection successful")
            event_bus.emit(EventType.OMNIPARSER_STATUS_CHANGED, {
                "status": "online",
                "url": self.config.omniparser_url
            })
        else:
            logger.warning("[FAIL] Omniparser connection failed")
            event_bus.emit(EventType.OMNIPARSER_STATUS_CHANGED, {
                "status": "offline",
                "url": self.config.omniparser_url
            })
            
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        device_stats = self.device_registry.get_device_stats()
        discovery_status = self.discovery_service.get_discovery_status()
        omniparser_status = self.omniparser_client.get_server_status()
        
        return {
            "backend": {
                "running": self.running,
                "version": "2.0.0",
                "uptime": time.time(),  # Simplified uptime
                "websocket_clients": self.websocket_handler.get_connected_clients_count()
            },
            "discovery": discovery_status,
            "devices": device_stats,
            "omniparser": omniparser_status,
            "config": {
                "discovery_interval": self.config.discovery_interval,
                "discovery_timeout": self.config.discovery_timeout,
                "sut_port": self.config.sut_port
            }
        }
        
    def force_discovery_scan(self) -> Dict[str, Any]:
        """Force an immediate discovery scan"""
        logger.info("Forcing discovery scan via controller")
        return self.discovery_service.force_discovery_scan()
        
    def get_device_by_id(self, device_id: str):
        """Get device by ID"""
        return self.device_registry.get_device_by_id(device_id)
        
    def get_device_by_ip(self, ip: str):
        """Get device by IP"""
        return self.device_registry.get_device_by_ip(ip)
        
    def get_all_devices(self):
        """Get all devices"""
        return self.device_registry.get_all_devices()
        
    def get_online_devices(self):
        """Get online devices"""
        return self.device_registry.get_online_devices()
        
    def perform_sut_action(self, device_id: str, action: Dict[str, Any]):
        """Perform action on a SUT device"""
        device = self.device_registry.get_device_by_id(device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")
            
        if not device.is_online:
            raise ValueError(f"Device {device_id} is not online")
            
        # Mark device as busy
        self.device_registry.set_device_busy(device_id, f"Performing {action.get('type', 'action')}")
        
        try:
            # Perform the action
            result = self.sut_client.perform_action(device.ip, device.port, action)
            
            # Emit event
            event_bus.emit(EventType.AUTOMATION_STARTED if result.success else EventType.AUTOMATION_FAILED, {
                "device_id": device_id,
                "action": action,
                "result": result.data if result.success else {"error": result.error}
            })
            
            return result
            
        finally:
            # Mark device as available again
            self.device_registry.set_device_online(device_id)
            
    def analyze_screenshot_with_omniparser(self, screenshot_path: str):
        """Analyze screenshot using Omniparser"""
        return self.omniparser_client.analyze_screenshot(screenshot_path)
        
    # Context manager support
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()