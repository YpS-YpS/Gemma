# -*- coding: utf-8 -*-
"""
Enhanced Decision Engine module based on Finite State Machine principles.
Supports flexible text matching and state context for any game benchmark.
"""

import logging
import time
from typing import List, Dict, Any, Tuple, Optional, Set

from modules.gemma_client import BoundingBox

logger = logging.getLogger(__name__)

class DecisionEngine:
    """
    FSM-based decision engine with enhanced flexibility for different games.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the decision engine with game-specific configuration."""
        self.config = config
        self.states = config.get("states", {})
        self.transitions = config.get("transitions", {})
        self.fallbacks = config.get("fallbacks", {})
        self.current_state = config.get("initial_state", "initial")
        self.target_state = config.get("target_state", "completed")
        self.game_name = config.get("metadata", {}).get("game_name", "Unknown Game")
        
        # FSM enhancements
        self.state_history = []  # Track visited states
        self.state_context = {}  # Context variables
        self.visited_states = set()  # Set of visited states
        self.transitions_taken = set()  # Track which transitions we've already used
        self.state_start_times = {}  # Track when we entered each state
        self.benchmark_started_at = None
        self.benchmark_completed_at = None
        
        # Build state graph for validation
        self.state_graph = self._build_state_graph()
        
        logger.info(f"DecisionEngine initialized for {self.game_name} with {len(self.states)} states")
        logger.info(f"Initial state: {self.current_state}, Target state: {self.target_state}")
    
    def _build_state_graph(self) -> Dict[str, Set[str]]:
        """
        Build a graph representation of possible state transitions.
        
        Returns:
            Dictionary mapping from_state to set of possible to_states
        """
        graph = {}
        for transition_key in self.transitions:
            try:
                from_state, to_state = transition_key.split("->")
                if from_state not in graph:
                    graph[from_state] = set()
                graph[from_state].add(to_state)
            except ValueError:
                logger.error(f"Invalid transition key format: {transition_key}")
        return graph
    
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
        Find a UI element that matches the state definition with flexible matching.
        
        Args:
            state_def: State definition from the config
            bounding_boxes: List of detected UI elements
        
        Returns:
            Matching BoundingBox or None if no match
        """
        required_elements = state_def.get("required_elements", [])
        
        for required in required_elements:
            req_type = required.get("type", "any")
            req_text = required.get("text", "")
            text_match_type = required.get("text_match", "exact")
            min_confidence = required.get("required_confidence", 0.6)
            
            for bbox in bounding_boxes:
                # Type matching - handle "any" type
                type_match = (req_type == "any" or 
                             not req_type or 
                             bbox.element_type == req_type)
                
                # Text matching with different strategies
                text_match = False
                if bbox.element_text and req_text:
                    if text_match_type == "exact":
                        text_match = req_text.lower() == bbox.element_text.lower()
                    elif text_match_type == "contains":
                        text_match = req_text.lower() in bbox.element_text.lower()
                    elif text_match_type == "startswith":
                        text_match = bbox.element_text.lower().startswith(req_text.lower())
                    elif text_match_type == "endswith":
                        text_match = bbox.element_text.lower().endswith(req_text.lower())
                elif not req_text:  # If no text requirement, consider it a match
                    text_match = True
                
                # Confidence threshold check
                confidence_match = bbox.confidence >= min_confidence
                
                if type_match and text_match and confidence_match:
                    match_details = f"type: '{bbox.element_type}', text: '{bbox.element_text}'"
                    required_details = f"required type: '{req_type}', required text: '{req_text}'"
                    logger.info(f"Found matching element: {match_details} matches {required_details}")
                    return bbox
        
        if required_elements:
            logger.debug(f"No UI elements matched the requirements: {required_elements}")
        return None
    
    def _identify_current_state(self, bounding_boxes: List[BoundingBox]) -> str:
        """
        Identify the current UI state based on detected elements with enhanced context awareness.
        
        Args:
            bounding_boxes: List of detected UI elements
        
        Returns:
            Name of the identified state or "unknown" if no match
        """
        # First, check if we're in a special context-sensitive state
        if self.state_context.get("in_benchmark") and len(self.state_history) > 0:
            prev_state = self.state_history[-1]
            if prev_state == "benchmark_running":
                if self._is_likely_benchmark_results(bounding_boxes):
                    logger.info("Context detection: Identified benchmark_complete based on context")
                    return "benchmark_complete"
        
        # Next, try to identify based on UI elements
        matching_states = []
        for state_name, state_def in self.states.items():
            if self._find_matching_element(state_def, bounding_boxes):
                matching_states.append(state_name)
        
        if not matching_states:
            logger.warning("Could not identify current state from UI elements")
            return "unknown"
        
        # If only one match, return it
        if len(matching_states) == 1:
            logger.info(f"Identified current state: {matching_states[0]}")
            return matching_states[0]
        
        # Multiple matching states - use context to disambiguate
        logger.info(f"Multiple matching states found: {matching_states}, using context to disambiguate")
        
        # Check sequence - prefer states that follow our current position in the workflow
        if len(self.state_history) > 0:
            current = self.state_history[-1]
            for candidate in matching_states:
                transition = f"{current}->{candidate}"
                if transition in self.transitions:
                    logger.info(f"Selected {candidate} based on valid transition from {current}")
                    return candidate
        
        # Handle special case for states that appear multiple times in the flow
        if "benchmark_running" in matching_states and "benchmark_complete" in matching_states:
            if self.state_context.get("benchmark_run"):
                logger.info("Context detection: This is post-benchmark state")
                return "benchmark_complete"
            else:
                logger.info("Context detection: This is benchmark_running state")
                return "benchmark_running"
        
        # Default to first match with a warning
        logger.warning(f"Ambiguous state detection, selecting {matching_states[0]}")
        return matching_states[0]
    
    def _is_likely_benchmark_results(self, bounding_boxes: List[BoundingBox]) -> bool:
        """
        Determine if the current screen is likely showing benchmark results.
        
        Args:
            bounding_boxes: List of detected UI elements
        
        Returns:
            True if this appears to be benchmark results
        """
        # Look for elements that suggest benchmark results
        result_keywords = ["result", "fps", "score", "performance", "benchmark", "complete", "average"]
        
        for bbox in bounding_boxes:
            if bbox.element_text:
                lowercase_text = bbox.element_text.lower()
                if any(keyword in lowercase_text for keyword in result_keywords):
                    logger.info(f"Found likely benchmark result element: {bbox.element_text}")
                    return True
        
        return False
    
    def track_benchmark_timing(self, current_state: str, new_state: str):
        """
        Track benchmark start and end times for reporting.
        
        Args:
            current_state: Current state before transition
            new_state: New state after transition
        """
        if new_state == "benchmark_running" and not self.benchmark_started_at:
            self.benchmark_started_at = time.time()
            self.state_context["in_benchmark"] = True
            logger.info(f"Benchmark started at {time.strftime('%H:%M:%S', time.localtime(self.benchmark_started_at))}")
            
        if current_state == "benchmark_running" and new_state == "benchmark_complete":
            self.benchmark_completed_at = time.time()
            self.state_context["benchmark_run"] = True
            
            if self.benchmark_started_at:
                duration = self.benchmark_completed_at - self.benchmark_started_at
                logger.info(f"Benchmark completed in {duration:.2f} seconds")
                self.state_context["benchmark_duration"] = duration
    
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
        
        # Record this transition
        self.transitions_taken.add(transition_key)
        
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
            element_type = target_element.get("type", "any")
            element_text = target_element.get("text", "")
            text_match_type = target_element.get("text_match", "exact")
            
            # Look for a matching element with the improved matching strategy
            for bbox in bounding_boxes:
                # Type matching - handle "any" type
                type_match = (element_type == "any" or 
                             not element_type or 
                             bbox.element_type == element_type)
                
                # Text matching with different strategies
                text_match = False
                if bbox.element_text and element_text:
                    if text_match_type == "exact":
                        text_match = element_text.lower() == bbox.element_text.lower()
                    elif text_match_type == "contains":
                        text_match = element_text.lower() in bbox.element_text.lower()
                    elif text_match_type == "startswith":
                        text_match = bbox.element_text.lower().startswith(element_text.lower())
                    elif text_match_type == "endswith":
                        text_match = bbox.element_text.lower().endswith(element_text.lower())
                elif not element_text:  # If no text requirement, consider it a match
                    text_match = True
                
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
            
            # If we're here, we couldn't find a matching element
            logger.warning(f"Could not find matching element for click in transition {transition_key}")
            
            # Check for fallback coordinates
            fallback_coords = transition.get("fallback_coords", {})
            if fallback_coords:
                x = fallback_coords.get("x", 0)
                y = fallback_coords.get("y", 0)
                logger.info(f"Using fallback coordinates: ({x}, {y}) for transition {transition_key}")
                return {
                    "type": "click",
                    "x": x,
                    "y": y
                }
                
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
            
            # If this is the benchmark running wait, set the context flag
            if from_state == "benchmark_running" or to_state == "benchmark_complete":
                self.state_context["in_benchmark"] = True
                logger.info("Setting in_benchmark context flag to True")
                
            return {
                "type": "wait",
                "duration": duration
            }
        
        logger.warning(f"Unknown action type: {action_type}")
        return {}
    
    def _select_next_state(self, current_state: str) -> str:
        """
        Select the next state to transition to based on the current state.
        
        Args:
            current_state: Current state name
            
        Returns:
            Next state name or empty string if no valid transition
        """
        # Find possible next states from the current state
        possible_transitions = []
        for transition_key in self.transitions:
            if transition_key.startswith(f"{current_state}->"):
                target_state = transition_key.split("->")[1]
                possible_transitions.append(target_state)
        
        if not possible_transitions:
            logger.warning(f"No transitions defined from state {current_state}")
            return ""
        
        # Apply context-aware selection if we have multiple options
        if len(possible_transitions) > 1:
            # Prefer states we haven't visited yet
            unvisited = [s for s in possible_transitions if s not in self.visited_states]
            if unvisited:
                selected = unvisited[0]
                logger.info(f"Selected unvisited state: {selected}")
                return selected
                
            # If all have been visited, use other heuristics
            # ...
        
        # Default to first option
        selected = possible_transitions[0]
        logger.info(f"Selected next state: {selected}")
        return selected
    
    def get_fallback_action(self, current_state: str) -> Dict[str, Any]:
        """
        Get a fallback action for error recovery.
        
        Args:
            current_state: Current state name
            
        Returns:
            Fallback action dictionary
        """
        # Check for state-specific fallback
        state_fallback = self.fallbacks.get(current_state, None)
        if state_fallback:
            logger.info(f"Using state-specific fallback for {current_state}")
            return state_fallback
        
        # Use general fallback
        general_fallback = self.fallbacks.get("general", {})
        if general_fallback:
            logger.info("Using general fallback action")
            return general_fallback
        
        # Default to Escape key
        logger.info("Using default escape key fallback")
        return {"type": "key", "key": "escape"}
    
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
        # Add to state history if state has changed
        if not self.state_history or self.state_history[-1] != current_state:
            self.state_history.append(current_state)
            self.visited_states.add(current_state)
            self.state_start_times[current_state] = time.time()
            logger.info(f"Updated state history: {' -> '.join(self.state_history)}")
        
        # Verify the current state by checking UI elements
        verified_state = self._identify_current_state(bounding_boxes)
        
        # If the verified state doesn't match the expected current state, use the verified one
        if verified_state != "unknown" and verified_state != current_state:
            logger.info(f"State mismatch: expected {current_state}, found {verified_state}")
            current_state = verified_state
            # Update history with the corrected state
            if self.state_history and self.state_history[-1] != current_state:
                self.state_history.append(current_state)
                self.visited_states.add(current_state)
                self.state_start_times[current_state] = time.time()
        
        # Check if we've reached the target state
        if current_state == self.target_state:
            logger.info(f"Reached target state: {self.target_state}")
            return {}, current_state
        
        # Select the next state to transition to
        next_state = self._select_next_state(current_state)
        
        if not next_state:
            # No valid transition found - try fallbacks
            
            # Fallback behavior: try "initial" state if we're stuck
            if current_state != "initial" and verified_state == "unknown":
                logger.info("Falling back to initial state since no UI elements were recognized")
                return {"type": "wait", "duration": 3}, "initial"
                
            # Another fallback: try to press escape key
            if current_state == "unknown" or verified_state == "unknown":
                fallback_action = self.get_fallback_action(current_state)
                logger.info(f"Using fallback action for unknown state: {fallback_action}")
                return fallback_action, current_state
                
            return {}, current_state
        
        # Get the action for this transition
        action = self._get_action_for_transition(current_state, next_state, bounding_boxes)
        
        # Track benchmark timing
        self.track_benchmark_timing(current_state, next_state)
        
        return action, next_state