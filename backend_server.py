#!/usr/bin/env python3
"""
Main Backend Server for Game Benchmarking Automation
Provides REST API and WebSocket interface for frontend communication
"""

import os
import time
import logging
import json
import uuid
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import yaml
import glob
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS

# Import existing modules
from modules.network import NetworkManager
from modules.screenshot import ScreenshotManager
from modules.gemma_client import GemmaClient
from modules.qwen_client import QwenClient
from modules.omniparser_client import OmniparserClient
from modules.annotator import Annotator
from modules.simple_automation import SimpleAutomation
from modules.game_launcher import GameLauncher

import requests
import sqlite3
import ipaddress
import concurrent.futures
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backend_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class SUTStatus:
    """SUT status information"""
    ip: str
    port: int
    status: str  # 'online', 'offline', 'busy'
    capabilities: List[str]
    last_seen: datetime
    current_task: Optional[str] = None

@dataclass
class GameConfig:
    """Game configuration information"""
    name: str
    path: str
    config_type: str  # 'steps' or 'state_machine'
    benchmark_duration: int
    resolution: str
    preset: str
    yaml_path: str

@dataclass
class AutomationRun:
    """Automation run status"""
    run_id: str
    game_name: str
    sut_ip: str
    status: str  # 'queued', 'running', 'completed', 'failed', 'stopped'
    progress: Dict[str, Any]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    results: Optional[Dict[str, Any]]
    error_message: Optional[str] = None
    
@dataclass
class SUTStatus:
    """Enhanced SUT status information with unique ID"""
    sut_id: str
    name: str
    ip: str
    port: int
    status: str  # 'online', 'offline', 'busy'
    capabilities: List[str]
    last_seen: datetime
    first_seen: datetime
    version: str
    system_info: Dict[str, Any]
    current_task: Optional[str] = None
    total_connections: int = 0

class GameBenchmarkServer:
    """Main backend server for game benchmarking automation"""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'your-secret-key-here'
        
        # Enable CORS
        CORS(self.app, origins="*")
        
        # Initialize SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        
        # Add SUT registry
        self.sut_registry = SUTRegistry()
        
        # Internal state
        self.suts: Dict[str, SUTStatus] = {}  # Active SUTs by sut_id
        self.sut_ip_mapping: Dict[str, str] = {}  # IP to sut_id mapping
        self.game_configs: Dict[str, GameConfig] = {}
        self.active_runs: Dict[str, AutomationRun] = {}
        self.run_history: List[AutomationRun] = []
        
        self.load_known_suts()
        
        # Configuration
        self.config_dir = "config/games"
        self.logs_dir = "logs"
        self.omniparser_url = "http://localhost:8000"
        
        # Background tasks
        self.discovery_thread = None
        self.stop_discovery = threading.Event()
        
        # Setup routes and event handlers
        self.setup_routes()
        self.setup_socket_handlers()
        
        # Initialize
        self.load_game_configurations()
        self.start_sut_discovery()
        
        logger.info("Game Benchmark Server initialized")
        
    def load_known_suts(self):
        """Load known SUTs from registry and mark them as offline"""
        try:
            known_suts = self.sut_registry.get_all_suts()
            
            for sut_data in known_suts:
                sut = SUTStatus(
                    sut_id=sut_data['sut_id'],
                    name=sut_data['name'],
                    ip=sut_data['ip'],
                    port=sut_data['port'],
                    status='offline',  # Start as offline, discovery will update
                    capabilities=sut_data['capabilities'],
                    last_seen=datetime.fromisoformat(sut_data['last_seen']) if sut_data['last_seen'] else datetime.now(),
                    first_seen=datetime.fromisoformat(sut_data['first_seen']) if sut_data['first_seen'] else datetime.now(),
                    version=sut_data['version'],
                    system_info=sut_data['system_info'],
                    total_connections=sut_data['total_connections']
                )
                
                self.suts[sut['sut_id']] = sut
                self.sut_ip_mapping[sut['ip']] = sut['sut_id']
            
            logger.info(f"Loaded {len(known_suts)} known SUTs from registry")
            
        except Exception as e:
            logger.error(f"Error loading known SUTs: {e}")


    
    def setup_routes(self):
        """Setup REST API routes"""
        
        @self.app.route('/api/status', methods=['GET'])
        def get_server_status():
            """Get server status"""
            return jsonify({
                'status': 'running',
                'version': '2.0.0',
                'uptime': time.time(),
                'active_runs': len(self.active_runs),
                'total_suts': len(self.suts),
                'online_suts': len([s for s in self.suts.values() if s.status == 'online'])
            })
        
        @self.app.route('/api/suts', methods=['GET'])
        def get_suts():
            """Get all discovered SUTs"""
            suts_data = {}
            for ip, sut in self.suts.items():
                suts_data[ip] = {
                    'ip': sut.ip,
                    'port': sut.port,
                    'status': sut.status,
                    'capabilities': sut.capabilities,
                    'last_seen': sut.last_seen.isoformat() if sut.last_seen else None,
                    'current_task': sut.current_task
                }
            return jsonify(suts_data)
        
        @self.app.route('/api/games', methods=['GET'])
        def get_games():
            """Get all available game configurations"""
            games_data = {}
            for name, config in self.game_configs.items():
                games_data[name] = asdict(config)
            return jsonify(games_data)
        
        @self.app.route('/api/games/reload', methods=['POST'])
        def reload_game_configs():
            """Reload game configurations from disk"""
            try:
                self.load_game_configurations()
                self.emit_game_configs_update()
                return jsonify({'status': 'success', 'count': len(self.game_configs)})
            except Exception as e:
                return jsonify({'status': 'error', 'error': str(e)}), 500
        
        @self.app.route('/api/runs', methods=['GET'])
        def get_runs():
            """Get all runs (active and history)"""
            active_data = {run_id: asdict(run) for run_id, run in self.active_runs.items()}
            history_data = [asdict(run) for run in self.run_history[-50:]]  # Last 50 runs
            
            return jsonify({
                'active': active_data,
                'history': history_data
            })
        
        @self.app.route('/api/runs', methods=['POST'])
        def start_automation_run():
            """Start new automation run"""
            try:
                data = request.get_json()
                
                # Validate request
                required_fields = ['sut_ip', 'game_name', 'iterations']
                for field in required_fields:
                    if field not in data:
                        return jsonify({'error': f'Missing required field: {field}'}), 400
                
                sut_ip = data['sut_ip']
                game_name = data['game_name']
                iterations = data['iterations']
                
                # Handle multiple games if game_name is a list (for future compatibility)
                if isinstance(game_name, list):
                    game_names = game_name
                else:
                    game_names = [game_name]
                
                # Check SUT availability
                if sut_ip not in self.suts or self.suts[sut_ip].status != 'online':
                    return jsonify({'error': f'SUT {sut_ip} is not available'}), 400
                
                # Check game configurations
                for gname in game_names:
                    if gname not in self.game_configs:
                        return jsonify({'error': f'Game configuration {gname} not found'}), 400
                
                # Create runs for each game
                run_ids = []
                for gname in game_names:
                    run_id = str(uuid.uuid4())
                    run = AutomationRun(
                        run_id=run_id,
                        game_name=gname,
                        sut_ip=sut_ip,
                        status='queued',
                        progress={'current_iteration': 0, 'total_iterations': iterations, 'current_step': 0},
                        start_time=None,
                        end_time=None,
                        results=None
                    )
                    
                    self.active_runs[run_id] = run
                    run_ids.append(run_id)
                    
                    # Start automation in background
                    threading.Thread(
                        target=self.execute_automation_run,
                        args=(run_id, {'sut_ip': sut_ip, 'game_name': gname, 'iterations': iterations}),
                        daemon=True
                    ).start()
                
                self.emit_runs_update()
                
                return jsonify({'status': 'success', 'run_ids': run_ids})
                
            except Exception as e:
                logger.error(f"Error starting automation run: {str(e)}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/runs/<run_id>/stop', methods=['POST'])
        def stop_automation_run(run_id):
            """Stop a running automation"""
            if run_id not in self.active_runs:
                return jsonify({'error': 'Run not found'}), 404
            
            run = self.active_runs[run_id]
            if run.status == 'running':
                run.status = 'stopped'
                run.end_time = datetime.now()
                # The actual stop signal will be handled in the automation thread
                
            self.emit_runs_update()
            return jsonify({'status': 'success'})
        
        @self.app.route('/api/runs/<run_id>/logs', methods=['GET'])
        def get_run_logs(run_id):
            """Get logs for a specific run"""
            # Implementation would read log files
            return jsonify({'logs': []})  # Placeholder
        
        @self.app.route('/api/omniparser/status', methods=['GET'])
        def check_omniparser_status():
            """Check omniparser server status"""
            try:
                import requests
                response = requests.get(f"{self.omniparser_url}/probe", timeout=5)
                if response.status_code == 200:
                    return jsonify({'status': 'online', 'url': self.omniparser_url})
                else:
                    return jsonify({'status': 'error', 'error': f'HTTP {response.status_code}'})
            except Exception as e:
                return jsonify({'status': 'offline', 'error': str(e)})
            
        @self.app.route('/api/suts/register', methods=['POST'])
        def register_sut():
            """Endpoint for SUTs to register themselves"""
            try:
                sut_data = request.get_json()
                
                # Validate required fields
                required_fields = ['sut_id', 'name', 'ip', 'port']
                for field in required_fields:
                    if field not in sut_data:
                        return jsonify({'error': f'Missing required field: {field}'}), 400
                
                # Update SUT information
                self.update_sut_from_discovery(
                    sut_data['ip'], 
                    sut_data['port'], 
                    sut_data
                )
                
                logger.info(f"SUT registered: {sut_data['name']} ({sut_data['sut_id']})")
                
                # Emit update
                self.emit_suts_update()
                
                return jsonify({'status': 'success', 'message': 'SUT registered successfully'})
                
            except Exception as e:
                logger.error(f"Error registering SUT: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/suts/heartbeat', methods=['POST'])
        def sut_heartbeat():
            """Endpoint for SUT heartbeat"""
            try:
                heartbeat_data = request.get_json()
                sut_id = heartbeat_data.get('sut_id')
                
                if sut_id in self.suts:
                    sut = self.suts[sut_id]
                    sut.last_seen = datetime.now()
                    sut.status = heartbeat_data.get('status', 'online')
                    sut.current_task = heartbeat_data.get('current_task')
                    
                    return jsonify({'status': 'success'})
                else:
                    return jsonify({'error': 'SUT not found'}), 404
                    
            except Exception as e:
                logger.error(f"Error processing heartbeat: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/suts/scan', methods=['POST'])
        def trigger_network_scan():
            """Manually trigger network scan for SUTs"""
            try:
                # Run discovery in background thread to avoid blocking
                discovery_thread = threading.Thread(
                    target=self.discover_suts_on_network,
                    daemon=True
                )
                discovery_thread.start()
                
                return jsonify({'status': 'success', 'message': 'Network scan initiated'})
                
            except Exception as e:
                logger.error(f"Error triggering network scan: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/suts/history/<sut_id>', methods=['GET'])
        def get_sut_history(sut_id):
            """Get connection history for a specific SUT"""
            try:
                conn = sqlite3.connect(self.sut_registry.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT timestamp, status, event_type, details
                    FROM sut_history 
                    WHERE sut_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 50
                ''', (sut_id,))
                
                history = []
                for row in cursor.fetchall():
                    history.append({
                        'timestamp': row[0],
                        'status': row[1],
                        'event_type': row[2],
                        'details': json.loads(row[3]) if row[3] else {}
                    })
                
                conn.close()
                return jsonify({'history': history})
                
            except Exception as e:
                logger.error(f"Error getting SUT history: {e}")
                return jsonify({'error': str(e)}), 500
        
        # Quick debug method - add this to your backend temporarily:
        @self.app.route('/api/debug/suts', methods=['GET'])
        def debug_suts():
            """Debug endpoint to see SUT data structure"""
            debug_data = {}
            for sut_id, sut in self.suts.items():
                debug_data[sut_id] = {
                    'sut_id': getattr(sut, 'sut_id', 'MISSING'),
                    'name': getattr(sut, 'name', 'MISSING'),
                    'ip': getattr(sut, 'ip', 'MISSING'),
                    'port': getattr(sut, 'port', 'MISSING'),
                    'status': getattr(sut, 'status', 'MISSING'),
                    'type': type(sut).__name__,
                    'attributes': dir(sut)
                }
            
            return jsonify({
                'suts_count': len(self.suts),
                'suts_data': debug_data,
                'suts_keys': list(self.suts.keys())
            })
        
        @self.app.route('/api/test/emit', methods=['POST'])
        def test_emit():
            """Test emitting SUT updates"""
            logger.info("Manual emit test triggered")
            self.emit_suts_update()
            return jsonify({'status': 'success', 'message': 'Emit triggered'})
    
    def setup_socket_handlers(self):
        """Setup WebSocket event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            logger.info(f"Client connected: {request.sid}")
            
            # Send initial data immediately upon connection
            try:
                # Send SUTs data with enhanced format
                suts_data = {}
                for sut_id, sut in self.suts.items():
                    suts_data[sut_id] = {
                        'sut_id': sut.sut_id,
                        'name': sut.name,
                        'ip': sut.ip,
                        'port': sut.port,
                        'status': sut.status,
                        'capabilities': sut.capabilities,
                        'last_seen': sut.last_seen.isoformat() if sut.last_seen else None,
                        'first_seen': sut.first_seen.isoformat() if sut.first_seen else None,
                        'current_task': sut.current_task,
                        'version': sut.version,
                        'system_info': sut.system_info,
                        'total_connections': sut.total_connections
                    }
                
                emit('suts_update', suts_data)
                emit('games_update', {name: asdict(config) for name, config in self.game_configs.items()})
                emit('runs_update', {
                    'active': {run_id: asdict(run) for run_id, run in self.active_runs.items()},
                    'history': [asdict(run) for run in self.run_history[-10:]]
                })
                
                logger.info(f"Sent initial data to client {request.sid}: {len(suts_data)} SUTs, {len(self.game_configs)} games")
                
            except Exception as e:
                logger.error(f"Error sending initial data to client: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info(f"Client disconnected: {request.sid}")
    
    def load_game_configurations(self):
        """Load game configurations from YAML files"""
        self.game_configs.clear()
        
        if not os.path.exists(self.config_dir):
            logger.warning(f"Config directory not found: {self.config_dir}")
            return
        
        yaml_files = glob.glob(os.path.join(self.config_dir, "*.yaml"))
        yaml_files.extend(glob.glob(os.path.join(self.config_dir, "*.yml")))
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r') as f:
                    config = yaml.safe_load(f)
                
                metadata = config.get('metadata', {})
                game_name = metadata.get('game_name', os.path.basename(yaml_file).replace('.yaml', ''))
                
                # Detect config type
                config_type = 'steps' if 'steps' in config else 'state_machine'
                
                game_config = GameConfig(
                    name=game_name,
                    path=metadata.get('path', ''),
                    config_type=config_type,
                    benchmark_duration=metadata.get('benchmark_duration', 120),
                    resolution=metadata.get('resolution', '1920x1080'),
                    preset=metadata.get('preset', 'High'),
                    yaml_path=yaml_file
                )
                
                self.game_configs[game_name] = game_config
                logger.info(f"Loaded game config: {game_name} ({config_type})")
                
            except Exception as e:
                logger.error(f"Failed to load config {yaml_file}: {str(e)}")
        
        logger.info(f"Loaded {len(self.game_configs)} game configurations")

    def enhanced_sut_discovery_loop(self):
        """Enhanced SUT discovery with network scanning"""
        while not self.stop_discovery.is_set():
            try:
                # Perform network scan
                self.discover_suts_on_network()
                
                # Check status of known SUTs that weren't recently seen
                current_time = datetime.now()
                for sut_id, sut in list(self.suts.items()):
                    time_since_last_seen = (current_time - sut.last_seen).total_seconds()
                    
                    if time_since_last_seen > 60:  # 60 seconds timeout
                        if sut.status == 'online':
                            sut.status = 'offline'
                            logger.info(f"SUT {sut.name} ({sut.ip}) marked as offline - last seen {int(time_since_last_seen)}s ago")
                            
                            # Add to history
                            try:
                                conn = sqlite3.connect(self.sut_registry.db_path)
                                cursor = conn.cursor()
                                cursor.execute('''
                                    INSERT INTO sut_history (sut_id, ip, status, event_type, details)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (
                                    sut_id, sut.ip, 'offline', 'timeout',
                                    json.dumps({"timeout_seconds": int(time_since_last_seen)})
                                ))
                                conn.commit()
                                conn.close()
                            except Exception as e:
                                logger.error(f"Error adding timeout event to history: {e}")
                
                # Emit updates if any changes occurred
                self.emit_suts_update()
                
                # Wait before next discovery cycle (30 seconds)
                self.stop_discovery.wait(30)
                
            except Exception as e:
                logger.error(f"Error in enhanced discovery loop: {e}")
                # Wait shorter time on error before retrying
                self.stop_discovery.wait(10)

    def discover_suts_on_network(self):
        """Scan network for SUTs"""
        try:
            # Get local network range
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Determine network range (assume /24 subnet)
            network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
            
            logger.debug(f"Scanning network {network} for SUTs...")
            
            def check_sut_at_ip(ip_str):
                """Check if there's a SUT at the given IP"""
                # Skip our own IP
                if ip_str == local_ip:
                    return None
                    
                for port in [8080, 8081, 8082, 8083]:  # Common SUT ports
                    try:
                        response = requests.get(
                            f"http://{ip_str}:{port}/status", 
                            timeout=2
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            if (data.get('status') == 'running' and 
                                'sut_id' in data and 
                                data.get('capabilities')):  # Validate it's actually a SUT
                                return ip_str, port, data
                    except requests.exceptions.RequestException:
                        # Expected for most IPs that don't have SUTs
                        continue
                    except Exception as e:
                        logger.debug(f"Unexpected error checking {ip_str}:{port} - {e}")
                        continue
                return None
            
            # Scan network in parallel with limited workers to avoid overwhelming network
            discovered_suts = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                # Submit all IP checks
                futures = [executor.submit(check_sut_at_ip, str(ip)) for ip in network.hosts()]
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(futures, timeout=45):
                    try:
                        result = future.result()
                        if result:
                            ip, port, sut_data = result
                            discovered_suts.append((ip, port, sut_data))
                            logger.info(f"Discovered SUT: {sut_data.get('name', 'Unknown')} at {ip}:{port}")
                    except concurrent.futures.TimeoutError:
                        logger.warning("Some network scans timed out")
                        break
                    except Exception as e:
                        logger.debug(f"Error processing scan result: {e}")
                        continue
            
            # Update SUT status for discovered SUTs
            for ip, port, sut_data in discovered_suts:
                self.update_sut_from_discovery(ip, port, sut_data)
            
            if discovered_suts:
                logger.info(f"Network scan complete. Found {len(discovered_suts)} active SUTs")
            else:
                logger.debug("Network scan complete. No active SUTs found")
            
        except Exception as e:
            logger.error(f"Error during network discovery: {e}")

    def update_sut_from_discovery(self, ip, port, sut_data):
        """Update SUT information from discovery data"""
        try:
            sut_id = sut_data['sut_id']
            current_time = datetime.now()
            
            # Register in persistent registry
            self.sut_registry.register_sut(sut_data)
            
            # Update in-memory tracking
            if sut_id in self.suts:
                # Update existing SUT
                sut = self.suts[sut_id]
                
                # Check if IP changed
                ip_changed = sut.ip != ip
                if ip_changed:
                    logger.info(f"SUT {sut.name} IP changed from {sut.ip} to {ip}")
                    # Update IP mapping
                    if sut.ip in self.sut_ip_mapping:
                        del self.sut_ip_mapping[sut.ip]
                    self.sut_ip_mapping[ip] = sut_id
                
                # Update SUT data
                sut.ip = ip
                sut.port = port
                was_offline = sut.status == 'offline'
                sut.status = 'online'
                sut.last_seen = current_time
                sut.version = sut_data.get('version', '')
                sut.capabilities = sut_data.get('capabilities', [])
                sut.system_info = sut_data.get('system_info', {})
                
                # Log status change
                if was_offline:
                    logger.info(f"SUT {sut.name} ({ip}) came back online")
                    
            else:
                # Create new SUT
                sut = SUTStatus(
                    sut_id=sut_id,
                    name=sut_data.get('name', f"SUT-{sut_id[:8]}"),
                    ip=ip,
                    port=port,
                    status='online',
                    capabilities=sut_data.get('capabilities', []),
                    last_seen=current_time,
                    first_seen=current_time,
                    version=sut_data.get('version', ''),
                    system_info=sut_data.get('system_info', {}),
                    total_connections=1
                )
                self.suts[sut_id] = sut
                logger.info(f"New SUT discovered: {sut.name} ({ip}:{port})")
            
            # Update IP mapping
            self.sut_ip_mapping[ip] = sut_id
            
            # Add discovery event to history
            try:
                conn = sqlite3.connect(self.sut_registry.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO sut_history (sut_id, ip, status, event_type, details)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    sut_id, ip, 'online', 'discovery',
                    json.dumps({
                        "discovery_method": "network_scan",
                        "port": port,
                        "version": sut_data.get('version', ''),
                        "capabilities_count": len(sut_data.get('capabilities', []))
                    })
                ))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error adding discovery event to history: {e}")

            logger.info(f"SUT {sut_data.get('name', 'Unknown')} updated, emitting update")
            self.emit_suts_update()
            
        except Exception as e:
            logger.error(f"Error updating SUT from discovery: {e}")

    def emit_suts_update(self):
        """Emit SUT status updates via WebSocket"""
        try:
            suts_data = {}
            for sut_id, sut in self.suts.items():
                suts_data[sut_id] = {
                    'sut_id': sut.sut_id,
                    'name': sut.name,
                    'ip': sut.ip,
                    'port': sut.port,
                    'status': sut.status,
                    'capabilities': sut.capabilities,
                    'last_seen': sut.last_seen.isoformat() if sut.last_seen else None,
                    'first_seen': sut.first_seen.isoformat() if sut.first_seen else None,
                    'current_task': sut.current_task,
                    'version': sut.version,
                    'system_info': sut.system_info,
                    'total_connections': sut.total_connections
                }
            
            logger.info(f"Emitting SUT update with {len(suts_data)} SUTs: {list(suts_data.keys())}")
            self.socketio.emit('suts_update', suts_data)  # Remove room='updates' for now
        
        except Exception as e:
            logger.error(f"Error emitting SUT updates: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def start_sut_discovery(self):
        """Start enhanced SUT discovery background thread"""
        self.discovery_thread = threading.Thread(target=self.enhanced_sut_discovery_loop, daemon=True)
        self.discovery_thread.start()
        logger.info("Started enhanced SUT discovery thread with network scanning")
    
    
    
    def check_sut_status(self, ip: str, port: int = 8080):
        """Check status of a specific SUT"""
        try:
            import requests
            response = requests.get(f"http://{ip}:{port}/status", timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                capabilities = data.get('capabilities', ['basic_automation'])
                
                # Check if SUT is busy
                current_status = 'online'
                current_task = None
                
                for run in self.active_runs.values():
                    if run.sut_ip == ip and run.status == 'running':
                        current_status = 'busy'
                        current_task = f"Running {run.game_name}"
                        break
                
                self.suts[ip] = SUTStatus(
                    ip=ip,
                    port=port,
                    status=current_status,
                    capabilities=capabilities,
                    last_seen=datetime.now(),
                    current_task=current_task
                )
            else:
                # Mark as offline if previously online
                if ip in self.suts:
                    self.suts[ip].status = 'offline'
                    
        except Exception as e:
            # Mark as offline
            if ip in self.suts:
                self.suts[ip].status = 'offline'
            logger.debug(f"SUT {ip} not reachable: {str(e)}")
    
    def execute_automation_run(self, run_id: str, run_config: Dict[str, Any]):
        """Execute automation run in background thread"""
        run = self.active_runs[run_id]
        
        try:
            run.status = 'running'
            run.start_time = datetime.now()
            self.emit_runs_update()
            
            # Mark SUT as busy
            if run.sut_ip in self.suts:
                self.suts[run.sut_ip].status = 'busy'
                self.suts[run.sut_ip].current_task = f"Running {run.game_name}"
                self.emit_suts_update()
            
            game_config = self.game_configs[run.game_name]
            iterations = run_config['iterations']
            
            # Initialize components
            network = NetworkManager(run.sut_ip, 8080)
            screenshot_mgr = ScreenshotManager(network)
            
            # Initialize vision model (default to omniparser for now)
            vision_model = OmniparserClient(self.omniparser_url)
            
            annotator = Annotator()
            game_launcher = GameLauncher(network)
            
            # Create run directory
            run_dir = f"{self.logs_dir}/{run.game_name}/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.makedirs(run_dir, exist_ok=True)
            os.makedirs(f"{run_dir}/screenshots", exist_ok=True)
            os.makedirs(f"{run_dir}/annotated", exist_ok=True)
            
            # Execute iterations
            successful_runs = 0
            
            for iteration in range(1, iterations + 1):
                if run.status == 'stopped':
                    logger.info(f"Run {run_id} stopped by user")
                    break
                
                run.progress['current_iteration'] = iteration
                self.emit_run_progress_update(run_id)
                
                logger.info(f"Starting iteration {iteration}/{iterations} for {run.game_name}")
                
                try:
                    # Create stop event for this iteration
                    stop_event = threading.Event()
                    if run.status == 'stopped':
                        stop_event.set()
                    
                    # Run automation
                    automation = SimpleAutomation(
                        config_path=game_config.yaml_path,
                        network=network,
                        screenshot_mgr=screenshot_mgr,
                        vision_model=vision_model,
                        stop_event=stop_event,
                        run_dir=run_dir,
                        annotator=annotator
                    )
                    
                    success = automation.run()
                    
                    if success:
                        successful_runs += 1
                        logger.info(f"Iteration {iteration} completed successfully")
                    else:
                        logger.warning(f"Iteration {iteration} failed")
                    
                except Exception as e:
                    logger.error(f"Error in iteration {iteration}: {str(e)}")
            
            # Complete the run
            run.status = 'completed'
            run.end_time = datetime.now()
            run.results = {
                'total_iterations': iterations,
                'successful_runs': successful_runs,
                'success_rate': successful_runs / iterations if iterations > 0 else 0,
                'run_directory': run_dir
            }
            
            logger.info(f"Run {run_id} completed: {successful_runs}/{iterations} successful")
            
        except Exception as e:
            logger.error(f"Error in automation run {run_id}: {str(e)}")
            run.status = 'failed'
            run.end_time = datetime.now()
            run.error_message = str(e)
        
        finally:
            # Move to history and cleanup
            self.run_history.append(run)
            if run_id in self.active_runs:
                del self.active_runs[run_id]
            
            # Mark SUT as available again
            if run.sut_ip in self.suts:
                self.suts[run.sut_ip].status = 'online'
                self.suts[run.sut_ip].current_task = None
            
            self.emit_runs_update()
            self.emit_suts_update()
    
    def emit_games_update(self):
        """Emit game configurations updates via WebSocket"""
        games_data = {name: asdict(config) for name, config in self.game_configs.items()}
        self.socketio.emit('games_update', games_data, room='updates')
    
    def emit_game_configs_update(self):
        """Emit game configurations updates via WebSocket"""
        self.emit_games_update()
    
    def emit_runs_update(self):
        """Emit runs updates via WebSocket"""
        runs_data = {
            'active': {run_id: asdict(run) for run_id, run in self.active_runs.items()},
            'history': [asdict(run) for run in self.run_history[-10:]]
        }
        self.socketio.emit('runs_update', runs_data, room='updates')
    
    def emit_run_progress_update(self, run_id: str):
        """Emit specific run progress update"""
        if run_id in self.active_runs:
            run_data = asdict(self.active_runs[run_id])
            self.socketio.emit('run_progress', {'run_id': run_id, 'run': run_data}, room='updates')
    
    def run_server(self, host='0.0.0.0', port=5000, debug=False):
        """Start the server"""
        logger.info(f"Starting Game Benchmark Server on {host}:{port}")
        self.socketio.run(self.app, host=host, port=port, debug=debug)
    
    def shutdown(self):
        """Shutdown the server gracefully"""
        logger.info("Shutting down Game Benchmark Server")
        self.stop_discovery.set()
        if self.discovery_thread:
            self.discovery_thread.join(timeout=5)

class SUTRegistry:
    """Persistent registry for discovered SUTs"""
    
    def __init__(self, db_path="suts_registry.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the SUT registry database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suts (
                sut_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ip TEXT NOT NULL,
                port INTEGER NOT NULL,
                version TEXT,
                system_info TEXT,
                capabilities TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_connections INTEGER DEFAULT 1,
                notes TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sut_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sut_id TEXT,
                ip TEXT,
                status TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT,
                details TEXT,
                FOREIGN KEY (sut_id) REFERENCES suts (sut_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("SUT registry database initialized")
    
    def register_sut(self, sut_data):
        """Register or update a SUT in the registry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if SUT exists
        cursor.execute('SELECT sut_id, total_connections FROM suts WHERE sut_id = ?', (sut_data['sut_id'],))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing SUT
            cursor.execute('''
                UPDATE suts SET 
                    name = ?, ip = ?, port = ?, version = ?, 
                    system_info = ?, capabilities = ?, last_seen = CURRENT_TIMESTAMP,
                    total_connections = ?
                WHERE sut_id = ?
            ''', (
                sut_data['name'], sut_data['ip'], sut_data['port'], 
                sut_data.get('version', ''), json.dumps(sut_data.get('system_info', {})),
                json.dumps(sut_data.get('capabilities', [])),
                existing[1] + 1,  # Increment connection count
                sut_data['sut_id']
            ))
        else:
            # Insert new SUT
            cursor.execute('''
                INSERT INTO suts (sut_id, name, ip, port, version, system_info, capabilities)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                sut_data['sut_id'], sut_data['name'], sut_data['ip'], sut_data['port'],
                sut_data.get('version', ''), json.dumps(sut_data.get('system_info', {})),
                json.dumps(sut_data.get('capabilities', []))
            ))
        
        # Add to history
        cursor.execute('''
            INSERT INTO sut_history (sut_id, ip, status, event_type, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            sut_data['sut_id'], sut_data['ip'], 'registered', 'registration',
            json.dumps(sut_data)
        ))
        
        conn.commit()
        conn.close()
    
    def get_all_suts(self):
        """Get all SUTs from registry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sut_id, name, ip, port, version, system_info, capabilities,
                   first_seen, last_seen, total_connections
            FROM suts ORDER BY last_seen DESC
        ''')
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'sut_id': row[0],
                'name': row[1],
                'ip': row[2],
                'port': row[3],
                'version': row[4],
                'system_info': json.loads(row[5]) if row[5] else {},
                'capabilities': json.loads(row[6]) if row[6] else [],
                'first_seen': row[7],
                'last_seen': row[8],
                'total_connections': row[9]
            })
        
        conn.close()
        return results

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Game Benchmark Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    server = GameBenchmarkServer()
    
    try:
        server.run_server(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    finally:
        server.shutdown()

if __name__ == '__main__':
    main()