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

class GameBenchmarkServer:
    """Main backend server for game benchmarking automation"""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'your-secret-key-here'
        
        # Enable CORS
        CORS(self.app, origins="*")
        
        # Initialize SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        
        # Internal state
        self.suts: Dict[str, SUTStatus] = {}
        self.game_configs: Dict[str, GameConfig] = {}
        self.active_runs: Dict[str, AutomationRun] = {}
        self.run_history: List[AutomationRun] = []
        
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
    
    def setup_socket_handlers(self):
        """Setup WebSocket event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            logger.info(f"Client connected: {request.sid}")
            join_room('updates')
            
            # Send initial data
            emit('suts_update', {ip: asdict(sut) for ip, sut in self.suts.items()})
            emit('games_update', {name: asdict(config) for name, config in self.game_configs.items()})
            emit('runs_update', {
                'active': {run_id: asdict(run) for run_id, run in self.active_runs.items()},
                'history': [asdict(run) for run in self.run_history[-10:]]
            })
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info(f"Client disconnected: {request.sid}")
            leave_room('updates')
    
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
    
    def start_sut_discovery(self):
        """Start SUT discovery background thread"""
        self.discovery_thread = threading.Thread(target=self.sut_discovery_loop, daemon=True)
        self.discovery_thread.start()
        logger.info("Started SUT discovery thread")
    
    def sut_discovery_loop(self):
        """Background loop for discovering SUTs"""
        # Default SUT IPs to check (you can make this configurable)
        sut_candidates = [
            "192.168.50.230",
            "192.168.50.231", 
            "192.168.1.100",
            "127.0.0.1"  # localhost for testing
        ]
        
        while not self.stop_discovery.is_set():
            for ip in sut_candidates:
                self.check_sut_status(ip, 8080)  # Default port
            
            # Emit updates if any changes
            self.emit_suts_update()
            
            # Wait before next discovery cycle
            self.stop_discovery.wait(10)  # Check every 10 seconds
    
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
    
    def emit_suts_update(self):
        """Emit SUT status updates via WebSocket"""
        suts_data = {ip: asdict(sut) for ip, sut in self.suts.items()}
        self.socketio.emit('suts_update', suts_data, room='updates')
    
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