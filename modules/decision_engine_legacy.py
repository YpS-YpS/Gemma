# -*- coding: utf-8 -*-
"""
Decision engine for determining the next action based on UI state and YAML configuration.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional

from modules.gemma_client import BoundingBox

logger = logging.getLogger(__name__)

class DecisionEngine:
    """
    Makes decisions about next actions based on the detected UI elements
    and the predefined UI flow in the YAML configuration.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the decision engine.
        
        Args:
            config: Parsed YAML configuration dictionary
        """
        self.config = config
        self.states = config.get("states", {})
        self.transitions = config.get("transitions", {})
        self.current_state = config.get("initial_state", "initial")
        self.target_state = config.get("target_state", "completed")
        
        logger.info(f"DecisionEngine initialized with {len(self.states)} states")
        logger.info(f"Initial state: {self.current_state}, Target state: {self.target_state}")
    
    def get_target_state(self) -> str:
        """
        Get the target state from the configuration.
        
        Returns:
            Name of the target state
        """
        return self.target_state
    
    def _find_matching_element(self, state_def: Dict[str, Any], 
                              bounding_boxes: List[BoundingBox]) -> Optional[BoundingBox]:
        """
        Find a UI element that matches the current state definition.
        
        Args:
            state_def: State definition from the config
            bounding_boxes: List of detected UI elements
        
        Returns:
            Matching BoundingBox or None if no match
        """
        required_elements = state_def.get("required_elements", [])
        
        for required in required_elements:
            req_type = required.get("type")
            req_text = required.get("text")
            
            for bbox in bounding_boxes:
                # Check if this bounding box matches the requirements
                type_match = not req_type or bbox.element_type == req_type
                text_match = not req_text or (req_text in bbox.element_text if bbox.element_text else False)
                
                if type_match and text_match:
                    match_details = f"type: '{bbox.element_type}', text: '{bbox.element_text}'"
                    required_details = f"required type: '{req_type}', required text: '{req_text}'"
                    logger.info(f"Found matching element: {match_details} matches {required_details}")
                    return bbox
        
        if required_elements:
            logger.debug(f"No UI elements matched the requirements: {required_elements}")
        return None
    
    def _identify_current_state(self, bounding_boxes: List[BoundingBox]) -> str:
        """
        Identify the current UI state based on detected elements.
        
        Args:
            bounding_boxes: List of detected UI elements
        
        Returns:
            Name of the identified state or "unknown" if no match
        """
        for state_name, state_def in self.states.items():
            if self._find_matching_element(state_def, bounding_boxes):
                logger.info(f"Identified current state: {state_name}")
                return state_name
        
        logger.warning("Could not identify current state from UI elements")
        return "unknown"
    
    def _get_action_for_transition(self, from_state: str, 
                                 to_state: str, 
                                 bounding_boxes: List[BoundingBox]) -> Dict[str, Any]:
        """
        Get the action required to transition from one state to another.
        
        Args:
            from_state: Current state name
            to_state: Target state name
            bounding_boxes: List of detected UI elements
        
        Returns:
            Action dictionary or empty dict if no action found
        """
        # Find the transition definition
        transition_key = f"{from_state}->{to_state}"
        transition = self.transitions.get(transition_key)
        
        if not transition:
            logger.warning(f"No transition defined for {transition_key}")
            return {}
        
        # Get the action type
        action_type = transition.get("action", "")
        
        # Check if there are hardcoded coordinates for this transition
        if "hardcoded_coords" in transition:
            coords = transition.get("hardcoded_coords", {})
            x = coords.get("x", 0)
            y = coords.get("y", 0)
            
            logger.info(f"Using hardcoded coordinates: ({x}, {y}) for transition {transition_key}")
            return {
                "type": "click",
                "x": x,
                "y": y
            }
        
        # Handle different action types
        if action_type == "click":
            # Find the element to click
            target_element = transition.get("target", {})
            element_type = target_element.get("type")
            element_text = target_element.get("text")
            
            # Look for a matching element
            for bbox in bounding_boxes:
                type_match = not element_type or bbox.element_type == element_type
                text_match = not element_text or (element_text in bbox.element_text if bbox.element_text else False)
                
                if type_match and text_match:
                    # Calculate center point for click
                    center_x = bbox.x + (bbox.width // 2)
                    center_y = bbox.y + (bbox.height // 2)
                    
                    logger.info(f"Action: Click at ({center_x}, {center_y}) on {bbox.element_type}")
                    return {
                        "type": "click",
                        "x": center_x,
                        "y": center_y
                    }
            
            logger.warning(f"Could not find matching element for click in transition {transition_key}")
            return {}
            
        elif action_type == "key":
            # Key press action
            key = transition.get("key", "")
            if key:
                logger.info(f"Action: Press key {key}")
                return {
                    "type": "key",
                    "key": key
                }
            else:
                logger.warning("Key action specified but no key provided")
                return {}
                
        elif action_type == "wait":
            # Wait action
            duration = transition.get("duration", 1)
            logger.info(f"Action: Wait for {duration} seconds")
            return {
                "type": "wait",
                "duration": duration
            }
        
        logger.warning(f"Unknown action type: {action_type}")
        return {}
    
    def determine_next_action(self, current_state: str, 
                            bounding_boxes: List[BoundingBox]) -> Tuple[Dict[str, Any], str]:
        """
        Determine the next action to take based on the current state and UI elements.
        
        Args:
            current_state: Current state name
            bounding_boxes: List of detected UI elements
        
        Returns:
            Tuple of (action_dict, new_state)
        """
        # Verify the current state by checking UI elements
        verified_state = self._identify_current_state(bounding_boxes)
        
        # If the verified state doesn't match the expected current state, use the verified one
        if verified_state != "unknown" and verified_state != current_state:
            logger.info(f"State mismatch: expected {current_state}, found {verified_state}")
            current_state = verified_state
        
        # Find possible next states from the current state
        possible_transitions = []
        for transition_key in self.transitions:
            if transition_key.startswith(f"{current_state}->"):
                target_state = transition_key.split("->")[1]
                possible_transitions.append(target_state)
        
        if not possible_transitions:
            logger.warning(f"No transitions defined from state {current_state}")
            
            # Fallback behavior: try "initial" state if we're stuck
            if current_state != "initial" and verified_state == "unknown":
                logger.info("Falling back to initial state since no UI elements were recognized")
                return {"type": "wait", "duration": 3}, "initial"
                
            # Another fallback: try to press escape key
            if current_state == "unknown" or verified_state == "unknown":
                logger.info("Pressing ESC key as fallback action for unknown state")
                return {"type": "key", "key": "escape"}, current_state
                
            return {}, current_state
        
        # Get the first possible transition (this can be improved with priority logic)
        next_state = possible_transitions[0]
        logger.info(f"Selected next state: {next_state}")
        
        # Get the action for this transition
        action = self._get_action_for_transition(current_state, next_state, bounding_boxes)
        
        return action, next_state