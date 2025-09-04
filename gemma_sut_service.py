"""
Enhanced SUT Service - Comprehensive action support for gaming automation
Supports all modular action types: clicks, drags, scrolls, hotkeys, text input, etc.
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
import win32api
import win32con
import win32gui
from pynput import mouse, keyboard
from pynput.mouse import Button, Listener as MouseListener
from pynput.keyboard import Key, Listener as KeyboardListener
import ctypes
from ctypes import wintypes
import socket
import uuid
import platform
import requests
import threading
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("enhanced_sut_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global variables
game_process = None
game_lock = threading.Lock()
current_game_process_name = None
mouse_controller = mouse.Controller()
keyboard_controller = keyboard.Controller()

# Add these global variables after your existing globals
SUT_ID = str(uuid.getnode())  # Use MAC address as unique ID
SUT_NAME = f"{platform.node()}-{platform.system()}"
SUT_VERSION = "2.1.0"
BACKEND_SERVERS = []  # Will be populated by discovery
REGISTRATION_INTERVAL = 30  # seconds
HEARTBEAT_INTERVAL = 10  # seconds

# Configure PyAutoGUI for enhanced control
pyautogui.FAILSAFE = False  # Disable failsafe for automation
pyautogui.PAUSE = 0.01  # Minimal pause between actions

class EnhancedInputController:
    """Enhanced input controller with precise timing and advanced features."""
    
    def __init__(self):
        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()
        
    def smooth_move(self, start_x, start_y, end_x, end_y, duration=1.0, steps=50):
        """Smooth mouse movement between two points."""
        step_delay = duration / steps
        
        for i in range(steps + 1):
            progress = i / steps
            # Use easing for natural movement
            eased_progress = self._ease_in_out_cubic(progress)
            
            current_x = start_x + (end_x - start_x) * eased_progress
            current_y = start_y + (end_y - start_y) * eased_progress
            
            self.mouse.position = (int(current_x), int(current_y))
            time.sleep(step_delay)
    
    def _ease_in_out_cubic(self, t):
        """Cubic easing function for natural movement."""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2

# Initialize enhanced controller
input_controller = EnhancedInputController()

def find_process_by_name(process_name):
    """Find a running process by its name."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
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
    """Terminate a process by its name."""
    try:
        processes_terminated = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                if (proc.info['name'] and process_name.lower() in proc.info['name'].lower()) or \
                   (proc.info['exe'] and process_name.lower() in os.path.basename(proc.info['exe']).lower()):
                    
                    process = psutil.Process(proc.info['pid'])
                    logger.info(f"Terminating process: {proc.info['name']} (PID: {proc.info['pid']})")
                    
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                        processes_terminated.append(proc.info['name'])
                    except psutil.TimeoutExpired:
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
    """Enhanced status endpoint with capabilities."""
    return jsonify({
        "status": "running",
        "version": "2.0",
        "capabilities": [
            "basic_clicks", "advanced_clicks", "drag_drop", "scroll",
            "hotkeys", "text_input", "sequences", "process_management",
            "performance_monitoring", "multi_monitor", "gaming_optimizations"
        ]
    })

@app.route('/screenshot', methods=['GET'])
def screenshot():
    """Capture and return a screenshot with optional parameters."""
    try:
        # Optional parameters for screenshot
        monitor = request.args.get('monitor', '0')  # Monitor index
        region = request.args.get('region')  # Format: "x,y,width,height"
        
        if region:
            # Capture specific region
            x, y, width, height = map(int, region.split(','))
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
        else:
            # Capture entire screen
            screenshot = pyautogui.screenshot()
        
        # Save to a bytes buffer
        img_buffer = BytesIO()
        screenshot.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        logger.info(f"Screenshot captured (monitor: {monitor}, region: {region})")
        return send_file(img_buffer, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error capturing screenshot: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/launch', methods=['POST'])
def launch_game():
    """Launch a game with support for process ID tracking - FIXED for Steam games."""
    global game_process, current_game_process_name
    
    try:
        data = request.json
        game_path = data.get('path', '')
        process_id = data.get('process_id', '')  # Expected process name
        
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
            logger.info(f"Subprocess started with PID: {game_process.pid}")
            
            # FIXED: Don't fail if subprocess exits - this is normal for Steam games
            # Wait a moment and check subprocess status but don't treat exit as failure
            time.sleep(3)
            subprocess_status = "running" if game_process.poll() is None else "exited"
            logger.info(f"Subprocess status after 3 seconds: {subprocess_status}")
            
            # Give the actual game process time to start (important for Steam games)
            max_wait_time = 15  # Wait up to 15 seconds for the game process to appear
            wait_interval = 1
            actual_process = None
            
            for i in range(max_wait_time):
                time.sleep(wait_interval)
                actual_process = find_process_by_name(current_game_process_name)
                if actual_process:
                    logger.info(f"Game process found after {i+1} seconds: {actual_process.name()} (PID: {actual_process.pid})")
                    break
                elif i == 5:  # Log progress at 5 seconds
                    logger.info(f"Still waiting for game process '{current_game_process_name}' to start...")
            
            response_data = {
                "status": "success",
                "subprocess_pid": game_process.pid,
                "subprocess_status": subprocess_status
            }
            
            if actual_process:
                response_data["game_process_pid"] = actual_process.pid
                response_data["game_process_name"] = actual_process.name()
                response_data["game_process_status"] = actual_process.status()
                logger.info(f"✓ Game launched successfully: {actual_process.name()} (PID: {actual_process.pid})")
            else:
                # This is now a warning, not an error - the game might still be starting
                logger.warning(f"Game process '{current_game_process_name}' not found within {max_wait_time} seconds")
                logger.warning("The game might still be starting or the process_id might be incorrect")
                response_data["warning"] = f"Game process '{current_game_process_name}' not detected within {max_wait_time}s, but subprocess launched successfully"
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error launching game: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/action', methods=['POST'])
def perform_action():
    """Enhanced action handler supporting all modular action types."""
    try:
        data = request.json
        action_type = data.get('type', '').lower()
        
        logger.info(f"Executing action: {action_type}")
        
        # === CLICK ACTIONS ===
        if action_type == 'click':
            return handle_click_action(data)
        
        # === ADVANCED MOUSE ACTIONS ===
        elif action_type in ['double_click', 'triple_click']:
            return handle_multi_click_action(data)
        
        # === DRAG ACTIONS ===
        elif action_type in ['drag', 'drag_drop']:
            return handle_drag_action(data)
        
        # === SCROLL ACTIONS ===
        elif action_type == 'scroll':
            return handle_scroll_action(data)
        
        # === KEYBOARD ACTIONS ===
        elif action_type in ['key', 'keypress']:
            return handle_key_action(data)
        
        # === HOTKEY ACTIONS ===
        elif action_type == 'hotkey':
            return handle_hotkey_action(data)
        
        # === TEXT INPUT ACTIONS ===
        elif action_type in ['text', 'type', 'input']:
            return handle_text_action(data)
        
        # === WAIT ACTIONS ===
        elif action_type == 'wait':
            return handle_wait_action(data)
        
        # === SEQUENCE ACTIONS ===
        elif action_type == 'sequence':
            return handle_sequence_action(data)
        
        # === GAME MANAGEMENT ===
        elif action_type == 'terminate_game':
            return handle_terminate_game()
        
        # === SYSTEM ACTIONS ===
        elif action_type in ['screenshot_region', 'window_focus', 'window_resize']:
            return handle_system_action(data)
        
        else:
            logger.error(f"Unknown action type: {action_type}")
            return jsonify({"status": "error", "error": f"Unknown action type: {action_type}"}), 400
            
    except Exception as e:
        logger.error(f"Error performing action: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

def handle_click_action(data):
    """Handle all types of click actions with enhanced precision."""
    x = data.get('x', 0)
    y = data.get('y', 0)
    button = data.get('button', 'left').lower()
    move_duration = data.get('move_duration', 0.3)
    click_delay = data.get('click_delay', 0.1)
    
    # Validate button
    if button not in ['left', 'right', 'middle']:
        return jsonify({"status": "error", "error": f"Invalid button: {button}"}), 400
    
    try:
        # Get current position for smooth movement
        current_pos = mouse_controller.position
        
        # Smooth movement to target
        if move_duration > 0:
            input_controller.smooth_move(current_pos[0], current_pos[1], x, y, move_duration)
        else:
            mouse_controller.position = (x, y)
        
        # Wait before clicking
        if click_delay > 0:
            time.sleep(click_delay)
        
        # Perform click
        button_map = {
            'left': Button.left,
            'right': Button.right,
            'middle': Button.middle
        }
        
        mouse_controller.click(button_map[button])
        
        logger.info(f"{button.capitalize()}-clicked at ({x}, {y})")
        return jsonify({
            "status": "success", 
            "action": f"{button}_click", 
            "coordinates": [x, y],
            "move_duration": move_duration,
            "click_delay": click_delay
        })
        
    except Exception as e:
        logger.error(f"Click action failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

def handle_multi_click_action(data):
    """Handle double-click, triple-click actions."""
    x = data.get('x', 0)
    y = data.get('y', 0)
    button = data.get('button', 'left').lower()
    action_type = data.get('type', 'double_click')
    click_count = 2 if action_type == 'double_click' else 3
    
    try:
        mouse_controller.position = (x, y)
        time.sleep(0.1)
        
        button_map = {
            'left': Button.left,
            'right': Button.right,
            'middle': Button.middle
        }
        
        for i in range(click_count):
            mouse_controller.click(button_map[button])
            if i < click_count - 1:  # Don't sleep after last click
                time.sleep(0.05)  # Small delay between clicks
        
        logger.info(f"{action_type} ({button}) at ({x}, {y})")
        return jsonify({
            "status": "success", 
            "action": action_type, 
            "coordinates": [x, y],
            "click_count": click_count
        })
        
    except Exception as e:
        logger.error(f"Multi-click action failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

def handle_drag_action(data):
    """Handle drag and drop actions."""
    start_x = data.get('start_x', data.get('x', 0))
    start_y = data.get('start_y', data.get('y', 0))
    end_x = data.get('end_x', start_x + 100)
    end_y = data.get('end_y', start_y)
    duration = data.get('duration', 1.0)
    button = data.get('button', 'left').lower()
    
    try:
        button_map = {
            'left': Button.left,
            'right': Button.right,
            'middle': Button.middle
        }
        
        # Move to start position
        mouse_controller.position = (start_x, start_y)
        time.sleep(0.1)
        
        # Press and hold button
        mouse_controller.press(button_map[button])
        
        # Smooth drag to end position
        input_controller.smooth_move(start_x, start_y, end_x, end_y, duration)
        
        # Release button
        mouse_controller.release(button_map[button])
        
        logger.info(f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y}) with {button} button")
        return jsonify({
            "status": "success", 
            "action": "drag", 
            "start": [start_x, start_y],
            "end": [end_x, end_y],
            "duration": duration
        })
        
    except Exception as e:
        logger.error(f"Drag action failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

def handle_scroll_action(data):
    """Handle scroll actions."""
    x = data.get('x', 0)
    y = data.get('y', 0)
    direction = data.get('direction', 'up').lower()
    clicks = data.get('clicks', 3)
    
    try:
        mouse_controller.position = (x, y)
        time.sleep(0.1)
        
        # Convert direction to scroll value
        if direction == 'up':
            scroll_value = 1
        elif direction == 'down':
            scroll_value = -1
        else:
            return jsonify({"status": "error", "error": f"Invalid scroll direction: {direction}"}), 400
        
        # Perform scroll
        for _ in range(clicks):
            mouse_controller.scroll(0, scroll_value)
            time.sleep(0.05)  # Small delay between scroll clicks
        
        logger.info(f"Scrolled {direction} {clicks} clicks at ({x}, {y})")
        return jsonify({
            "status": "success", 
            "action": "scroll", 
            "coordinates": [x, y],
            "direction": direction,
            "clicks": clicks
        })
        
    except Exception as e:
        logger.error(f"Scroll action failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

def handle_key_action(data):
    """Handle single key press actions."""
    key_name = data.get('key', '')
    
    if not key_name:
        return jsonify({"status": "error", "error": "No key specified"}), 400
    
    try:
        # Map common key names to pynput keys
        key_mapping = {
            'enter': Key.enter,
            'return': Key.enter,
            'space': Key.space,
            'tab': Key.tab,
            'escape': Key.esc,
            'esc': Key.esc,
            'delete': Key.delete,
            'backspace': Key.backspace,
            'shift': Key.shift,
            'ctrl': Key.ctrl,
            'alt': Key.alt,
            'win': Key.cmd,
            'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4,
            'f5': Key.f5, 'f6': Key.f6, 'f7': Key.f7, 'f8': Key.f8,
            'f9': Key.f9, 'f10': Key.f10, 'f11': Key.f11, 'f12': Key.f12,
            'up': Key.up, 'down': Key.down, 'left': Key.left, 'right': Key.right,
            'home': Key.home, 'end': Key.end, 'pageup': Key.page_up, 'pagedown': Key.page_down
        }
        
        # Get the key to press
        key_to_press = key_mapping.get(key_name.lower(), key_name)
        
        # Press and release the key
        keyboard_controller.press(key_to_press)
        keyboard_controller.release(key_to_press)
        
        logger.info(f"Pressed key: {key_name}")
        return jsonify({
            "status": "success", 
            "action": "keypress", 
            "key": key_name
        })
        
    except Exception as e:
        logger.error(f"Key action failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

def handle_hotkey_action(data):
    """Handle hotkey combination actions."""
    keys = data.get('keys', [])
    
    if not keys:
        return jsonify({"status": "error", "error": "No keys specified for hotkey"}), 400
    
    try:
        # Map key names
        key_mapping = {
            'ctrl': Key.ctrl, 'alt': Key.alt, 'shift': Key.shift, 'win': Key.cmd,
            'enter': Key.enter, 'space': Key.space, 'tab': Key.tab, 'escape': Key.esc,
            'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4,
            'f5': Key.f5, 'f6': Key.f6, 'f7': Key.f7, 'f8': Key.f8,
            'f9': Key.f9, 'f10': Key.f10, 'f11': Key.f11, 'f12': Key.f12,
        }
        
        # Convert key names to pynput keys
        keys_to_press = []
        for key_name in keys:
            key_obj = key_mapping.get(key_name.lower(), key_name)
            keys_to_press.append(key_obj)
        
        # Press all keys down
        for key in keys_to_press:
            keyboard_controller.press(key)
            time.sleep(0.01)  # Small delay between key presses
        
        # Small hold time
        time.sleep(0.05)
        
        # Release all keys in reverse order
        for key in reversed(keys_to_press):
            keyboard_controller.release(key)
            time.sleep(0.01)
        
        logger.info(f"Pressed hotkey combination: {'+'.join(keys)}")
        return jsonify({
            "status": "success", 
            "action": "hotkey", 
            "keys": keys
        })
        
    except Exception as e:
        logger.error(f"Hotkey action failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

def handle_text_action(data):
    """Handle text input actions."""
    text = data.get('text', '')
    clear_first = data.get('clear_first', False)
    char_delay = data.get('char_delay', 0.05)
    
    if not text:
        return jsonify({"status": "error", "error": "No text specified"}), 400
    
    try:
        # Clear existing text if requested
        if clear_first:
            keyboard_controller.press(Key.ctrl)
            keyboard_controller.press('a')
            keyboard_controller.release('a')
            keyboard_controller.release(Key.ctrl)
            time.sleep(0.1)
        
        # Type text character by character
        for char in text:
            if char == '\n':
                keyboard_controller.press(Key.enter)
                keyboard_controller.release(Key.enter)
            elif char == '\t':
                keyboard_controller.press(Key.tab)
                keyboard_controller.release(Key.tab)
            else:
                keyboard_controller.type(char)
            
            if char_delay > 0:
                time.sleep(char_delay)
        
        logger.info(f"Typed text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        return jsonify({
            "status": "success", 
            "action": "text_input", 
            "text_length": len(text),
            "clear_first": clear_first
        })
        
    except Exception as e:
        logger.error(f"Text action failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

def handle_wait_action(data):
    """Handle wait actions."""
    duration = data.get('duration', 1)
    
    try:
        logger.info(f"Waiting for {duration} seconds")
        time.sleep(duration)
        
        return jsonify({
            "status": "success", 
            "action": "wait", 
            "duration": duration
        })
        
    except Exception as e:
        logger.error(f"Wait action failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

def handle_sequence_action(data):
    """Handle sequence of actions."""
    actions = data.get('actions', [])
    delay_between = data.get('delay_between', 0.5)
    
    if not actions:
        return jsonify({"status": "error", "error": "No actions specified in sequence"}), 400
    
    try:
        results = []
        
        for i, action in enumerate(actions):
            logger.info(f"Executing sequence action {i+1}/{len(actions)}: {action.get('type', 'unknown')}")
            
            # Recursively call perform_action for each sub-action
            # Note: This creates a nested structure but avoids code duplication
            result = perform_action_internal(action)
            results.append(result)
            
            # Check if action failed
            if result.get('status') != 'success':
                logger.error(f"Sequence failed at action {i+1}")
                return jsonify({
                    "status": "error", 
                    "error": f"Sequence failed at action {i+1}",
                    "failed_action": action,
                    "results": results
                }), 500
            
            # Delay between actions (except after last action)
            if delay_between > 0 and i < len(actions) - 1:
                time.sleep(delay_between)
        
        logger.info(f"Completed sequence of {len(actions)} actions")
        return jsonify({
            "status": "success", 
            "action": "sequence", 
            "actions_completed": len(actions),
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Sequence action failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

def perform_action_internal(data):
    """Internal action handler for sequence actions."""
    # This is a simplified version that returns dict instead of Flask response
    try:
        action_type = data.get('type', '').lower()
        
        if action_type == 'click':
            handle_click_action(data)
            return {"status": "success", "action": action_type}
        elif action_type in ['key', 'keypress']:
            handle_key_action(data)
            return {"status": "success", "action": action_type}
        elif action_type == 'hotkey':
            handle_hotkey_action(data)
            return {"status": "success", "action": action_type}
        elif action_type in ['text', 'type']:
            handle_text_action(data)
            return {"status": "success", "action": action_type}
        elif action_type == 'wait':
            handle_wait_action(data)
            return {"status": "success", "action": action_type}
        # Add other action types as needed
        else:
            return {"status": "error", "error": f"Unknown action type in sequence: {action_type}"}
            
    except Exception as e:
        return {"status": "error", "error": str(e)}

def handle_terminate_game():
    """Handle game termination."""
    global game_process, current_game_process_name
    
    try:
        with game_lock:
            terminated = False
            
            if current_game_process_name:
                logger.info(f"Terminating game by process name: {current_game_process_name}")
                if terminate_process_by_name(current_game_process_name):
                    terminated = True
            
            if game_process and game_process.poll() is None:
                logger.info("Terminating game subprocess")
                game_process.terminate()
                try:
                    game_process.wait(timeout=5)
                    terminated = True
                except subprocess.TimeoutExpired:
                    game_process.kill()
                    terminated = True
            
            message = "Game terminated successfully" if terminated else "No running game to terminate"
            
            return jsonify({
                "status": "success", 
                "action": "terminate_game",
                "message": message,
                "terminated": terminated
            })
            
    except Exception as e:
        logger.error(f"Terminate game failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

def handle_system_action(data):
    """Handle system-level actions."""
    action_type = data.get('type')
    
    try:
        if action_type == 'window_focus':
            window_title = data.get('window_title', '')
            # Focus specific window
            hwnd = win32gui.FindWindow(None, window_title)
            if hwnd:
                win32gui.SetForegroundWindow(hwnd)
                return jsonify({"status": "success", "action": "window_focus"})
            else:
                return jsonify({"status": "error", "error": "Window not found"}), 404
                
        elif action_type == 'window_resize':
            window_title = data.get('window_title', '')
            width = data.get('width', 1920)
            height = data.get('height', 1080)
            # Resize specific window
            hwnd = win32gui.FindWindow(None, window_title)
            if hwnd:
                win32gui.SetWindowPos(hwnd, 0, 0, 0, width, height, win32con.SWP_NOMOVE)
                return jsonify({"status": "success", "action": "window_resize"})
            else:
                return jsonify({"status": "error", "error": "Window not found"}), 404
        
        else:
            return jsonify({"status": "error", "error": f"Unknown system action: {action_type}"}), 400
            
    except Exception as e:
        logger.error(f"System action failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500
    
def get_local_ip():
    """Get the local IP address of this machine."""
    try:
        # Create a socket to find local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

def get_system_info():
    """Get detailed system information."""
    try:
        return {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "total_memory": psutil.virtual_memory().total,
            "cpu_count": psutil.cpu_count(),
            "boot_time": psutil.boot_time()
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {}

def discover_backend_servers():
    """Discover backend servers on the network."""
    try:
        local_ip = get_local_ip()
        network_base = ".".join(local_ip.split(".")[:-1])
        
        backend_servers = []
        
        # Check common ports where backend might be running
        backend_ports = [5000, 8000, 3000]
        
        for i in range(1, 255):  # Scan entire subnet
            for port in backend_ports:
                ip = f"{network_base}.{i}"
                if ip == local_ip:  # Skip self
                    continue
                    
                try:
                    # Quick check for backend server
                    response = requests.get(
                        f"http://{ip}:{port}/api/status", 
                        timeout=1
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('status') == 'running':
                            backend_servers.append({
                                'ip': ip,
                                'port': port,
                                'url': f"http://{ip}:{port}"
                            })
                            logger.info(f"Discovered backend server: {ip}:{port}")
                except:
                    continue
        
        return backend_servers
    except Exception as e:
        logger.error(f"Error discovering backend servers: {e}")
        return []

def register_with_backend(backend_url):
    """Register this SUT with a backend server."""
    try:
        local_ip = get_local_ip()
        sut_data = {
            "sut_id": SUT_ID,
            "name": SUT_NAME,
            "ip": local_ip,
            "port": app.config.get('PORT', 8080),
            "version": SUT_VERSION,
            "capabilities": [
                "screenshot",
                "click_actions", 
                "keyboard_input",
                "game_launch",
                "process_management",
                "performance_monitoring",
                "enhanced_input_control"
            ],
            "system_info": get_system_info(),
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(
            f"{backend_url}/api/suts/register",
            json=sut_data,
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info(f"Successfully registered with backend: {backend_url}")
            return True
        else:
            logger.warning(f"Registration failed with {backend_url}: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error registering with backend {backend_url}: {e}")
        return False

def send_heartbeat(backend_url):
    """Send heartbeat to backend server."""
    try:
        heartbeat_data = {
            "sut_id": SUT_ID,
            "timestamp": datetime.now().isoformat(),
            "status": "online",
            "current_task": "idle",  # You can update this based on current activity
            "quick_metrics": {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent
            }
        }
        
        response = requests.post(
            f"{backend_url}/api/suts/heartbeat",
            json=heartbeat_data,
            timeout=3
        )
        
        return response.status_code == 200
        
    except Exception as e:
        logger.debug(f"Heartbeat failed for {backend_url}: {e}")
        return False

def background_discovery_and_registration():
    """Background thread for discovery and registration."""
    global BACKEND_SERVERS
    
    while True:
        try:
            # Discover backend servers periodically
            discovered = discover_backend_servers()
            
            # Update backend servers list
            BACKEND_SERVERS = discovered
            
            # Register with all discovered backends
            for backend in BACKEND_SERVERS:
                register_with_backend(backend['url'])
            
            # Wait before next discovery cycle
            time.sleep(REGISTRATION_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in discovery/registration loop: {e}")
            time.sleep(10)

def background_heartbeat():
    """Background thread for sending heartbeats."""
    while True:
        try:
            for backend in BACKEND_SERVERS:
                send_heartbeat(backend['url'])
            
            time.sleep(HEARTBEAT_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")
            time.sleep(5)

@app.route('/performance', methods=['GET'])
def get_performance_metrics():
    """Get system and game performance metrics."""
    try:
        metrics = {
            "timestamp": time.time(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "cpu_freq": psutil.cpu_freq().current if psutil.cpu_freq() else None,
            "cpu_count": psutil.cpu_count(),
            "cpu_count_logical": psutil.cpu_count(logical=True)
        }
        
        # Add game-specific metrics if available
        if current_game_process_name:
            game_process = find_process_by_name(current_game_process_name)
            if game_process:
                try:
                    metrics["game_process"] = {
                        "pid": game_process.pid,
                        "name": game_process.name(),
                        "cpu_percent": game_process.cpu_percent(),
                        "memory_percent": game_process.memory_percent(),
                        "memory_info": game_process.memory_info()._asdict(),
                        "num_threads": game_process.num_threads(),
                        "status": game_process.status()
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    metrics["game_process"] = None
        
        return jsonify({"status": "success", "metrics": metrics})
        
    except Exception as e:
        logger.error(f"Performance metrics failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Comprehensive health check."""
    try:
        health_status = {
            "service": "running",
            "version": "2.0",
            "uptime": time.time(),
            "mouse_controller": "active",
            "keyboard_controller": "active",
            "pyautogui": "active",
            "process_monitoring": "active"
        }
        
        # Check if game is running
        if current_game_process_name:
            game_process = find_process_by_name(current_game_process_name)
            health_status["game_process"] = "running" if game_process else "not_found"
        else:
            health_status["game_process"] = "none"
        
        return jsonify({"status": "success", "health": health_status})
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500
    
@app.route('/status', methods=['GET'])
def status():
    """Enhanced status endpoint with unique SUT identification."""
    try:
        local_ip = get_local_ip()
        
        status_data = {
            "status": "running",
            "sut_id": SUT_ID,
            "name": SUT_NAME,
            "version": SUT_VERSION,
            "ip": local_ip,
            "port": app.config.get('PORT', 8080),
            "capabilities": [
                "screenshot",
                "click_actions", 
                "keyboard_input",
                "game_launch",
                "process_management",
                "performance_monitoring",
                "enhanced_input_control"
            ],
            "system_info": get_system_info(),
            "current_game": current_game_process_name if current_game_process_name else None,
            "registered_backends": len(BACKEND_SERVERS),
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"Status check failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500
    
# Add this new endpoint for backend discovery
@app.route('/discover', methods=['GET'])
def discover_info():
    """Endpoint for backend servers to discover this SUT."""
    try:
        return status()  # Just call the status function
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced SUT Service v2.1 - Auto-Discovery Support')
    parser.add_argument('--port', type=int, default=8080, help='Port to run the service on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-auto-discovery', action='store_true', help='Disable automatic backend discovery')
    args = parser.parse_args()
    
    # Store port in app config for access in other functions
    app.config['PORT'] = args.port
    
    logger.info("=" * 60)
    logger.info("Enhanced SUT Service v2.1 - Auto-Discovery Gaming Platform")
    logger.info("=" * 60)
    logger.info(f"SUT ID: {SUT_ID}")
    logger.info(f"SUT Name: {SUT_NAME}")
    logger.info(f"Local IP: {get_local_ip()}")
    logger.info(f"Starting service on {args.host}:{args.port}")
    
    if not args.no_auto_discovery:
        logger.info("Starting auto-discovery and registration...")
        
        # Start background discovery and registration
        discovery_thread = threading.Thread(
            target=background_discovery_and_registration, 
            daemon=True
        )
        discovery_thread.start()
        
        # Start background heartbeat  
        heartbeat_thread = threading.Thread(
            target=background_heartbeat, 
            daemon=True
        )
        heartbeat_thread.start()
        
        logger.info("Auto-discovery enabled - SUT will automatically register with backend servers")
    else:
        logger.info("Auto-discovery disabled")
    
    logger.info("Supported Features:")
    logger.info("   All click types (left/right/middle/double/triple)")
    logger.info("   Drag & drop operations with smooth movement")
    logger.info("   Scroll actions with precise control")
    logger.info("   Hotkey combinations (Ctrl+Alt+Del, etc.)")
    logger.info("   Character-by-character text input")
    logger.info("   Action sequences with timing control")
    logger.info("   Process management with CPU/memory monitoring")
    logger.info("   Window management and system controls")
    logger.info("   Performance metrics and health monitoring")
    logger.info("   Gaming-optimized input handling")
    logger.info("   Auto-discovery and registration")
    logger.info("=" * 60)
    
    app.run(host=args.host, port=args.port, debug=args.debug)