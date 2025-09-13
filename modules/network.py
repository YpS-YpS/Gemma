# -*- coding: utf-8 -*-
"""
Network communication module for ARL-SUT interaction.
Handles all network operations between the development PC and the system under test.
"""

import socket
import json
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class NetworkManager:
    """Manages network communication with the SUT."""
    
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
        Send an action command to the SUT.
        
        Args:
            action: Dictionary containing action details
                   Example: {"type": "click", "x": 100, "y": 200}
        
        Returns:
            Response from the SUT as a dictionary
        
        Raises:
            RequestException: If the request fails
        """
        try:
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
    
    def get_screen_resolution(self) -> tuple[int, int]:
        """
        Get the screen resolution from the SUT.
        
        Returns:
            Tuple of (width, height)
        
        Raises:
            RequestException: If the request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/screen_info",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "success":
                width = data.get("screen_width")
                height = data.get("screen_height")
                logger.info(f"Screen resolution retrieved: {width}x{height}")
                return width, height
            else:
                raise Exception(f"SUT returned error: {data.get('error', 'Unknown error')}")
                
        except requests.RequestException as e:
            logger.error(f"Failed to get screen resolution: {str(e)}")
            raise
    
    def launch_game(self, game_path: str) -> Dict[str, Any]:
        """
        Request the SUT to launch a game.
        
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
    
    def close(self):
        """Close the network session."""
        self.session.close()
        logger.info("Network session closed")