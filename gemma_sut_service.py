"""
Enhanced SUT Service - Run this on the System Under Test (SUT)
This service handles requests from the ARL development PC with support for process ID tracking.
"""

import os
import time
import json
import subprocess
import threading
import psutil
from flask import Flask, request, jsonify, send_file
import pyautogui
from io import BytesIO
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sut_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global variables
game_process = None
game_lock = threading.Lock()
current_game_process_name = None  # Track the actual process name

def find_process_by_name(process_name):
    """
    Find a running process by its name.
    
    Args:
        process_name: Name of the process to find
        
    Returns:
        psutil.Process object if found, None otherwise
    """
    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                # Check both the process name and executable name
                if (proc.info['name'] and process_name.lower() in proc.info['name'].lower()) or \
                   (proc.info['exe'] and process_name.lower() in os.path.basename(proc.info['exe']).lower()):
                    logger.info(f"Found process: {proc.info['name']} (PID: {proc.info['pid']})")
                    return psutil.Process(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.error(f"Error searching for process {process_name}: {str(e)}")
    
    return None

def terminate_process_by_name(process_name):
    """
    Terminate a process by its name.
    
    Args:
        process_name: Name of the process to terminate
        
    Returns:
        True if process was found and terminated, False otherwise
    """
    try:
        processes_terminated = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                # Check both the process name and executable name
                if (proc.info['name'] and process_name.lower() in proc.info['name'].lower()) or \
                   (proc.info['exe'] and process_name.lower() in os.path.basename(proc.info['exe']).lower()):
                    
                    process = psutil.Process(proc.info['pid'])
                    logger.info(f"Terminating process: {proc.info['name']} (PID: {proc.info['pid']})")
                    
                    # Try graceful termination first
                    process.terminate()
                    
                    # Wait up to 5 seconds for graceful termination
                    try:
                        process.wait(timeout=5)
                        processes_terminated.append(proc.info['name'])
                    except psutil.TimeoutExpired:
                        # Force kill if graceful termination fails
                        logger.warning(f"Force killing process: {proc.info['name']}")
                        process.kill()
                        processes_terminated.append(proc.info['name'])
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        if processes_terminated:
            logger.info(f"Successfully terminated processes: {processes_terminated}")
            return True
        else:
            logger.info(f"No processes found with name: {process_name}")
            return False
            
    except Exception as e:
        logger.error(f"Error terminating process {process_name}: {str(e)}")
        return False

@app.route('/status', methods=['GET'])
def status():
    """Endpoint to check if the service is running."""
    return jsonify({"status": "running"})

@app.route('/screenshot', methods=['GET'])
def screenshot():
    """Capture and return a screenshot."""
    try:
        # Capture the entire screen
        screenshot = pyautogui.screenshot()
        
        # Save to a bytes buffer
        img_buffer = BytesIO()
        screenshot.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        logger.info("Screenshot captured")
        return send_file(img_buffer, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error capturing screenshot: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/launch', methods=['POST'])
def launch_game():
    """Launch a game with support for process ID tracking."""
    global game_process, current_game_process_name
    
    try:
        data = request.json
        game_path = data.get('path', '')
        process_id = data.get('process_id', '')  # New: Expected process name
        
        if not game_path or not os.path.exists(game_path):
            logger.error(f"Game path not found: {game_path}")
            return jsonify({"status": "error", "error": "Game executable not found"}), 404
        
        with game_lock:
            # Terminate existing game if running
            if current_game_process_name:
                logger.info(f"Terminating existing game process: {current_game_process_name}")
                terminate_process_by_name(current_game_process_name)
                current_game_process_name = None
            
            # Also terminate using the old method if we have a subprocess handle
            if game_process and game_process.poll() is None:
                logger.info("Terminating existing game subprocess")
                game_process.terminate()
                try:
                    game_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    game_process.kill()
            
            # Launch the game
            logger.info(f"Launching game: {game_path}")
            if process_id:
                logger.info(f"Expected process name: {process_id}")
                current_game_process_name = process_id
            else:
                # Fallback to executable name without extension
                current_game_process_name = os.path.splitext(os.path.basename(game_path))[0]
            
            game_process = subprocess.Popen(game_path)
            
            # Wait a moment to check if process started successfully
            time.sleep(3)
            if game_process.poll() is not None:
                logger.error("Game subprocess failed to start")
                return jsonify({"status": "error", "error": "Game subprocess failed to start"}), 500
            
            # Additional check: Look for the actual game process by name
            time.sleep(2)  # Give the game more time to fully initialize
            actual_process = find_process_by_name(current_game_process_name)
            
            response_data = {"status": "success", "subprocess_pid": game_process.pid}
            
            if actual_process:
                response_data["game_process_pid"] = actual_process.pid
                response_data["game_process_name"] = actual_process.name()
                logger.info(f"Game process found: {actual_process.name()} (PID: {actual_process.pid})")
            else:
                logger.warning(f"Could not find game process with name: {current_game_process_name}")
                response_data["warning"] = f"Could not verify game process: {current_game_process_name}"
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error launching game: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/action', methods=['POST'])
def perform_action():
    """Perform an action (click, key press, etc.) with enhanced support for right-click."""
    try:
        data = request.json
        action_type = data.get('type', '')
        
        if action_type == 'click':
            x = data.get('x', 0)
            y = data.get('y', 0)
            
            # Get optional parameters for movement and click customization
            move_duration = data.get('move_duration', 0.5)  # Default 0.5 seconds for smooth movement
            click_delay = data.get('click_delay', 1.0)      # Default 1 second delay before clicking
            button = data.get('button', 'left').lower()     # Support 'left' or 'right' clicks
            
            # Validate button parameter
            if button not in ['left', 'right']:
                logger.error(f"Invalid button type: {button}. Must be 'left' or 'right'")
                return jsonify({"status": "error", "error": f"Invalid button type: {button}"}), 400
            
            logger.info(f"Moving smoothly to ({x}, {y}) over {move_duration}s")
            
            # Move to the coordinate smoothly
            pyautogui.moveTo(x=x, y=y, duration=move_duration)
            
            # Wait for the specified delay
            logger.info(f"Waiting {click_delay}s before {button}-clicking")
            time.sleep(click_delay)
            
            # Perform the click at current position with specified button
            logger.info(f"{button.capitalize()}-clicking at ({x}, {y})")
            if button == 'right':
                pyautogui.click(button='right')
            else:
                pyautogui.click(button='left')  # Default behavior
            
            return jsonify({"status": "success", "action": f"{button}_click", "coordinates": [x, y]})
            
        elif action_type == 'key':
            key = data.get('key', '')
            logger.info(f"Pressing key: {key}")
            pyautogui.press(key)
            return jsonify({"status": "success", "action": "keypress", "key": key})
            
        elif action_type == 'wait':
            duration = data.get('duration', 1)
            logger.info(f"Waiting for {duration} seconds")
            time.sleep(duration)
            return jsonify({"status": "success", "action": "wait", "duration": duration})
            
        elif action_type == 'terminate_game':
            with game_lock:
                terminated = False
                
                # First try to terminate by process name (more reliable)
                if current_game_process_name:
                    logger.info(f"Terminating game by process name: {current_game_process_name}")
                    if terminate_process_by_name(current_game_process_name):
                        terminated = True
                
                # Also try to terminate the subprocess handle
                if game_process and game_process.poll() is None:
                    logger.info("Terminating game subprocess")
                    game_process.terminate()
                    try:
                        game_process.wait(timeout=5)
                        terminated = True
                    except subprocess.TimeoutExpired:
                        game_process.kill()
                        terminated = True
                
                if terminated:
                    return jsonify({"status": "success", "action": "terminate_game"})
                else:
                    return jsonify({"status": "success", "action": "terminate_game", "message": "No running game to terminate"})
        
        # Enhanced action types for future extensibility
        elif action_type == 'double_click':
            x = data.get('x', 0)
            y = data.get('y', 0)
            button = data.get('button', 'left').lower()
            move_duration = data.get('move_duration', 0.5)
            
            logger.info(f"Double-{button}-clicking at ({x}, {y})")
            pyautogui.moveTo(x=x, y=y, duration=move_duration)
            time.sleep(0.5)
            pyautogui.doubleClick(x=x, y=y, button=button)
            return jsonify({"status": "success", "action": f"double_{button}_click", "coordinates": [x, y]})
            
        elif action_type == 'hotkey':
            keys = data.get('keys', [])  # List of keys to press simultaneously
            
            if not keys:
                logger.error("No keys specified for hotkey action")
                return jsonify({"status": "error", "error": "No keys specified for hotkey"}), 400
            
            logger.info(f"Pressing hotkey combination: {'+'.join(keys)}")
            pyautogui.hotkey(*keys)
            return jsonify({"status": "success", "action": "hotkey", "keys": keys})
            
        else:
            logger.error(f"Unknown action type: {action_type}")
            return jsonify({"status": "error", "error": f"Unknown action type: {action_type}"}), 400
            
    except Exception as e:
        logger.error(f"Error performing action: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/processes', methods=['GET'])
def list_processes():
    """List running processes for debugging."""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'create_time']):
            try:
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'exe': proc.info['exe'],
                    'create_time': proc.info['create_time']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        return jsonify({"status": "success", "processes": processes})
    except Exception as e:
        logger.error(f"Error listing processes: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/game_status', methods=['GET'])
def game_status():
    """Get detailed game process status."""
    try:
        status_info = {
            "subprocess_running": game_process is not None and game_process.poll() is None,
            "subprocess_pid": game_process.pid if game_process and game_process.poll() is None else None,
            "expected_process_name": current_game_process_name,
            "actual_game_process": None
        }
        
        # Look for the actual game process
        if current_game_process_name:
            actual_process = find_process_by_name(current_game_process_name)
            if actual_process:
                status_info["actual_game_process"] = {
                    "pid": actual_process.pid,
                    "name": actual_process.name(),
                    "status": actual_process.status(),
                    "cpu_percent": actual_process.cpu_percent(),
                    "memory_percent": actual_process.memory_percent()
                }
        
        return jsonify({"status": "success", "game_status": status_info})
    except Exception as e:
        logger.error(f"Error getting game status: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced SUT Service with Process ID Support')
    parser.add_argument('--port', type=int, default=8080, help='Port to run the service on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    args = parser.parse_args()
    
    logger.info(f"Starting Enhanced SUT Service on {args.host}:{args.port}")
    logger.info("Enhanced features: Process ID tracking, Right-click, Process management")
    app.run(host=args.host, port=args.port)