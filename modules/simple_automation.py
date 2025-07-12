"""
Enhanced simple step-by-step automation module for game UI navigation.
Supports process ID tracking and enhanced action types.
"""

import os
import time
import logging
import yaml
from typing import List, Dict, Any, Optional

from modules.gemma_client import BoundingBox

logger = logging.getLogger(__name__)

class SimpleAutomation:
    """Enhanced step-by-step automation for game UI workflows with process tracking."""
    
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
            # Fall back to direct YAML loading
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
        
        logger.info(f"EnhancedSimpleAutomation initialized for {self.game_name}")
        if self.process_id:
            logger.info(f"Process ID tracking enabled: {self.process_id}")
            
    def run(self):
        """Run the enhanced step-by-step automation."""
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
        
        # Debug: Log the available steps
        logger.info(f"Available steps: {list(steps.keys())}")
        
        current_step = 1
        max_retries = 3
        retries = 0
        
        logger.info(f"Starting enhanced automation with {len(steps)} steps")
        
        # Track process status if enabled
        if self.process_id and self.monitor_process:
            self._log_process_status("before_automation")
        
        while current_step <= len(steps):
            step_key = str(current_step)
            
            if step_key not in steps:
                logger.error(f"Step {step_key} not found in configuration. Available steps: {list(steps.keys())}")
                return False
                
            step = steps[step_key]
            logger.info(f"Executing step {current_step}: {step.get('description', 'No description')}")
            
            # Check for stop event
            if self.stop_event and self.stop_event.is_set():
                logger.info("Stop event detected, ending automation")
                break
            
            # Capture screenshot
            screenshot_path = f"{self.run_dir}/screenshots/screenshot_{current_step}.png"
            try:
                self.screenshot_mgr.capture(screenshot_path)
            except Exception as e:
                logger.error(f"Failed to capture screenshot: {str(e)}")
                retries += 1
                if retries >= max_retries:
                    logger.error(f"Max retries reached for screenshot capture, failing")
                    return False
                continue
            
            # Detect UI elements
            try:
                bounding_boxes = self.vision_model.detect_ui_elements(screenshot_path)
            except Exception as e:
                logger.error(f"Failed to detect UI elements: {str(e)}")
                retries += 1
                if retries >= max_retries:
                    logger.error(f"Max retries reached for UI detection, failing")
                    return False
                continue
            
            # Annotate screenshot if annotator available
            if self.annotator:
                try:
                    annotated_path = f"{self.run_dir}/annotated/annotated_{current_step}.png"
                    self.annotator.draw_bounding_boxes(screenshot_path, bounding_boxes, annotated_path)
                    logger.info(f"Annotated screenshot saved: {annotated_path}")
                except Exception as e:
                    logger.warning(f"Failed to create annotated screenshot: {str(e)}")
            
            # Process step based on type
            success = self._process_step(step, bounding_boxes, current_step)
            
            if success:
                logger.info(f"Step {current_step} completed successfully")
                current_step += 1
                retries = 0  # Reset retry counter on success
                
                # Log process status after significant steps if enabled
                if self.process_id and self.monitor_process and current_step in [3, 5, len(steps)]:
                    self._log_process_status(f"after_step_{current_step-1}")
                    
            else:
                retries += 1
                logger.warning(f"Step {current_step} failed, retry {retries}/{max_retries}")
                if retries >= max_retries:
                    logger.error(f"Max retries reached for step {current_step}, failing")
                    return False
                # Execute fallback if step fails
                self._execute_fallback()
                
        if current_step > len(steps):
            logger.info("All steps completed successfully!")
            
            # Final process status if enabled
            if self.process_id and self.monitor_process:
                self._log_process_status("after_automation")
                
            return True
        else:
            logger.info("Automation stopped before completion")
            return False
    
    def _process_step(self, step: Dict[str, Any], bounding_boxes: List[BoundingBox], step_num: int) -> bool:
        """Process a single step with enhanced action support."""
        if "find_and_click" in step:
            return self._handle_find_and_click(step, bounding_boxes, step_num)
        elif "action" in step:
            return self._handle_action(step, step_num)
        else:
            logger.error(f"Unknown step type in step {step_num}: {step}")
            return False
    
    def _handle_find_and_click(self, step: Dict[str, Any], bounding_boxes: List[BoundingBox], step_num: int) -> bool:
        """Handle find_and_click steps with enhanced action support."""
        target = step["find_and_click"]
        element = self._find_matching_element(target, bounding_boxes)
        
        if element:
            # Calculate center point for click
            center_x = element.x + (element.width // 2)
            center_y = element.y + (element.height // 2)
            
            # Get action configuration (default to left click)
            action_config = step.get("action", {"type": "click", "click_type": "left"})
            click_type = action_config.get("click_type", "left")
            
            # Execute click with specified type
            action = {
                "type": "click",
                "x": center_x,
                "y": center_y,
                "button": click_type
            }
            
            try:
                response = self.network.send_action(action)
                logger.info(f"{click_type.capitalize()}-clicked on '{element.element_text}' at ({center_x}, {center_y})")
                logger.debug(f"Network response: {response}")
            except Exception as e:
                logger.error(f"Failed to send {click_type} click action: {str(e)}")
                return False
            
            # Wait for expected delay
            expected_delay = step.get("expected_delay", 2)
            logger.info(f"Waiting {expected_delay} seconds after {click_type} click...")
            time.sleep(expected_delay)
            
            # Verify success if specified
            if step.get("verify_success"):
                return self._verify_step_success(step, step_num)
            else:
                return True
                
        else:
            target_text = target.get('text', 'Unknown')
            target_type = target.get('type', 'any')
            logger.warning(f"Target element '{target_text}' (type: {target_type}) not found")
            self._log_available_elements(bounding_boxes)
            return False
    
    def _handle_action(self, step: Dict[str, Any], step_num: int) -> bool:
        """Handle direct action steps with enhanced support."""
        action_config = step["action"]
        
        if isinstance(action_config, str) and action_config == "wait":
            # Simple wait action
            duration = step.get("duration", 10)
            logger.info(f"Waiting for {duration} seconds")
            
            # Wait in smaller increments to allow for interruption
            for i in range(duration):
                if self.stop_event and self.stop_event.is_set():
                    logger.info("Wait interrupted by stop event")
                    break
                time.sleep(1)
                if i % 10 == 0 and i > 0:  # Log progress for long waits
                    logger.info(f"Still waiting... {i}/{duration} seconds elapsed")
            
            return True
            
        elif isinstance(action_config, dict):
            # Enhanced action configuration
            action_type = action_config.get("type")
            
            if action_type == "wait":
                duration = action_config.get("duration", step.get("duration", 10))
                logger.info(f"Waiting for {duration} seconds")
                
                for i in range(duration):
                    if self.stop_event and self.stop_event.is_set():
                        logger.info("Wait interrupted by stop event")
                        break
                    time.sleep(1)
                    if i % 10 == 0 and i > 0:
                        logger.info(f"Still waiting... {i}/{duration} seconds elapsed")
                
                return True
                
            elif action_type == "key" or action_type == "keypress":
                key = action_config.get("key", "")
                if key:
                    logger.info(f"Pressing key: {key}")
                    try:
                        self.network.send_action({"type": "key", "key": key})
                        time.sleep(step.get("expected_delay", 1))
                        return True
                    except Exception as e:
                        logger.error(f"Failed to send key action: {str(e)}")
                        return False
                else:
                    logger.error("No key specified for keypress action")
                    return False
                    
            elif action_type == "right_click":
                # Handle right click at current mouse position or specified coordinates
                x = action_config.get("x", 0)
                y = action_config.get("y", 0)
                
                action = {"type": "click", "x": x, "y": y, "button": "right"}
                
                try:
                    response = self.network.send_action(action)
                    logger.info(f"Right-clicked at ({x}, {y})")
                    time.sleep(step.get("expected_delay", 1))
                    return True
                except Exception as e:
                    logger.error(f"Failed to send right click action: {str(e)}")
                    return False
            
            else:
                logger.error(f"Unknown enhanced action type: {action_type}")
                return False
        
        else:
            logger.error(f"Invalid action configuration in step {step_num}: {action_config}")
            return False
    
    def _verify_step_success(self, step: Dict[str, Any], step_num: int) -> bool:
        """Verify step success with enhanced checking."""
        logger.info("Verifying step success...")
        
        # Capture new screenshot for verification
        verify_path = f"{self.run_dir}/screenshots/verify_{step_num}.png"
        try:
            self.screenshot_mgr.capture(verify_path)
            verify_boxes = self.vision_model.detect_ui_elements(verify_path)
            
            # Annotate verification screenshot if annotator available
            if self.annotator:
                try:
                    annotated_verify_path = f"{self.run_dir}/annotated/verify_{step_num}.png"
                    self.annotator.draw_bounding_boxes(verify_path, verify_boxes, annotated_verify_path)
                except Exception as e:
                    logger.warning(f"Failed to create verification annotation: {str(e)}")
            
            # Check for verification elements
            success = True
            for verify_element in step["verify_success"]:
                if not self._find_matching_element(verify_element, verify_boxes):
                    success = False
                    logger.warning(f"Verification failed: {verify_element.get('text', 'Unknown element')} not found")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed during verification: {str(e)}")
            return False
    
    def _find_matching_element(self, target_def, bounding_boxes):
        """Find a UI element matching the target definition."""
        target_type = target_def.get("type", "any")
        target_text = target_def.get("text", "")
        match_type = target_def.get("text_match", "contains")
        
        logger.debug(f"Looking for element: type='{target_type}', text='{target_text}', match='{match_type}'")
        
        for bbox in bounding_boxes:
            # Check element type
            type_match = (target_type == "any" or bbox.element_type == target_type)
            
            # Check text content with specified matching strategy
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
                else:
                    logger.warning(f"Unknown text_match type: {match_type}, using 'contains'")
                    text_match = target_text_lower in bbox_text_lower
            elif not target_text:  # If no text requirement, match any element of the right type
                text_match = True
            
            if type_match and text_match:
                logger.debug(f"Found matching element: type='{bbox.element_type}', text='{bbox.element_text}'")
                return bbox
                
        logger.debug("No matching element found")
        return None
    
    def _log_available_elements(self, bounding_boxes):
        """Log available elements for debugging."""
        if bounding_boxes:
            logger.info("Available UI elements:")
            for i, bbox in enumerate(bounding_boxes):
                logger.info(f"  {i+1}. Type: {bbox.element_type}, Text: '{bbox.element_text}'")
        else:
            logger.info("No UI elements detected")
    
    def _log_process_status(self, checkpoint: str):
        """Log process status if process monitoring is enabled."""
        try:
            # Try to get process status from enhanced SUT service
            response = self.network.session.get(
                f"{self.network.base_url}/game_status",
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    game_status = result.get("game_status", {})
                    actual_process = game_status.get("actual_game_process")
                    
                    if actual_process:
                        logger.info(f"Process status at {checkpoint}:")
                        logger.info(f"  PID: {actual_process.get('pid')}")
                        logger.info(f"  Name: {actual_process.get('name')}")
                        logger.info(f"  CPU: {actual_process.get('cpu_percent', 0):.1f}%")
                        logger.info(f"  Memory: {actual_process.get('memory_percent', 0):.1f}%")
                    else:
                        logger.warning(f"Process {self.process_id} not found at {checkpoint}")
                        
        except Exception as e:
            logger.debug(f"Could not get process status at {checkpoint}: {str(e)}")
    
    def _execute_fallback(self):
        """Execute fallback action if step fails."""
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
            elif action_type == "click":
                x = fallback.get("x", 0)
                y = fallback.get("y", 0)
                logger.info(f"Executing fallback: Click at ({x}, {y})")
                try:
                    self.network.send_action({"type": "click", "x": x, "y": y})
                except Exception as e:
                    logger.error(f"Failed to execute fallback click action: {str(e)}")
        else:
            logger.info("No fallback action defined, pressing Escape key as default")
            try:
                self.network.send_action({"type": "key", "key": "Escape"})
            except Exception as e:
                logger.error(f"Failed to execute default fallback action: {str(e)}")
                
        # Wait after fallback
        fallback_delay = fallback.get("expected_delay", 1) if fallback else 1
        logger.info(f"Waiting {fallback_delay} seconds after fallback action")
        time.sleep(fallback_delay)