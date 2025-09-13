# -*- coding: utf-8 -*-
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
    
    def __init__(self, device_registry, discovery_service, sut_client, omniparser_client, websocket_handler, game_manager=None):
        self.device_registry = device_registry
        self.discovery_service = discovery_service
        self.sut_client = sut_client
        self.omniparser_client = omniparser_client
        self.websocket_handler = websocket_handler
        self.game_manager = game_manager
        
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

        # Game configuration management
        @app.route('/api/games', methods=['GET'])
        def get_games():
            """Get all game configurations"""
            try:
                if not self.game_manager:
                    return jsonify({"games": {}})
                
                games = self.game_manager.to_dict()
                return jsonify({"games": games})
            except Exception as e:
                logger.error(f"Error getting games: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/<game_name>', methods=['GET'])
        def get_game(game_name):
            """Get specific game configuration"""
            try:
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500
                
                game = self.game_manager.get_game(game_name)
                if not game:
                    return jsonify({"error": f"Game '{game_name}' not found"}), 404
                
                return jsonify({"game": game.__dict__})
            except Exception as e:
                logger.error(f"Error getting game {game_name}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/reload', methods=['POST'])
        def reload_games():
            """Reload game configurations from disk"""
            try:
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500
                
                stats = self.game_manager.reload_configurations()
                
                # Emit updated games to WebSocket clients
                games_data = self.game_manager.to_dict()
                self.websocket_handler.broadcast_message('games_update', games_data)
                
                return jsonify(stats)
            except Exception as e:
                logger.error(f"Error reloading games: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/stats', methods=['GET'])
        def get_game_stats():
            """Get game statistics"""
            try:
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500
                
                stats = self.game_manager.get_game_stats()
                return jsonify(stats)
            except Exception as e:
                logger.error(f"Error getting game stats: {e}")
                return jsonify({"error": str(e)}), 500

        # Automation runs management
        @app.route('/api/runs', methods=['POST'])
        def start_automation_run():
            """Start a new automation run"""
            try:
                logger.info(f"Received start automation run request from {request.remote_addr}")
                data = request.get_json()
                logger.info(f"Request data: {data}")
                if not data:
                    logger.warning("No request data provided")
                    return jsonify({"error": "Request data required"}), 400
                
                # Validate required fields
                sut_ip = data.get('sut_ip')
                game_name = data.get('game_name')
                iterations = data.get('iterations', 1)
                
                if not sut_ip or not game_name:
                    return jsonify({"error": "sut_ip and game_name are required"}), 400
                
                # Validate SUT exists and is online
                device = self.device_registry.get_device_by_ip(sut_ip)
                if not device:
                    return jsonify({"error": f"SUT {sut_ip} not found"}), 404
                
                if not device.is_online:
                    return jsonify({"error": f"SUT {sut_ip} is not online"}), 400
                
                # Validate game exists
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500
                
                game = self.game_manager.get_game(game_name)
                if not game:
                    return jsonify({"error": f"Game '{game_name}' not found"}), 404
                
                # Queue the run (run_manager is passed from controller)
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    logger.error("Run manager not available when trying to start run")
                    return jsonify({"error": "Run manager not available"}), 500
                
                logger.info(f"Run manager available, queuing run: {game_name} on {sut_ip} ({iterations} iterations)")
                
                try:
                    run_id = self.run_manager.queue_run(
                        game_name=game_name,
                        sut_ip=sut_ip,
                        sut_device_id=device.unique_id,
                        iterations=int(iterations)
                    )
                    logger.info(f"Successfully queued run {run_id}")
                    
                    return jsonify({
                        "status": "success",
                        "run_id": run_id,
                        "message": f"Started automation run for {game_name} on {sut_ip}"
                    })
                    
                except Exception as queue_error:
                    logger.error(f"Failed to queue run: {queue_error}", exc_info=True)
                    return jsonify({"error": f"Failed to queue run: {str(queue_error)}"}), 500
                
            except Exception as e:
                logger.error(f"Error starting automation run: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs', methods=['GET'])
        def get_automation_runs():
            """Get all automation runs (active and history)"""
            try:
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"active": {}, "history": []})
                
                runs_data = self.run_manager.get_all_runs()
                return jsonify(runs_data)
                
            except Exception as e:
                logger.error(f"Error getting automation runs: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/<run_id>', methods=['GET'])
        def get_automation_run(run_id):
            """Get specific automation run status"""
            try:
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not available"}), 500
                
                run_data = self.run_manager.get_run_status(run_id)
                if not run_data:
                    return jsonify({"error": f"Run {run_id} not found"}), 404
                
                return jsonify(run_data)
                
            except Exception as e:
                logger.error(f"Error getting run {run_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/<run_id>/stop', methods=['POST'])
        def stop_automation_run(run_id):
            """Stop a specific automation run"""
            try:
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not available"}), 500
                
                success = self.run_manager.stop_run(run_id)
                if not success:
                    return jsonify({"error": f"Run {run_id} not found or not running"}), 404
                
                return jsonify({
                    "status": "success",
                    "message": f"Stopped run {run_id}"
                })
                
            except Exception as e:
                logger.error(f"Error stopping run {run_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/stats', methods=['GET'])
        def get_runs_stats():
            """Get automation runs statistics"""
            try:
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({
                        "active_runs": 0,
                        "queued_runs": 0,
                        "total_history": 0,
                        "completed_runs": 0,
                        "failed_runs": 0
                    })
                
                stats = self.run_manager.get_stats()
                return jsonify(stats)
                
            except Exception as e:
                logger.error(f"Error getting runs stats: {e}")
                return jsonify({"error": str(e)}), 500

        # SUT Pairing Management
        @app.route('/api/suts/pair', methods=['POST'])
        def pair_sut():
            """Pair a SUT device"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({"error": "Request data required"}), 400
                
                device_id = data.get('device_id')
                nickname = data.get('nickname', '')
                
                if not device_id:
                    return jsonify({"error": "device_id is required"}), 400
                
                # Verify SUT exists in device registry
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"SUT {device_id} not found"}), 404
                
                # Update SUT info in database first
                if hasattr(self, 'db') and self.db:
                    self.db.upsert_sut(
                        device_id=device.unique_id,
                        ip_address=device.ip,
                        port=device.port,
                        hostname=device.hostname,
                        capabilities=device.capabilities,
                        status='online' if device.is_online else 'offline'
                    )
                    
                    # Now pair the SUT
                    success = self.db.pair_sut(device_id, nickname)
                    if success:
                        # Broadcast update to WebSocket clients
                        paired_suts = self.db.get_paired_suts()
                        self.websocket_handler.broadcast_message('paired_suts_update', paired_suts)
                        
                        return jsonify({
                            "status": "success",
                            "message": f"SUT {device_id} paired successfully",
                            "nickname": nickname
                        })
                    else:
                        return jsonify({"error": "Failed to pair SUT"}), 500
                else:
                    return jsonify({"error": "Database not available"}), 500
                
            except Exception as e:
                logger.error(f"Error pairing SUT: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/suts/unpair/<device_id>', methods=['POST'])
        def unpair_sut(device_id):
            """Unpair a SUT device (forget device)"""
            try:
                if hasattr(self, 'db') and self.db:
                    success = self.db.unpair_sut(device_id)
                    if success:
                        # Broadcast update to WebSocket clients
                        paired_suts = self.db.get_paired_suts()
                        self.websocket_handler.broadcast_message('paired_suts_update', paired_suts)
                        
                        return jsonify({
                            "status": "success",
                            "message": f"SUT {device_id} unpaired successfully"
                        })
                    else:
                        return jsonify({"error": f"SUT {device_id} not found or not paired"}), 404
                else:
                    return jsonify({"error": "Database not available"}), 500
                
            except Exception as e:
                logger.error(f"Error unpairing SUT {device_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/suts/paired', methods=['GET'])
        def get_paired_suts():
            """Get all paired SUTs"""
            try:
                if hasattr(self, 'db') and self.db:
                    paired_suts = self.db.get_paired_suts()
                    return jsonify({
                        "paired_suts": paired_suts,
                        "count": len(paired_suts)
                    })
                else:
                    return jsonify({"paired_suts": [], "count": 0})
                
            except Exception as e:
                logger.error(f"Error getting paired SUTs: {e}")
                return jsonify({"error": str(e)}), 500