"""
REST API routes for the backend system
"""

import logging
import json
import os
import tempfile
from flask import Blueprint, request, jsonify, send_file
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class APIRoutes:
    """API routes handler"""
    
    def __init__(self, device_registry, discovery_service, sut_client, omniparser_client, websocket_handler):
        self.device_registry = device_registry
        self.discovery_service = discovery_service
        self.sut_client = sut_client
        self.omniparser_client = omniparser_client
        self.websocket_handler = websocket_handler
        
    def register_routes(self, app):
        """Register all API routes with Flask app"""
        
        # System status and health
        @app.route('/api/status', methods=['GET'])
        def get_system_status():
            """Get comprehensive system status"""
            try:
                device_stats = self.device_registry.get_device_stats()
                discovery_status = self.discovery_service.get_discovery_status()
                omniparser_status = self.omniparser_client.get_server_status()
                
                return jsonify({
                    "status": "running",
                    "version": "2.0.0",
                    "websocket_clients": self.websocket_handler.get_connected_clients_count(),
                    "discovery": discovery_status,
                    "devices": device_stats,
                    "omniparser": omniparser_status
                })
            except Exception as e:
                logger.error(f"Error getting system status: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/health', methods=['GET'])
        def health_check():
            """Basic health check endpoint"""
            return jsonify({
                "status": "healthy",
                "timestamp": self.discovery_service.get_discovery_status()
            })
            
        # Device management
        @app.route('/api/devices', methods=['GET'])
        def get_devices():
            """Get all discovered devices"""
            try:
                devices = self.device_registry.get_all_devices()
                devices_data = []
                
                for device in devices:
                    device_data = {
                        "device_id": device.unique_id,
                        "ip": device.ip,
                        "port": device.port,
                        "hostname": device.hostname,
                        "status": device.status.value,
                        "capabilities": device.capabilities,
                        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                        "first_discovered": device.first_discovered.isoformat() if device.first_discovered else None,
                        "current_task": device.current_task,
                        "error_count": device.error_count,
                        "success_rate": device.success_rate,
                        "age_seconds": device.age_seconds,
                        "last_seen_seconds": device.last_seen_seconds
                    }
                    devices_data.append(device_data)
                    
                return jsonify({
                    "devices": devices_data,
                    "total_count": len(devices_data),
                    "online_count": len([d for d in devices if d.is_online])
                })
            except Exception as e:
                logger.error(f"Error getting devices: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/devices/<device_id>', methods=['GET'])
        def get_device_details(device_id):
            """Get detailed information about a specific device"""
            try:
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404
                    
                device_data = {
                    "device_id": device.unique_id,
                    "ip": device.ip,
                    "port": device.port,
                    "hostname": device.hostname,
                    "status": device.status.value,
                    "capabilities": device.capabilities,
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "first_discovered": device.first_discovered.isoformat() if device.first_discovered else None,
                    "current_task": device.current_task,
                    "error_count": device.error_count,
                    "total_pings": device.total_pings,
                    "successful_pings": device.successful_pings,
                    "success_rate": device.success_rate,
                    "age_seconds": device.age_seconds,
                    "last_seen_seconds": device.last_seen_seconds
                }
                
                return jsonify(device_data)
            except Exception as e:
                logger.error(f"Error getting device {device_id}: {e}")
                return jsonify({"error": str(e)}), 500
                
        # Discovery management
        @app.route('/api/discovery/scan', methods=['POST'])
        def force_discovery_scan():
            """Force an immediate discovery scan"""
            try:
                scan_result = self.discovery_service.force_discovery_scan()
                return jsonify({
                    "status": "success",
                    "scan_result": scan_result
                })
            except Exception as e:
                logger.error(f"Error forcing discovery scan: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/discovery/status', methods=['GET'])
        def get_discovery_status():
            """Get discovery service status"""
            try:
                status = self.discovery_service.get_discovery_status()
                return jsonify(status)
            except Exception as e:
                logger.error(f"Error getting discovery status: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/discovery/targets', methods=['POST'])
        def add_discovery_target():
            """Add IP to discovery targets"""
            try:
                data = request.get_json()
                ip = data.get('ip')
                
                if not ip:
                    return jsonify({"error": "IP address required"}), 400
                    
                self.discovery_service.add_target_ip(ip)
                return jsonify({"status": "success", "ip": ip})
            except Exception as e:
                logger.error(f"Error adding discovery target: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/discovery/targets/<ip>', methods=['DELETE'])
        def remove_discovery_target(ip):
            """Remove IP from discovery targets"""
            try:
                self.discovery_service.remove_target_ip(ip)
                return jsonify({"status": "success", "ip": ip})
            except Exception as e:
                logger.error(f"Error removing discovery target: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/discovery/network-info', methods=['GET'])
        def get_network_info():
            """Get comprehensive network information"""
            try:
                from ..discovery.network_utils import NetworkDiscovery
                network_info = NetworkDiscovery.get_network_info()
                return jsonify(network_info)
            except Exception as e:
                logger.error(f"Error getting network info: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/discovery/rediscover-networks', methods=['POST'])
        def rediscover_networks():
            """Force rediscovery of network ranges and restart scanning"""
            try:
                # Reinitialize target IPs with fresh network discovery
                self.discovery_service._initialize_target_ips()
                
                # Force an immediate scan
                stats = self.discovery_service.force_discovery_scan()
                
                return jsonify({
                    "status": "success", 
                    "message": "Network rediscovery completed",
                    "stats": stats
                })
            except Exception as e:
                logger.error(f"Error rediscovering networks: {e}")
                return jsonify({"error": str(e)}), 500
                
        # SUT communication
        @app.route('/api/sut/<device_id>/status', methods=['GET'])
        def get_sut_status(device_id):
            """Get status from a specific SUT"""
            try:
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404
                    
                result = self.sut_client.get_status(device.ip, device.port)
                
                if result.success:
                    return jsonify({
                        "status": "success",
                        "data": result.data,
                        "response_time": result.response_time
                    })
                else:
                    return jsonify({
                        "status": "error",
                        "error": result.error
                    }), 500
                    
            except Exception as e:
                logger.error(f"Error getting SUT status for {device_id}: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/sut/<device_id>/screenshot', methods=['GET'])
        def take_sut_screenshot(device_id):
            """Take screenshot from a specific SUT"""
            try:
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404
                    
                # Create temporary file for screenshot
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    
                result = self.sut_client.take_screenshot(device.ip, device.port, tmp_path)
                
                if result.success:
                    return send_file(tmp_path, mimetype='image/png')
                else:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                    return jsonify({
                        "status": "error",
                        "error": result.error
                    }), 500
                    
            except Exception as e:
                logger.error(f"Error taking screenshot from {device_id}: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/sut/<device_id>/action', methods=['POST'])
        def perform_sut_action(device_id):
            """Perform action on a specific SUT"""
            try:
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404
                    
                if not device.is_online:
                    return jsonify({"error": f"Device {device_id} is not online"}), 400
                    
                action_data = request.get_json()
                if not action_data:
                    return jsonify({"error": "Action data required"}), 400
                    
                # Mark device as busy
                self.device_registry.set_device_busy(device_id, f"Performing {action_data.get('type', 'action')}")
                
                try:
                    result = self.sut_client.perform_action(device.ip, device.port, action_data)
                    
                    if result.success:
                        return jsonify({
                            "status": "success",
                            "data": result.data,
                            "response_time": result.response_time
                        })
                    else:
                        return jsonify({
                            "status": "error",
                            "error": result.error
                        }), 500
                        
                finally:
                    # Mark device as available again
                    self.device_registry.set_device_online(device_id)
                    
            except Exception as e:
                logger.error(f"Error performing action on {device_id}: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/sut/<device_id>/launch', methods=['POST'])
        def launch_sut_application(device_id):
            """Launch application on a specific SUT"""
            try:
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404
                    
                if not device.is_online:
                    return jsonify({"error": f"Device {device_id} is not online"}), 400
                    
                launch_data = request.get_json()
                if not launch_data or 'path' not in launch_data:
                    return jsonify({"error": "Application path required"}), 400
                    
                app_path = launch_data['path']
                process_id = launch_data.get('process_id')
                
                result = self.sut_client.launch_application(device.ip, device.port, app_path, process_id)
                
                if result.success:
                    return jsonify({
                        "status": "success",
                        "data": result.data,
                        "response_time": result.response_time
                    })
                else:
                    return jsonify({
                        "status": "error",
                        "error": result.error
                    }), 500
                    
            except Exception as e:
                logger.error(f"Error launching application on {device_id}: {e}")
                return jsonify({"error": str(e)}), 500
                
        # Omniparser integration
        @app.route('/api/omniparser/status', methods=['GET'])
        def get_omniparser_status():
            """Get Omniparser server status"""
            try:
                status = self.omniparser_client.get_server_status()
                return jsonify(status)
            except Exception as e:
                logger.error(f"Error getting Omniparser status: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/omniparser/analyze', methods=['POST'])
        def analyze_with_omniparser():
            """Analyze screenshot with Omniparser"""
            try:
                if 'screenshot' not in request.files:
                    return jsonify({"error": "Screenshot file required"}), 400
                    
                file = request.files['screenshot']
                if file.filename == '':
                    return jsonify({"error": "No file selected"}), 400
                    
                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    file.save(tmp_file.name)
                    tmp_path = tmp_file.name
                    
                try:
                    result = self.omniparser_client.analyze_screenshot(tmp_path)
                    
                    if result.success:
                        response_data = {
                            "status": "success",
                            "elements": result.elements,
                            "response_time": result.response_time,
                            "element_count": len(result.elements or [])
                        }
                        
                        # If annotated image is requested, include it
                        if request.args.get('include_annotation') == 'true' and result.annotated_image_data:
                            import base64
                            response_data["annotated_image_base64"] = base64.b64encode(result.annotated_image_data).decode('utf-8')
                            
                        return jsonify(response_data)
                    else:
                        return jsonify({
                            "status": "error",
                            "error": result.error
                        }), 500
                        
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                        
            except Exception as e:
                logger.error(f"Error analyzing with Omniparser: {e}")
                return jsonify({"error": str(e)}), 500
                
        # WebSocket client management
        @app.route('/api/websocket/clients', methods=['GET'])
        def get_websocket_clients():
            """Get connected WebSocket clients info"""
            try:
                clients = self.websocket_handler.get_client_info()
                return jsonify({
                    "client_count": len(clients),
                    "clients": clients
                })
            except Exception as e:
                logger.error(f"Error getting WebSocket clients: {e}")
                return jsonify({"error": str(e)}), 500