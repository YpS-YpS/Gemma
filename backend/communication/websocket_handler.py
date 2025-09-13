# -*- coding: utf-8 -*-
"""
WebSocket handler for real-time frontend communication
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional
from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from dataclasses import asdict

from ..core.events import event_bus, EventType, Event
from ..discovery.device_registry import DeviceRegistry, SUTDevice
from ..core.game_manager import GameConfigManager

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Handles WebSocket connections and real-time updates for frontend"""
    
    def __init__(self, socketio: SocketIO, device_registry: DeviceRegistry, game_manager: GameConfigManager = None):
        self.socketio = socketio
        self.registry = device_registry
        self.game_manager = game_manager
        self.connected_clients: Dict[str, Dict[str, Any]] = {}
        
        # Subscribe to events
        self._subscribe_to_events()
        
        # Register socket event handlers
        self._register_handlers()
        
        logger.info("WebSocket handler initialized")
        
    def _subscribe_to_events(self):
        """Subscribe to system events for real-time updates"""
        event_bus.subscribe(EventType.SUT_DISCOVERED, self._on_sut_discovered)
        event_bus.subscribe(EventType.SUT_ONLINE, self._on_sut_online)
        event_bus.subscribe(EventType.SUT_OFFLINE, self._on_sut_offline)
        event_bus.subscribe(EventType.SUT_STATUS_CHANGED, self._on_sut_status_changed)
        event_bus.subscribe(EventType.AUTOMATION_STARTED, self._on_automation_started)
        event_bus.subscribe(EventType.AUTOMATION_COMPLETED, self._on_automation_completed)
        event_bus.subscribe(EventType.AUTOMATION_FAILED, self._on_automation_failed)
        
    def _register_handlers(self):
        """Register WebSocket event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect(auth=None):
            client_id = request.sid
            logger.info(f"Frontend client connected: {client_id}")
            
            # Store client info
            self.connected_clients[client_id] = {
                "connected_at": time.time(),
                "subscriptions": set()
            }
            
            # Join general updates room
            join_room('general_updates')
            
            # Send initial data
            self._send_initial_data(client_id)
            
            emit('connection_status', {
                'status': 'connected',
                'client_id': client_id,
                'timestamp': time.time()
            })
            
        @self.socketio.on('disconnect')
        def handle_disconnect():
            client_id = request.sid
            logger.info(f"Frontend client disconnected: {client_id}")
            
            # Clean up client data
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
                
        @self.socketio.on('subscribe_to_device')
        def handle_device_subscription(data):
            """Subscribe to specific device updates"""
            client_id = request.sid
            device_id = data.get('device_id')
            
            if device_id and client_id in self.connected_clients:
                room_name = f"device_{device_id}"
                join_room(room_name)
                self.connected_clients[client_id]["subscriptions"].add(device_id)
                
                logger.debug(f"Client {client_id} subscribed to device {device_id}")
                emit('subscription_status', {
                    'device_id': device_id,
                    'subscribed': True
                })
                
        @self.socketio.on('unsubscribe_from_device')
        def handle_device_unsubscription(data):
            """Unsubscribe from specific device updates"""
            client_id = request.sid
            device_id = data.get('device_id')
            
            if device_id and client_id in self.connected_clients:
                room_name = f"device_{device_id}"
                leave_room(room_name)
                self.connected_clients[client_id]["subscriptions"].discard(device_id)
                
                logger.debug(f"Client {client_id} unsubscribed from device {device_id}")
                emit('subscription_status', {
                    'device_id': device_id,
                    'subscribed': False
                })
                
        @self.socketio.on('request_device_list')
        def handle_device_list_request():
            """Send current device list to requesting client"""
            self._send_device_list()
            
        @self.socketio.on('request_device_details')
        def handle_device_details_request(data):
            """Send detailed info for specific device"""
            device_id = data.get('device_id')
            if device_id:
                device = self.registry.get_device_by_id(device_id)
                if device:
                    emit('device_details', self._serialize_device(device))
                else:
                    emit('error', {'message': f'Device {device_id} not found'})
                    
        @self.socketio.on('ping')
        def handle_ping():
            """Handle ping from client"""
            emit('pong', {'timestamp': time.time()})
            
    def _send_initial_data(self, client_id: str):
        """Send initial data to newly connected client"""
        try:
            # Send current device list
            devices_data = self._get_devices_data()
            self.socketio.emit('initial_devices', devices_data, room=client_id)
            
            # Send discovery status
            discovery_status = self._get_discovery_status()
            self.socketio.emit('discovery_status', discovery_status, room=client_id)
            
            # Send game configurations
            if self.game_manager:
                games_data = self._get_games_data()
                self.socketio.emit('games_update', games_data, room=client_id)
            
            logger.debug(f"Sent initial data to client {client_id}")
            
        except Exception as e:
            logger.error(f"Error sending initial data to {client_id}: {e}")
            
    def _get_devices_data(self) -> Dict[str, Any]:
        """Get serialized devices data"""
        devices = self.registry.get_all_devices()
        return {
            'devices': [self._serialize_device(device) for device in devices],
            'total_count': len(devices),
            'online_count': len([d for d in devices if d.is_online]),
            'timestamp': time.time()
        }
        
    def _get_discovery_status(self) -> Dict[str, Any]:
        """Get discovery status"""
        stats = self.registry.get_device_stats()
        return {
            'discovery_active': True,  # Will be set by controller
            'last_scan': time.time(),
            **stats
        }
        
    def _get_games_data(self) -> Dict[str, Any]:
        """Get serialized games data"""
        if not self.game_manager:
            return {}
        return self.game_manager.to_dict()
        
    def _serialize_device(self, device: SUTDevice) -> Dict[str, Any]:
        """Serialize device for JSON transmission"""
        data = asdict(device)
        
        # Convert datetime objects to ISO strings
        if device.last_seen:
            data['last_seen'] = device.last_seen.isoformat()
        if device.first_discovered:
            data['first_discovered'] = device.first_discovered.isoformat()
            
        # Convert enum to string
        data['status'] = device.status.value
        
        # Add computed properties
        data['success_rate'] = device.success_rate
        data['age_seconds'] = device.age_seconds
        data['last_seen_seconds'] = device.last_seen_seconds
        
        return data
        
    def _send_device_list(self):
        """Send current device list to all clients"""
        devices_data = self._get_devices_data()
        self.socketio.emit('devices_update', devices_data, room='general_updates')
        logger.debug("Sent device list update to all clients")
        
    # Event handlers for system events
    def _on_sut_discovered(self, event: Event):
        """Handle SUT discovered event"""
        device_id = event.data.get('device_id')
        device = self.registry.get_device_by_id(device_id)
        
        if device:
            update_data = {
                'event': 'device_discovered',
                'device': self._serialize_device(device),
                'timestamp': event.timestamp.isoformat()
            }
            
            self.socketio.emit('device_event', update_data, room='general_updates')
            logger.debug(f"Sent device discovered event for {device_id}")
            
    def _on_sut_online(self, event: Event):
        """Handle SUT online event"""
        device_id = event.data.get('device_id')
        device = self.registry.get_device_by_id(device_id)
        
        if device:
            update_data = {
                'event': 'device_online',
                'device': self._serialize_device(device),
                'timestamp': event.timestamp.isoformat()
            }
            
            self.socketio.emit('device_event', update_data, room='general_updates')
            self.socketio.emit('device_event', update_data, room=f'device_{device_id}')
            logger.debug(f"Sent device online event for {device_id}")
            
    def _on_sut_offline(self, event: Event):
        """Handle SUT offline event"""
        device_id = event.data.get('device_id')
        device = self.registry.get_device_by_id(device_id)
        
        if device:
            update_data = {
                'event': 'device_offline',
                'device': self._serialize_device(device),
                'timestamp': event.timestamp.isoformat()
            }
            
            self.socketio.emit('device_event', update_data, room='general_updates')
            self.socketio.emit('device_event', update_data, room=f'device_{device_id}')
            logger.debug(f"Sent device offline event for {device_id}")
            
    def _on_sut_status_changed(self, event: Event):
        """Handle SUT status change event"""
        device_id = event.data.get('device_id')
        device = self.registry.get_device_by_id(device_id)
        
        if device:
            update_data = {
                'event': 'device_status_changed',
                'device': self._serialize_device(device),
                'old_status': event.data.get('old_status'),
                'new_status': event.data.get('new_status'),
                'timestamp': event.timestamp.isoformat()
            }
            
            self.socketio.emit('device_event', update_data, room='general_updates')
            self.socketio.emit('device_event', update_data, room=f'device_{device_id}')
            logger.debug(f"Sent device status change event for {device_id}")
            
    def _on_automation_started(self, event: Event):
        """Handle automation started event"""
        automation_data = {
            'event': 'automation_started',
            'data': event.data,
            'timestamp': event.timestamp.isoformat()
        }
        
        self.socketio.emit('automation_event', automation_data, room='general_updates')
        
    def _on_automation_completed(self, event: Event):
        """Handle automation completed event"""
        automation_data = {
            'event': 'automation_completed',
            'data': event.data,
            'timestamp': event.timestamp.isoformat()
        }
        
        self.socketio.emit('automation_event', automation_data, room='general_updates')
        
    def _on_automation_failed(self, event: Event):
        """Handle automation failed event"""
        automation_data = {
            'event': 'automation_failed',
            'data': event.data,
            'timestamp': event.timestamp.isoformat()
        }
        
        self.socketio.emit('automation_event', automation_data, room='general_updates')
        
    def broadcast_message(self, event_name: str, data: Dict[str, Any], room: str = 'general_updates'):
        """Broadcast a message to specified room"""
        self.socketio.emit(event_name, data, room=room)
        
    def get_connected_clients_count(self) -> int:
        """Get number of connected clients"""
        return len(self.connected_clients)
        
    def get_client_info(self) -> List[Dict[str, Any]]:
        """Get information about connected clients"""
        return [
            {
                'client_id': client_id,
                'connected_at': info['connected_at'],
                'subscriptions': list(info['subscriptions'])
            }
            for client_id, info in self.connected_clients.items()
        ]