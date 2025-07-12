"""
Enhanced network communication module for ARL-SUT interaction.
Handles all network operations with support for process ID tracking.
"""

import socket
import json
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class NetworkManager:
    """Enhanced network manager for communication with the SUT."""
    
    def __init__(self, sut_ip: str, sut_port: int):
        """
        Initialize the network manager.
        
        Args:
            sut_ip: IP address of the system under test
            sut_port: Port number for communication
        """
        self.sut_ip = sut_ip
        self.sut_port = sut_port
        self.base_url = f"http://{sut_ip}:{sut_port}"
        self.session = requests.Session()
        logger.info(f"NetworkManager initialized with SUT at {self.base_url}")
        
        # Verify connection
        try:
            self._check_connection()
        except Exception as e:
            logger.error(f"Failed to connect to SUT: {str(e)}")
            raise
    
    def _check_connection(self) -> bool:
        """
        Check if the SUT is reachable.
        
        Returns:
            True if connection is successful
        
        Raises:
            ConnectionError: If SUT is not reachable
        """
        try:
            response = self.session.get(f"{self.base_url}/status", timeout=5)
            response.raise_for_status()
            logger.info("Successfully connected to SUT")
            return True
        except requests.RequestException as e:
            logger.error(f"Connection check failed: {str(e)}")
            raise ConnectionError(f"Cannot connect to SUT at {self.base_url}: {str(e)}")
    
    def send_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send an action command to the SUT with enhanced error handling.
        
        Args:
            action: Dictionary containing action details
                   Example: {"type": "click", "x": 100, "y": 200, "button": "left"}
        
        Returns:
            Response from the SUT as a dictionary
        
        Raises:
            RequestException: If the request fails
        """
        try:
            # Handle special case for launch actions with process ID
            if action.get("type") == "launch" and "data" in action:
                return self.launch_game_enhanced(action["data"])
            
            response = self.session.post(
                f"{self.base_url}/action",
                json=action,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Action sent: {action}, Response: {result}")
            return result
        except requests.RequestException as e:
            logger.error(f"Failed to send action {action}: {str(e)}")
            raise
    
    def get_screenshot(self) -> bytes:
        """
        Request a screenshot from the SUT.
        
        Returns:
            Raw screenshot data as bytes
        
        Raises:
            RequestException: If the request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/screenshot",
                timeout=15
            )
            response.raise_for_status()
            logger.debug("Screenshot retrieved successfully")
            return response.content
        except requests.RequestException as e:
            logger.error(f"Failed to get screenshot: {str(e)}")
            raise
    
    def launch_game(self, game_path: str) -> Dict[str, Any]:
        """
        Request the SUT to launch a game (legacy method).
        
        Args:
            game_path: Path to the game executable on the SUT
        
        Returns:
            Response from the SUT as a dictionary
        
        Raises:
            RequestException: If the request fails
        """
        try:
            response = self.session.post(
                f"{self.base_url}/launch",
                json={"path": game_path},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Game launch request sent: {game_path}")
            return result
        except requests.RequestException as e:
            logger.error(f"Failed to launch game {game_path}: {str(e)}")
            raise
    
    def launch_game_enhanced(self, launch_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Request the SUT to launch a game with enhanced process tracking.
        
        Args:
            launch_data: Dictionary containing path and optional process_id
                        Example: {"path": "game.exe", "process_id": "game_process"}
        
        Returns:
            Response from the SUT as a dictionary
        
        Raises:
            RequestException: If the request fails
        """
        try:
            response = self.session.post(
                f"{self.base_url}/launch",
                json=launch_data,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            game_path = launch_data.get("path", "unknown")
            process_id = launch_data.get("process_id")
            
            if process_id:
                logger.info(f"Enhanced game launch request sent: {game_path} (process: {process_id})")
            else:
                logger.info(f"Game launch request sent: {game_path}")
                
            return result
        except requests.RequestException as e:
            logger.error(f"Failed to launch game with enhanced tracking: {str(e)}")
            raise
    
    def get_game_status(self) -> Dict[str, Any]:
        """
        Get detailed game process status from the SUT.
        
        Returns:
            Game status information as a dictionary
        
        Raises:
            RequestException: If the request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/game_status",
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            logger.debug("Game status retrieved successfully")
            return result
        except requests.RequestException as e:
            logger.error(f"Failed to get game status: {str(e)}")
            raise
    
    def list_processes(self) -> Dict[str, Any]:
        """
        Get a list of running processes from the SUT.
        
        Returns:
            Process list as a dictionary
        
        Raises:
            RequestException: If the request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/processes",
                timeout=15
            )
            response.raise_for_status()
            result = response.json()
            logger.debug("Process list retrieved successfully")
            return result
        except requests.RequestException as e:
            logger.error(f"Failed to get process list: {str(e)}")
            raise
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information from the SUT.
        
        Returns:
            System information as a dictionary
        
        Raises:
            RequestException: If the request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/system_info",
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            logger.debug("System info retrieved successfully")
            return result
        except requests.RequestException as e:
            logger.error(f"Failed to get system info: {str(e)}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a comprehensive health check of the SUT service.
        
        Returns:
            Health status as a dictionary
        
        Raises:
            RequestException: If the request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=5
            )
            response.raise_for_status()
            result = response.json()
            logger.debug("Health check completed successfully")
            return result
        except requests.RequestException as e:
            logger.error(f"Health check failed: {str(e)}")
            raise
    
    def terminate_game(self) -> Dict[str, Any]:
        """
        Request the SUT to terminate the currently running game.
        
        Returns:
            Response from the SUT as a dictionary
        
        Raises:
            RequestException: If the request fails
        """
        try:
            response = self.session.post(
                f"{self.base_url}/action",
                json={"type": "terminate_game"},
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            logger.info("Game termination request sent")
            return result
        except requests.RequestException as e:
            logger.error(f"Failed to terminate game: {str(e)}")
            raise
    
    def send_enhanced_action(self, action_type: str, **kwargs) -> Dict[str, Any]:
        """
        Send an enhanced action with additional parameters.
        
        Args:
            action_type: Type of action to perform
            **kwargs: Additional parameters for the action
        
        Returns:
            Response from the SUT as a dictionary
        
        Raises:
            RequestException: If the request fails
        """
        action = {"type": action_type, **kwargs}
        return self.send_action(action)
    
    def right_click(self, x: int, y: int, move_duration: float = 0.5, click_delay: float = 1.0) -> Dict[str, Any]:
        """
        Perform a right-click at the specified coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            move_duration: Time to move to the coordinate
            click_delay: Delay before clicking
        
        Returns:
            Response from the SUT as a dictionary
        """
        return self.send_enhanced_action(
            "click",
            x=x, y=y, 
            button="right",
            move_duration=move_duration,
            click_delay=click_delay
        )
    
    def double_click(self, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        """
        Perform a double-click at the specified coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            button: Mouse button to use ("left" or "right")
        
        Returns:
            Response from the SUT as a dictionary
        """
        return self.send_enhanced_action(
            "double_click",
            x=x, y=y,
            button=button
        )
    
    def send_hotkey(self, keys: list) -> Dict[str, Any]:
        """
        Send a hotkey combination.
        
        Args:
            keys: List of keys to press simultaneously
        
        Returns:
            Response from the SUT as a dictionary
        """
        return self.send_enhanced_action("hotkey", keys=keys)
    
    def scroll(self, x: int, y: int, direction: str = "up", clicks: int = 3) -> Dict[str, Any]:
        """
        Scroll at the specified coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            direction: Scroll direction ("up" or "down")
            clicks: Number of scroll clicks
        
        Returns:
            Response from the SUT as a dictionary
        """
        return self.send_enhanced_action(
            "scroll",
            x=x, y=y,
            direction=direction,
            clicks=clicks
        )
    
    def close(self):
        """Close the network session."""
        self.session.close()
        logger.info("Network session closed")