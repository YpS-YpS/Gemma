"""
Enhanced simple step-by-step automation module with fully modular action system.
Supports all human input types: clicks, keys, text, drag/drop, scroll, etc.
"""

import os
import time
import logging
import yaml
from typing import List, Dict, Any, Optional, Union

from modules.gemma_client import BoundingBox

logger = logging.getLogger(__name__)

class SimpleAutomation:
    """Fully modular step-by-step automation with comprehensive action support."""
    
    def __init__(self, config_path, network, screenshot_mgr, vision_model, stop_event=None, run_dir=None, annotator=None):
        """Initialize with all necessary components."""
        self.config_path = config_path
        self.network = network
        self.screenshot_mgr = screenshot_mgr
        self.vision_model = vision_model
        self.stop_event = stop_event
        self.annotator = annotator
        
        # Load configuration
        try:
            from modules.simple_config_parser import SimpleConfigParser
            config_parser = SimpleConfigParser(config_path)
            self.config = config_parser.get_config()
            logger.info("Using SimpleConfigParser for step-based configuration")
        except (ImportError, ValueError):
            logger.info("SimpleConfigParser not available, loading YAML directly")
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        
        # Game metadata with enhanced support
        self.game_name = self.config.get("metadata", {}).get("game_name", "Unknown Game")
        self.process_id = self.config.get("metadata", {}).get("process_id")
        self.run_dir = run_dir or f"logs/{self.game_name}"
        
        # Enhanced features
        self.enhanced_features = self.config.get("enhanced_features", {})
        self.monitor_process = self.enhanced_features.get("monitor_process_cpu", False)
        
        # Optional step handlers
        self.optional_steps = self.config.get("optional_steps", {})
        
        logger.info(f"SimpleAutomation initialized for {self.game_name}")
        if self.process_id:
            logger.info(f"Process ID tracking enabled: {self.process_id}")

    def _execute_fallback(self):
        """Execute fallback action when step fails."""
        fallback = self.config.get("fallbacks", {}).get("general", {})
        if fallback:
            action_type = fallback.get("action")
            if action_type == "key":
                key = fallback.get("key", "Escape")
                logger.info(f"Executing fallback: Press key {key}")
                try:
                    self.network.send_action({"type": "key", "key": key})
                except Exception as e:
                    logger.error(f"Failed to execute fallback key action: {str(e)}")
        # Add delay after fallback
        time.sleep(fallback.get("expected_delay", 1))
            
    def run(self):
        """Run the enhanced step-by-step automation with optional step handling."""
        # Get steps from configuration
        steps = self.config.get("steps", {})
        
        if not steps:
            logger.error("No steps defined in configuration")
            return False
        
        # Convert all step keys to strings to handle both integer and string keys
        normalized_steps = {}
        for key, value in steps.items():
            normalized_steps[str(key)] = value
        steps = normalized_steps
        
        logger.info(f"Starting enhanced automation with {len(steps)} steps")
        
        current_step = 1
        max_retries = 3
        retries = 0
        
        while current_step <= len(steps):
            step_key = str(current_step)
            
            if step_key not in steps:
                logger.error(f"Step {step_key} not found in configuration")
                return False
                
            step = steps[step_key]
            logger.info(f"Executing step {current_step}: {step.get('description', 'No description')}")
            
            # Check for stop event
            if self.stop_event and self.stop_event.is_set():
                logger.info("Stop event detected, ending automation")
                break
            
            # Handle optional steps (popups, interruptions)
            if self._handle_optional_steps():
                logger.info("Optional step handled, continuing with current step")
                continue
            
            # Capture screenshot
            screenshot_path = f"{self.run_dir}/screenshots/screenshot_{current_step}.png"
            try:
                self.screenshot_mgr.capture(screenshot_path)
            except Exception as e:
                logger.error(f"Failed to capture screenshot: {str(e)}")
                retries += 1
                if retries >= max_retries:
                    return False
                continue
            
            # Detect UI elements
            try:
                bounding_boxes = self.vision_model.detect_ui_elements(screenshot_path)
            except Exception as e:
                logger.error(f"Failed to detect UI elements: {str(e)}")
                retries += 1
                if retries >= max_retries:
                    return False
                continue
            
            # Annotate screenshot if annotator available
            if self.annotator:
                try:
                    annotated_path = f"{self.run_dir}/annotated/annotated_{current_step}.png"
                    self.annotator.draw_bounding_boxes(screenshot_path, bounding_boxes, annotated_path)
                except Exception as e:
                    logger.warning(f"Failed to create annotated screenshot: {str(e)}")
            
            # Process step using modular action system
            success = self._process_step_modular(step, bounding_boxes, current_step)
            
            if success:
                logger.info(f"Step {current_step} completed successfully")
                current_step += 1
                retries = 0
            else:
                retries += 1
                logger.warning(f"Step {current_step} failed, retry {retries}/{max_retries}")
                if retries >= max_retries:
                    logger.error(f"Max retries reached for step {current_step}")
                    return False
                self._execute_fallback()
                
        return current_step > len(steps)
    
    def _process_step_modular(self, step: Dict[str, Any], bounding_boxes: List[BoundingBox], step_num: int) -> bool:
        """Process a step using the new modular action system with enhanced logging."""
        
        target_element = None
        
        # 1. FIND ELEMENT (if specified)
        if "find" in step:
            target_element = self._find_matching_element(step["find"], bounding_boxes)
            if not target_element:
                target_text = step["find"].get('text', 'Unknown')
                target_type = step["find"].get('type', 'Unknown')
                logger.warning(f"Target element not found: {target_type} with text '{target_text}'")
                self._log_available_elements(bounding_boxes)
                return False
            else:
                # Log successful element detection
                element_text = target_element.element_text if target_element.element_text else "(no text)"
                logger.info("=========================================================")
                logger.info(f"Found target element: {target_element.element_type} '{element_text}' at ({target_element.x}, {target_element.y})")
                logger.info("=========================================================")

        
        # 2. EXECUTE ACTION
        if "action" in step:
            success = self._execute_modular_action(step["action"], target_element, step_num)
            if not success:
                return False
        else:
            logger.error(f"No action specified in step {step_num}")
            return False
        
        # Wait for expected delay
        expected_delay = step.get("expected_delay", 1)
        if expected_delay > 0:
            logger.info(f"Waiting {expected_delay} seconds after action...")
            time.sleep(expected_delay)
        
        # 3. VERIFY SUCCESS (if specified)
        if "verify_success" in step:
            return self._verify_step_success(step, step_num)
        
        return True
    
    def _execute_modular_action(self, action_config: Union[str, Dict[str, Any]], target_element: Optional[BoundingBox], step_num: int) -> bool:
        """Execute an action using the modular action system."""
        
        # Handle simple string actions
        if isinstance(action_config, str):
            if action_config == "wait":
                duration = 10  # Default wait
                logger.info(f"Waiting for {duration} seconds")
                self._interruptible_wait(duration)
                return True
            else:
                logger.error(f"Unknown simple action: {action_config}")
                return False
        
        # Handle complex action configurations
        if not isinstance(action_config, dict):
            logger.error(f"Invalid action configuration: {action_config}")
            return False
        
        action_type = action_config.get("type", "").lower()
        
        # === CLICK ACTIONS ===
        if action_type == "click":
            return self._handle_click_action(action_config, target_element)
        
        # === KEYBOARD ACTIONS ===
        elif action_type in ["key", "keypress", "hotkey"]:
            return self._handle_keyboard_action(action_config)
        
        # === TEXT INPUT ACTIONS ===
        elif action_type in ["type", "text", "input"]:
            return self._handle_text_action(action_config)
        
        # === MOUSE ACTIONS ===
        elif action_type in ["double_click", "right_click", "middle_click"]:
            return self._handle_mouse_action(action_config, target_element)
        
        # === DRAG AND DROP ACTIONS ===
        elif action_type in ["drag", "drag_drop"]:
            return self._handle_drag_action(action_config, target_element)
        
        # === SCROLL ACTIONS ===
        elif action_type == "scroll":
            return self._handle_scroll_action(action_config, target_element)
        
        # === WAIT ACTIONS ===
        elif action_type == "wait":
            return self._handle_wait_action(action_config)
        
        # === CONDITIONAL ACTIONS ===
        elif action_type == "conditional":
            return self._handle_conditional_action(action_config, target_element)
        
        # === SEQUENCE ACTIONS ===
        elif action_type == "sequence":
            return self._handle_sequence_action(action_config, target_element)
        
        else:
            logger.error(f"Unknown action type: {action_type}")
            return False
    
    def _handle_click_action(self, action_config: Dict[str, Any], target_element: Optional[BoundingBox]) -> bool:
        """Handle various click actions with enhanced logging."""
        button = action_config.get("button", "left").lower()
        
        # Get element information for logging
        element_info = "unknown element"
        if target_element:
            element_info = f"'{target_element.element_text}'" if target_element.element_text else f"{target_element.element_type} element"
            x = target_element.x + (target_element.width // 2)
            y = target_element.y + (target_element.height // 2)
        else:
            x = action_config.get("x", 0)
            y = action_config.get("y", 0)
            element_info = "coordinates"
        
        # Apply offset if specified
        offset_x = action_config.get("offset_x", 0)
        offset_y = action_config.get("offset_y", 0)
        x += offset_x
        y += offset_y
        
        # Movement and timing parameters
        move_duration = action_config.get("move_duration", 0.5)
        click_delay = action_config.get("click_delay", 0.1)
        
        action = {
            "type": "click",
            "x": x,
            "y": y,
            "button": button,
            "move_duration": move_duration,
            "click_delay": click_delay
        }
        
        try:
            response = self.network.send_action(action)
            # Enhanced logging with element information
            logger.info(f"Clicked on {element_info} at ({x}, {y})")
            if target_element and target_element.element_text:
                logger.debug(f"Element details: type='{target_element.element_type}', text='{target_element.element_text}', size={target_element.width}x{target_element.height}")
            return True
        except Exception as e:
            logger.error(f"Failed to click on {element_info}: {str(e)}")
            return False
    
    def _handle_keyboard_action(self, action_config: Dict[str, Any]) -> bool:
        """Handle keyboard actions including single keys and combinations."""
        action_type = action_config.get("type", "key")
        
        if action_type == "hotkey":
            # Handle key combinations like Ctrl+C, Alt+Tab, etc.
            keys = action_config.get("keys", [])
            if not keys:
                logger.error("No keys specified for hotkey")
                return False
            
            try:
                response = self.network.send_action({"type": "hotkey", "keys": keys})
                logger.info(f"Pressed hotkey: {'+'.join(keys)}")
                return True
            except Exception as e:
                logger.error(f"Failed to send hotkey: {str(e)}")
                return False
        else:
            # Handle single key press
            key = action_config.get("key", "")
            if not key:
                logger.error("No key specified for keypress")
                return False
            
            # Support for special key names
            key_mapping = {
                "enter": "Return",
                "return": "Return",
                "space": "space",
                "tab": "Tab",
                "escape": "Escape",
                "esc": "Escape",
                "delete": "Delete",
                "backspace": "BackSpace",
                "shift": "Shift_L",
                "ctrl": "Control_L",
                "alt": "Alt_L",
                "win": "Super_L",
                "f1": "F1", "f2": "F2", "f3": "F3", "f4": "F4",
                "f5": "F5", "f6": "F6", "f7": "F7", "f8": "F8",
                "f9": "F9", "f10": "F10", "f11": "F11", "f12": "F12",
                "up": "Up", "down": "Down", "left": "Left", "right": "Right",
                "home": "Home", "end": "End", "pageup": "Page_Up", "pagedown": "Page_Down"
            }
            
            mapped_key = key_mapping.get(key.lower(), key)
            
            try:
                response = self.network.send_action({"type": "key", "key": mapped_key})
                logger.info(f"Pressed key: {mapped_key}")
                return True
            except Exception as e:
                logger.error(f"Failed to send key action: {str(e)}")
                return False
    
    def _handle_text_action(self, action_config: Dict[str, Any]) -> bool:
        """Handle text input actions."""
        text = action_config.get("text", "")
        if not text:
            logger.error("No text specified for text input")
            return False
        
        # Clear existing text if specified
        clear_first = action_config.get("clear_first", False)
        if clear_first:
            try:
                # Ctrl+A to select all, then type
                self.network.send_action({"type": "hotkey", "keys": ["ctrl", "a"]})
                time.sleep(0.1)
            except Exception as e:
                logger.warning(f"Failed to clear existing text: {str(e)}")
        
        # Type character by character with optional delay
        char_delay = action_config.get("char_delay", 0.05)
        
        try:
            for char in text:
                if self.stop_event and self.stop_event.is_set():
                    break
                    
                if char == ' ':
                    self.network.send_action({"type": "key", "key": "space"})
                elif char == '\n':
                    self.network.send_action({"type": "key", "key": "Return"})
                elif char == '\t':
                    self.network.send_action({"type": "key", "key": "Tab"})
                else:
                    self.network.send_action({"type": "key", "key": char})
                
                if char_delay > 0:
                    time.sleep(char_delay)
            
            logger.info(f"Typed text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to type text: {str(e)}")
            return False
    
    def _handle_mouse_action(self, action_config: Dict[str, Any], target_element: Optional[BoundingBox]) -> bool:
        """Handle advanced mouse actions with enhanced logging."""
        action_type = action_config.get("type")
        
        # Get element information for logging
        element_info = "unknown element"
        if target_element:
            element_info = f"'{target_element.element_text}'" if target_element.element_text else f"{target_element.element_type} element"
            x = target_element.x + (target_element.width // 2)
            y = target_element.y + (target_element.height // 2)
        else:
            x = action_config.get("x", 0)
            y = action_config.get("y", 0)
            element_info = "coordinates"
        
        if action_type == "double_click":
            button = action_config.get("button", "left")
            try:
                response = self.network.send_action({
                    "type": "double_click",
                    "x": x, "y": y,
                    "button": button
                })
                logger.info(f"Double-clicked on {element_info} at ({x}, {y})")
                return True
            except Exception as e:
                logger.error(f"Failed to double-click on {element_info}: {str(e)}")
                return False
        
        elif action_type == "right_click":
            try:
                response = self.network.send_action({
                    "type": "click",
                    "x": x, "y": y,
                    "button": "right"
                })
                logger.info(f"Right-clicked on {element_info} at ({x}, {y})")
                return True
            except Exception as e:
                logger.error(f"Failed to right-click on {element_info}: {str(e)}")
                return False
        
        elif action_type == "middle_click":
            try:
                response = self.network.send_action({
                    "type": "click",
                    "x": x, "y": y,
                    "button": "middle"
                })
                logger.info(f"Middle-clicked on {element_info} at ({x}, {y})")
                return True
            except Exception as e:
                logger.error(f"Failed to middle-click on {element_info}: {str(e)}")
                return False
        
        return False
    
    def _handle_drag_action(self, action_config: Dict[str, Any], target_element: Optional[BoundingBox]) -> bool:
        """Handle drag and drop actions with enhanced logging."""
        if not target_element:
            logger.error("Drag action requires a target element")
            return False
        
        # Source element information
        source_info = f"'{target_element.element_text}'" if target_element.element_text else f"{target_element.element_type} element"
        source_x = target_element.x + (target_element.width // 2)
        source_y = target_element.y + (target_element.height // 2)
        
        # Destination coordinates
        dest_x = action_config.get("dest_x", source_x + 100)
        dest_y = action_config.get("dest_y", source_y + 100)
        
        # Drag parameters
        drag_duration = action_config.get("duration", 1.0)
        steps = action_config.get("steps", 20)
        
        try:
            response = self.network.send_action({
                "type": "drag",
                "start_x": source_x,
                "start_y": source_y,
                "end_x": dest_x,
                "end_y": dest_y,
                "duration": drag_duration,
                "steps": steps
            })
            logger.info(f"Dragged {source_info} from ({source_x}, {source_y}) to ({dest_x}, {dest_y})")
            return True
        except Exception as e:
            logger.error(f"Failed to drag {source_info}: {str(e)}")
            return False

    
    def _handle_scroll_action(self, action_config: Dict[str, Any], target_element: Optional[BoundingBox]) -> bool:
        """Handle scroll actions with enhanced logging."""
        # Get scroll location
        if target_element:
            element_info = f"'{target_element.element_text}'" if target_element.element_text else f"{target_element.element_type} element"
            x = target_element.x + (target_element.width // 2)
            y = target_element.y + (target_element.height // 2)
        else:
            x = action_config.get("x", 500)  # Default center screen
            y = action_config.get("y", 400)
            element_info = "screen coordinates"
        
        # Scroll parameters
        direction = action_config.get("direction", "down")
        clicks = action_config.get("clicks", 3)
        
        try:
            response = self.network.send_action({
                "type": "scroll",
                "x": x,
                "y": y,
                "direction": direction,
                "clicks": clicks
            })
            logger.info(f"Scrolled {direction} {clicks} clicks on {element_info} at ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Failed to scroll on {element_info}: {str(e)}")
            return False
    
    def _handle_wait_action(self, action_config: Dict[str, Any]) -> bool:
        """Handle wait actions with various conditions."""
        duration = action_config.get("duration", 1)
        condition = action_config.get("condition")
        
        if condition:
            # Conditional wait (wait until condition is met)
            max_wait = action_config.get("max_wait", 30)
            check_interval = action_config.get("check_interval", 1)
            
            logger.info(f"Waiting up to {max_wait}s for condition: {condition}")
            # Note: Condition checking would require additional implementation
            self._interruptible_wait(max_wait)
        else:
            # Simple wait
            logger.info(f"Waiting for {duration} seconds")
            self._interruptible_wait(duration)
        
        return True
    
    def _handle_conditional_action(self, action_config: Dict[str, Any], target_element: Optional[BoundingBox]) -> bool:
        """Handle conditional actions."""
        condition = action_config.get("condition", {})
        if_action = action_config.get("if_true")
        else_action = action_config.get("if_false")
        
        # Simple condition checking (can be extended)
        condition_met = target_element is not None
        
        if condition_met and if_action:
            logger.info("Condition met, executing if_true action")
            return self._execute_modular_action(if_action, target_element, 0)
        elif not condition_met and else_action:
            logger.info("Condition not met, executing if_false action")
            return self._execute_modular_action(else_action, target_element, 0)
        
        return True
    
    def _handle_sequence_action(self, action_config: Dict[str, Any], target_element: Optional[BoundingBox]) -> bool:
        """Handle sequence of actions."""
        actions = action_config.get("actions", [])
        delay_between = action_config.get("delay_between", 0.5)
        
        for i, action in enumerate(actions):
            logger.info(f"Executing sequence action {i+1}/{len(actions)}")
            success = self._execute_modular_action(action, target_element, 0)
            if not success:
                logger.error(f"Sequence failed at action {i+1}")
                return False
            
            if delay_between > 0 and i < len(actions) - 1:
                time.sleep(delay_between)
        
        logger.info(f"Completed sequence of {len(actions)} actions")
        return True
    
    def _handle_optional_steps(self) -> bool:
        """Handle optional steps (popups, interruptions)."""
        if not self.optional_steps:
            return False
        
        try:
            # Capture current screenshot for optional step checking
            optional_screenshot = f"{self.run_dir}/screenshots/optional_check.png"
            self.screenshot_mgr.capture(optional_screenshot)
            optional_boxes = self.vision_model.detect_ui_elements(optional_screenshot)
            
            # Check each optional step
            for step_name, step_config in self.optional_steps.items():
                if self._check_optional_step_condition(step_config, optional_boxes):
                    logger.info(f"Optional step triggered: {step_name}")
                    success = self._execute_modular_action(step_config["action"], None, 0)
                    if success:
                        logger.info(f"Optional step '{step_name}' completed")
                        return True
                    else:
                        logger.warning(f"Optional step '{step_name}' failed")
            
        except Exception as e:
            logger.debug(f"Optional step checking failed: {str(e)}")
        
        return False
    
    def _check_optional_step_condition(self, step_config: Dict[str, Any], bounding_boxes: List[BoundingBox]) -> bool:
        """Check if an optional step condition is met."""
        trigger = step_config.get("trigger", {})
        return self._find_matching_element(trigger, bounding_boxes) is not None
    
    def _interruptible_wait(self, duration: int):
        """Wait that can be interrupted by stop event."""
        for i in range(duration):
            if self.stop_event and self.stop_event.is_set():
                logger.info("Wait interrupted by stop event")
                break
            time.sleep(1)
            if i % 10 == 0 and i > 0:
                logger.info(f"Still waiting... {i}/{duration} seconds elapsed")
    
    def _find_matching_element(self, target_def, bounding_boxes):
        """Find a UI element matching the target definition with enhanced logging."""
        target_type = target_def.get("type", "any")
        target_text = target_def.get("text", "")
        match_type = target_def.get("text_match", "contains")
        
        logger.debug(f"Searching for element: type='{target_type}', text='{target_text}', match_strategy='{match_type}'")
        
        for bbox in bounding_boxes:
            # Check element type
            type_match = (target_type == "any" or bbox.element_type == target_type)
            
            # Check text content
            text_match = False
            if bbox.element_text and target_text:
                bbox_text_lower = bbox.element_text.lower()
                target_text_lower = target_text.lower()
                
                if match_type == "exact":
                    text_match = target_text_lower == bbox_text_lower
                elif match_type == "contains":
                    text_match = target_text_lower in bbox_text_lower
                elif match_type == "startswith":
                    text_match = bbox_text_lower.startswith(target_text_lower)
                elif match_type == "endswith":
                    text_match = bbox_text_lower.endswith(target_text_lower)
                
                # Debug logging for text matching attempts
                if type_match:
                    logger.debug(f"  Checking element '{bbox.element_text}': text_match={text_match} (strategy={match_type})")
                    
            elif not target_text:
                text_match = True
            
            if type_match and text_match:
                element_text = bbox.element_text if bbox.element_text else "(no text)"
                logger.debug(f"✅ Match found: {bbox.element_type} '{element_text}' at ({bbox.x}, {bbox.y})")
                return bbox
        
        logger.debug("❌ No matching element found")
        return None
            

    
    def _verify_step_success(self, step: Dict[str, Any], step_num: int) -> bool:
        """Verify step success with enhanced checking."""
        logger.info("Verifying step success...")
        
        verify_path = f"{self.run_dir}/screenshots/verify_{step_num}.png"
        try:
            self.screenshot_mgr.capture(verify_path)
            verify_boxes = self.vision_model.detect_ui_elements(verify_path)
            
            if self.annotator:
                try:
                    annotated_verify_path = f"{self.run_dir}/annotated/verify_{step_num}.png"
                    self.annotator.draw_bounding_boxes(verify_path, verify_boxes, annotated_verify_path)
                except Exception as e:
                    logger.warning(f"Failed to create verification annotation: {str(e)}")
            
            success = True
            for verify_element in step["verify_success"]:
                if not self._find_matching_element(verify_element, verify_boxes):
                    success = False
                    logger.warning(f"Verification failed: {verify_element.get('text', 'Unknown element')} not found")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed during verification: {str(e)}")
            return False
    
    def _log_available_elements(self, bounding_boxes):
        """Log available elements for debugging with enhanced formatting."""
        if bounding_boxes:
            logger.info(f"Available UI elements ({len(bounding_boxes)} found):")
            for i, bbox in enumerate(bounding_boxes):
                element_text = bbox.element_text if bbox.element_text else "(no text)"
                logger.info(f"  [{i+1}] {bbox.element_type}: '{element_text}' at ({bbox.x}, {bbox.y}, {bbox.width}x{bbox.height})")
        else:
            logger.info("No UI elements detected in current screenshot")
# `"""
# Simple step-by-step automation module for game UI navigation.
# Uses a direct procedural approach instead of complex state machines.
# """

# import os
# import time
# import logging
# import yaml
# from typing import List, Dict, Any, Optional

# from modules.gemma_client import BoundingBox

# logger = logging.getLogger(__name__)

# class SimpleAutomation:
#     """Simplified step-by-step automation for game UI workflows."""
    
#     def __init__(self, config_path, network, screenshot_mgr, vision_model, stop_event=None, run_dir=None, annotator=None):
#         """Initialize with all necessary components."""
#         self.config_path = config_path
#         self.network = network
#         self.screenshot_mgr = screenshot_mgr
#         self.vision_model = vision_model
#         self.stop_event = stop_event
#         self.annotator = annotator
        
#         # Load configuration using SimpleConfigParser if available
#         try:
#             from modules.simple_config_parser import SimpleConfigParser
#             config_parser = SimpleConfigParser(config_path)
#             self.config = config_parser.get_config()
#             logger.info("Using SimpleConfigParser for step-based configuration")
#         except (ImportError, ValueError):
#             # Fall back to direct YAML loading
#             logger.info("SimpleConfigParser not available, loading YAML directly")
#             with open(config_path, 'r') as f:
#                 self.config = yaml.safe_load(f)
        
#         # Game metadata
#         self.game_name = self.config.get("metadata", {}).get("game_name", "Unknown Game")
#         self.run_dir = run_dir or f"logs/{self.game_name}"
        
#         logger.info(f"SimpleAutomation initialized for {self.game_name}")
            
#     def run(self):
#         """Run the simplified step-by-step automation."""
#         # Get steps from configuration
#         steps = self.config.get("steps", {})
        
#         # If no steps defined, try to convert from state machine format
#         if not steps:
#             logger.info("No steps defined in config, attempting to convert from state machine format")
#             steps = self._convert_states_to_steps()
            
#         if not steps:
#             logger.error("No steps defined and couldn't convert from state machine format")
#             return False
        
#         # Convert all step keys to strings to handle both integer and string keys
#         normalized_steps = {}
#         for key, value in steps.items():
#             normalized_steps[str(key)] = value
#         steps = normalized_steps
        
#         # Debug: Log the available steps
#         logger.info(f"Available steps: {list(steps.keys())}")
        
#         current_step = 1
#         max_retries = 3
#         retries = 0
        
#         logger.info(f"Starting automation with {len(steps)} steps")
        
#         while current_step <= len(steps):
#             step_key = str(current_step)
            
#             if step_key not in steps:
#                 logger.error(f"Step {step_key} not found in configuration. Available steps: {list(steps.keys())}")
#                 return False
                
#             step = steps[step_key]
#             logger.info(f"Executing step {current_step}: {step.get('description', 'No description')}")
            
#             # Check for stop event
#             if self.stop_event and self.stop_event.is_set():
#                 logger.info("Stop event detected, ending automation")
#                 break
            
#             # Capture screenshot
#             screenshot_path = f"{self.run_dir}/screenshots/screenshot_{current_step}.png"
#             try:
#                 self.screenshot_mgr.capture(screenshot_path)
#             except Exception as e:
#                 logger.error(f"Failed to capture screenshot: {str(e)}")
#                 retries += 1
#                 if retries >= max_retries:
#                     logger.error(f"Max retries reached for screenshot capture, failing")
#                     return False
#                 continue
            
#             # Detect UI elements
#             try:
#                 bounding_boxes = self.vision_model.detect_ui_elements(screenshot_path)
#             except Exception as e:
#                 logger.error(f"Failed to detect UI elements: {str(e)}")
#                 retries += 1
#                 if retries >= max_retries:
#                     logger.error(f"Max retries reached for UI detection, failing")
#                     return False
#                 continue
            
#             # Annotate screenshot if annotator available
#             if self.annotator:
#                 try:
#                     annotated_path = f"{self.run_dir}/annotated/annotated_{current_step}.png"
#                     self.annotator.draw_bounding_boxes(screenshot_path, bounding_boxes, annotated_path)
#                     logger.info(f"Annotated screenshot saved: {annotated_path}")
#                 except Exception as e:
#                     logger.warning(f"Failed to create annotated screenshot: {str(e)}")
            
#             # Process step based on type
#             if "find_and_click" in step:
#                 # Find and click element
#                 target = step["find_and_click"]
#                 element = self._find_matching_element(target, bounding_boxes)
                
#                 if element:
#                     # Calculate center point for click
#                     center_x = element.x + (element.width // 2)
#                     center_y = element.y + (element.height // 2)
                    
#                     # Execute click
#                     action = {"type": "click", "x": center_x, "y": center_y}
#                     try:
#                         response = self.network.send_action(action)
#                         logger.info(f"Clicked on '{element.element_text}' at ({center_x}, {center_y})")
#                         logger.debug(f"Network response: {response}")
#                     except Exception as e:
#                         logger.error(f"Failed to send click action: {str(e)}")
#                         retries += 1
#                         if retries >= max_retries:
#                             logger.error(f"Max retries reached for click action, failing")
#                             return False
#                         continue
                    
#                     # Wait for expected delay
#                     expected_delay = step.get("expected_delay", 2)
#                     logger.info(f"Waiting {expected_delay} seconds after click...")
#                     time.sleep(expected_delay)
                    
#                     # Verify success if specified
#                     if step.get("verify_success"):
#                         logger.info("Verifying step success...")
#                         # Capture new screenshot for verification
#                         verify_path = f"{self.run_dir}/screenshots/verify_{current_step}.png"
#                         try:
#                             self.screenshot_mgr.capture(verify_path)
#                             verify_boxes = self.vision_model.detect_ui_elements(verify_path)
                            
#                             # Annotate verification screenshot if annotator available
#                             if self.annotator:
#                                 try:
#                                     annotated_verify_path = f"{self.run_dir}/annotated/verify_{current_step}.png"
#                                     self.annotator.draw_bounding_boxes(verify_path, verify_boxes, annotated_verify_path)
#                                 except Exception as e:
#                                     logger.warning(f"Failed to create verification annotation: {str(e)}")
                            
#                             # Check for verification elements
#                             success = True
#                             for verify_element in step["verify_success"]:
#                                 if not self._find_matching_element(verify_element, verify_boxes):
#                                     success = False
#                                     logger.warning(f"Verification failed: {verify_element.get('text', 'Unknown element')} not found")
                            
#                             if success:
#                                 logger.info(f"Step {current_step} completed successfully")
#                                 current_step += 1
#                                 retries = 0  # Reset retry counter on success
#                             else:
#                                 retries += 1
#                                 logger.warning(f"Step {current_step} verification failed, retry {retries}/{max_retries}")
#                                 if retries >= max_retries:
#                                     logger.error(f"Max retries reached for step {current_step}, failing")
#                                     return False
#                                 # Execute fallback if verification fails
#                                 self._execute_fallback()
#                         except Exception as e:
#                             logger.error(f"Failed during verification: {str(e)}")
#                             retries += 1
#                             if retries >= max_retries:
#                                 logger.error(f"Max retries reached during verification, failing")
#                                 return False
#                             continue
#                     else:
#                         # No verification needed, move to next step
#                         logger.info(f"Step {current_step} completed (no verification required)")
#                         current_step += 1
#                         retries = 0  # Reset retry counter on success
#                 else:
#                     retries += 1
#                     target_text = target.get('text', 'Unknown')
#                     target_type = target.get('type', 'any')
#                     logger.warning(f"Target element '{target_text}' (type: {target_type}) not found, retry {retries}/{max_retries}")
                    
#                     # Log available elements for debugging
#                     if bounding_boxes:
#                         logger.info("Available UI elements:")
#                         for i, bbox in enumerate(bounding_boxes):
#                             logger.info(f"  {i+1}. Type: {bbox.element_type}, Text: '{bbox.element_text}'")
#                     else:
#                         logger.info("No UI elements detected")
                    
#                     if retries >= max_retries:
#                         logger.error(f"Max retries reached for step {current_step}, failing")
#                         return False
#                     # Execute fallback if target not found
#                     self._execute_fallback()
                    
#             elif "action" in step and step["action"] == "wait":
#                 # Wait action
#                 duration = step.get("duration", 10)
#                 logger.info(f"Waiting for {duration} seconds")
                
#                 # Wait in smaller increments to allow for interruption
#                 for i in range(duration):
#                     if self.stop_event and self.stop_event.is_set():
#                         logger.info("Wait interrupted by stop event")
#                         break
#                     time.sleep(1)
#                     if i % 10 == 0 and i > 0:  # Log progress for long waits
#                         logger.info(f"Still waiting... {i}/{duration} seconds elapsed")
                
#                 # Move to next step after wait
#                 logger.info(f"Wait completed for step {current_step}")
#                 current_step += 1
#                 retries = 0  # Reset retry counter
#             else:
#                 logger.error(f"Unknown step type in step {current_step}: {step}")
#                 return False
                
#         if current_step > len(steps):
#             logger.info("All steps completed successfully!")
#             return True
#         else:
#             logger.info("Automation stopped before completion")
#             return False
    
#     def _find_matching_element(self, target_def, bounding_boxes):
#         """Find a UI element matching the target definition."""
#         target_type = target_def.get("type", "any")
#         target_text = target_def.get("text", "")
#         match_type = target_def.get("text_match", "contains")
        
#         logger.debug(f"Looking for element: type='{target_type}', text='{target_text}', match='{match_type}'")
        
#         for bbox in bounding_boxes:
#             # Check element type
#             type_match = (target_type == "any" or bbox.element_type == target_type)
            
#             # Check text content with specified matching strategy
#             text_match = False
#             if bbox.element_text and target_text:
#                 bbox_text_lower = bbox.element_text.lower()
#                 target_text_lower = target_text.lower()
                
#                 if match_type == "exact":
#                     text_match = target_text_lower == bbox_text_lower
#                 elif match_type == "contains":
#                     text_match = target_text_lower in bbox_text_lower
#                 elif match_type == "startswith":
#                     text_match = bbox_text_lower.startswith(target_text_lower)
#                 elif match_type == "endswith":
#                     text_match = bbox_text_lower.endswith(target_text_lower)
#                 else:
#                     logger.warning(f"Unknown text_match type: {match_type}, using 'contains'")
#                     text_match = target_text_lower in bbox_text_lower
#             elif not target_text:  # If no text requirement, match any element of the right type
#                 text_match = True
            
#             if type_match and text_match:
#                 logger.debug(f"Found matching element: type='{bbox.element_type}', text='{bbox.element_text}'")
#                 return bbox
                
#         logger.debug("No matching element found")
#         return None
        
#     def _execute_fallback(self):
#         """Execute fallback action if step fails."""
#         fallback = self.config.get("fallbacks", {}).get("general", {})
#         if fallback:
#             action_type = fallback.get("action")
#             if action_type == "key":
#                 key = fallback.get("key", "Escape")
#                 logger.info(f"Executing fallback: Press key {key}")
#                 try:
#                     self.network.send_action({"type": "key", "key": key})
#                 except Exception as e:
#                     logger.error(f"Failed to execute fallback key action: {str(e)}")
#             elif action_type == "click":
#                 x = fallback.get("x", 0)
#                 y = fallback.get("y", 0)
#                 logger.info(f"Executing fallback: Click at ({x}, {y})")
#                 try:
#                     self.network.send_action({"type": "click", "x": x, "y": y})
#                 except Exception as e:
#                     logger.error(f"Failed to execute fallback click action: {str(e)}")
#         else:
#             logger.info("No fallback action defined, pressing Escape key as default")
#             try:
#                 self.network.send_action({"type": "key", "key": "Escape"})
#             except Exception as e:
#                 logger.error(f"Failed to execute default fallback action: {str(e)}")
                
#         # Wait after fallback
#         fallback_delay = fallback.get("expected_delay", 1) if fallback else 1
#         logger.info(f"Waiting {fallback_delay} seconds after fallback action")
#         time.sleep(fallback_delay)
        
#     def _convert_states_to_steps(self):
#         """
#         Attempt to convert state machine format to step format.
#         This allows using existing YAML files with the simple automation.
#         """
#         steps = {}
#         states = self.config.get("states", {})
#         transitions = self.config.get("transitions", {})
#         initial_state = self.config.get("initial_state")
        
#         if not states or not transitions or not initial_state:
#             logger.warning("Missing required state machine components for conversion")
#             return {}
            
#         # Start with initial state
#         current_state = initial_state
#         step_num = 1
#         visited_states = set()
        
#         # Prevent infinite loops
#         while current_state not in visited_states and step_num <= 10:
#             visited_states.add(current_state)
            
#             # Find transitions from current state
#             for transition_key, transition in transitions.items():
#                 if transition_key.startswith(f"{current_state}->"):
#                     to_state = transition_key.split("->")[1]
#                     action_type = transition.get("action")
                    
#                     # Create step based on transition type
#                     if action_type == "click":
#                         target = transition.get("target", {})
                        
#                         step = {
#                             "description": f"Click to go from {current_state} to {to_state}",
#                             "find_and_click": {
#                                 "type": target.get("type", "any"),
#                                 "text": target.get("text", ""),
#                                 "text_match": target.get("text_match", "contains")
#                             },
#                             "expected_delay": transition.get("expected_delay", 2)
#                         }
                        
#                         # Add verification if target state has required elements
#                         if to_state in states:
#                             verify = []
#                             for req in states[to_state].get("required_elements", []):
#                                 verify.append({
#                                     "type": req.get("type", "any"),
#                                     "text": req.get("text", ""),
#                                     "text_match": req.get("text_match", "contains")
#                                 })
#                             if verify:
#                                 step["verify_success"] = verify
                        
#                         steps[str(step_num)] = step
#                         step_num += 1
#                         current_state = to_state
#                         break
                        
#                     elif action_type == "wait":
#                         step = {
#                             "description": f"Wait during {current_state}",
#                             "action": "wait",
#                             "duration": transition.get("duration", 10)
#                         }
#                         steps[str(step_num)] = step
#                         step_num += 1
#                         current_state = to_state
#                         break
        
#         logger.info(f"Converted state machine to {len(steps)} steps")
#         return steps