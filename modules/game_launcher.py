# -*- coding: utf-8 -*-
"""
Game Launcher module for starting games on the SUT.
"""

import logging
from typing import Dict, Any

from modules.network import NetworkManager

logger = logging.getLogger(__name__)

class GameLauncher:
    """Handles launching games on the SUT."""
    
    def __init__(self, network_manager: NetworkManager):
        """
        Initialize the game launcher.
        
        Args:
            network_manager: NetworkManager instance for communication with SUT
        """
        self.network_manager = network_manager
        logger.info("GameLauncher initialized")
    
    def launch(self, game_path: str) -> bool:
        """
        Launch a game on the SUT.
        
        Args:
            game_path: Path to the game executable on the SUT
        
        Returns:
            True if the game was successfully launched
        
        Raises:
            RuntimeError: If the game fails to launch
        """
        try:
            # Send launch command to SUT
            response = self.network_manager.launch_game(game_path)
            
            # Check response
            if response.get("status") == "success":
                logger.info(f"Game launched successfully: {game_path}")
                return True
            else:
                error_msg = response.get("error", "Unknown error")
                logger.error(f"Failed to launch game: {error_msg}")
                raise RuntimeError(f"Game launch failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error launching game: {str(e)}")
            raise RuntimeError(f"Game launch error: {str(e)}")
    
    def terminate(self) -> bool:
        """
        Terminate the currently running game on the SUT.
        
        Returns:
            True if the game was successfully terminated
        
        Raises:
            RuntimeError: If the game fails to terminate
        """
        try:
            # Send terminate command to SUT
            response = self.network_manager.send_action({
                "type": "terminate_game"
            })
            
            # Check response
            if response.get("status") == "success":
                logger.info("Game terminated successfully")
                return True
            else:
                error_msg = response.get("error", "Unknown error")
                logger.error(f"Failed to terminate game: {error_msg}")
                raise RuntimeError(f"Game termination failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error terminating game: {str(e)}")
            raise RuntimeError(f"Game termination error: {str(e)}")