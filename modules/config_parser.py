# -*- coding: utf-8 -*-
"""
Simple Configuration Parser for Game Automation

Updated to support modular action format:
- Modular: separate find + action sections
- Wait-only: action: wait

Removes legacy find_and_click support.
"""

import yaml
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SimpleConfigParser:
    """
    Parser for simple automation configurations supporting modular actions.
    
    Supports configuration formats:
    1. Modular format: separate find + action sections
    2. Wait-only format: action: wait
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the parser with a configuration file.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.config = {}
        self._load_config()
        self._validate_config()
    
    def _load_config(self):
        """Load and parse the YAML configuration file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.config = yaml.safe_load(file)
                logger.info(f"Loaded configuration from {self.config_path}")
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML configuration: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {str(e)}")
            raise
    
    def _validate_config(self) -> bool:
        """
        Validate configuration format supporting modular actions.
        
        Returns:
            True if valid
        
        Raises:
            ValueError: If the config is invalid
        """
        # Check for required sections
        if "steps" not in self.config:
            logger.error("Missing required 'steps' section in config")
            raise ValueError("Invalid config: missing 'steps' section")
        
        # Validate steps
        steps = self.config.get("steps", {})
        if not isinstance(steps, dict) or not steps:
            logger.error("Steps section must be a non-empty dictionary")
            raise ValueError("Invalid config: steps section must be a non-empty dictionary")
        
        # Validate each step
        for step_num, step in steps.items():
            if "description" not in step:
                logger.warning(f"Step {step_num} missing description")
            
            # Check for valid step formats:
            # 1. Modular format: has both 'find' and 'action' sections
            # 2. Wait-only format: has 'action' with type 'wait'
            has_modular_format = "find" in step and "action" in step
            has_wait_action = "action" in step and self._is_wait_action(step["action"])
            
            if not (has_modular_format or has_wait_action):
                logger.error(f"Step {step_num} must have either:")
                logger.error(f"  1. Both 'find' and 'action' sections (modular format)")
                logger.error(f"  2. 'action' section with wait type")
                raise ValueError(f"Invalid step {step_num}: missing required sections")
            
            # Validate modular format
            if has_modular_format:
                self._validate_find_section(step["find"], step_num)
                self._validate_action_section(step["action"], step_num)
            
            # Validate wait action
            if has_wait_action:
                self._validate_wait_action(step["action"], step_num)
        
        logger.info("Configuration validation successful")
        return True
    
    def _is_wait_action(self, action) -> bool:
        """Check if action is a wait action."""
        if isinstance(action, str):
            return action == "wait"
        elif isinstance(action, dict):
            return action.get("type", "").lower() == "wait"
        return False
    
    def _validate_find_section(self, find_config: Dict[str, Any], step_num: str):
        """Validate the find section of a step."""
        if not isinstance(find_config, dict):
            raise ValueError(f"Step {step_num}: 'find' section must be a dictionary")
        
        if "type" not in find_config:
            logger.warning(f"Step {step_num}: 'find' section missing 'type' attribute")
        
        if "text" not in find_config:
            logger.warning(f"Step {step_num}: 'find' section missing 'text' attribute")
    
    def _validate_action_section(self, action_config: Any, step_num: str):
        """Validate the action section of a step."""
        if isinstance(action_config, str):
            # Simple string actions like "wait"
            valid_simple_actions = ["wait"]
            if action_config not in valid_simple_actions:
                logger.warning(f"Step {step_num}: Unknown simple action '{action_config}'")
        elif isinstance(action_config, dict):
            # Complex action configurations
            if "type" not in action_config:
                logger.warning(f"Step {step_num}: 'action' section missing 'type' attribute")
            else:
                action_type = action_config.get("type", "").lower()
                valid_action_types = [
                    "click", "double_click", "right_click", "middle_click",
                    "key", "keypress", "hotkey", "type", "text", "input",
                    "drag", "drag_drop", "scroll", "wait",
                    "conditional", "sequence"
                ]
                if action_type not in valid_action_types:
                    logger.warning(f"Step {step_num}: Unknown action type '{action_type}'")
        else:
            raise ValueError(f"Step {step_num}: 'action' must be string or dictionary")
    
    def _validate_wait_action(self, action_config: Any, step_num: str):
        """Validate wait action configuration."""
        if isinstance(action_config, dict):
            if "duration" not in action_config and action_config.get("type") == "wait":
                logger.warning(f"Step {step_num}: Wait action missing 'duration' attribute")
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the parsed configuration.
        
        Returns:
            Configuration dictionary
        """
        return self.config
    
    def get_step(self, step_num: str) -> Optional[Dict[str, Any]]:
        """
        Get the definition for a specific step.
        
        Args:
            step_num: Step number as string
        
        Returns:
            Step definition dictionary or None if not found
        """
        steps = self.config.get("steps", {})
        return steps.get(step_num)
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get game metadata from the configuration.
        
        Returns:
            Metadata dictionary with game information
        """
        return self.config.get("metadata", {})
    
    def is_modular_step(self, step: Dict[str, Any]) -> bool:
        """
        Check if a step uses the modular format (separate find + action).
        
        Args:
            step: Step configuration dictionary
            
        Returns:
            True if step uses modular format
        """
        return "find" in step and "action" in step
    
    def is_wait_step(self, step: Dict[str, Any]) -> bool:
        """
        Check if a step is a wait-only step.
        
        Args:
            step: Step configuration dictionary
            
        Returns:
            True if step is wait-only
        """
        return "action" in step and self._is_wait_action(step["action"])