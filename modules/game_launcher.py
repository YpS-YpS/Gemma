"""
Enhanced Game Launcher module for starting games on the SUT with process ID support.
"""

import logging
from typing import Dict, Any, List

from modules.network import NetworkManager

logger = logging.getLogger(__name__)

class GameLauncher:
    """Handles launching games on the SUT with enhanced process tracking."""
    
    def __init__(self, network_manager: NetworkManager):
        """
        Initialize the game launcher.
        
        Args:
            network_manager: NetworkManager instance for communication with SUT
        """
        self.network_manager = network_manager
        logger.info("GameLauncher initialized with enhanced process tracking")
    
    def launch(self, game_path: str, process_id: str = None) -> bool:
        """
        Launch a game on the SUT with optional process ID specification.
        
        Args:
            game_path: Path to the game executable on the SUT
            process_id: Expected process name (different from executable name)
        
        Returns:
            True if the game was successfully launched
        
        Raises:
            RuntimeError: If the game fails to launch
        """
        try:
            # Prepare launch command with process ID if provided
            launch_data = {"path": game_path}
            if process_id:
                launch_data["process_id"] = process_id
                logger.info(f"Launching game with process ID tracking: {process_id}")
            
            # Send launch command to SUT
            response = self.network_manager.send_action({
                "type": "launch",
                "data": launch_data
            })
            
            # For backward compatibility, also try the old launch method
            if "error" in response:
                logger.info("Trying legacy launch method...")
                response = self.network_manager.launch_game(game_path)
            
            # Check response
            if response.get("status") == "success":
                logger.info(f"Game launched successfully: {game_path}")
                
                # Log additional process information if available
                if "game_process_pid" in response:
                    logger.info(f"Game process PID: {response['game_process_pid']}")
                if "game_process_name" in response:
                    logger.info(f"Game process name: {response['game_process_name']}")
                if "warning" in response:
                    logger.warning(f"Launch warning: {response['warning']}")
                
                return True
            else:
                error_msg = response.get("error", "Unknown error")
                logger.error(f"Failed to launch game: {error_msg}")
                raise RuntimeError(f"Game launch failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error launching game: {str(e)}")
            raise RuntimeError(f"Game launch error: {str(e)}")
    
    def launch_with_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Launch a game using metadata from configuration file.
        
        Args:
            metadata: Game metadata dictionary containing path and optional process_id
        
        Returns:
            True if the game was successfully launched
        
        Raises:
            RuntimeError: If the game fails to launch or required metadata is missing
        """
        try:
            # Extract required path
            game_path = metadata.get("path")
            if not game_path:
                raise RuntimeError("Game path not found in metadata")
            
            # Extract optional process_id
            process_id = metadata.get("process_id")
            
            if process_id:
                logger.info(f"Using process ID from metadata: {process_id}")
            else:
                logger.info("No process_id specified in metadata, using executable name")
            
            return self.launch(game_path, process_id)
            
        except Exception as e:
            logger.error(f"Error launching game with metadata: {str(e)}")
            raise RuntimeError(f"Game launch with metadata error: {str(e)}")
    
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
    
    def get_game_status(self) -> Dict[str, Any]:
        """
        Get the current status of the game process on the SUT.
        
        Returns:
            Dictionary containing game process status information
        
        Raises:
            RuntimeError: If status check fails
        """
        try:
            # Try to get game status from enhanced SUT service
            try:
                response = self.network_manager.session.get(
                    f"{self.network_manager.base_url}/game_status",
                    timeout=10
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("status") == "success":
                    return result.get("game_status", {})
                else:
                    logger.warning("Could not get detailed game status")
                    
            except Exception as e:
                logger.debug(f"Enhanced game status not available: {str(e)}")
            
            # Fallback to basic status check
            return {"basic_status": "Service available but enhanced status not supported"}
            
        except Exception as e:
            logger.error(f"Error getting game status: {str(e)}")
            raise RuntimeError(f"Game status check error: {str(e)}")
    
    def list_processes(self) -> List[Dict[str, Any]]:
        """
        Get a list of running processes on the SUT for debugging.
        
        Returns:
            List of process information dictionaries
        
        Raises:
            RuntimeError: If process listing fails
        """
        try:
            response = self.network_manager.session.get(
                f"{self.network_manager.base_url}/processes",
                timeout=15
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("status") == "success":
                processes = result.get("processes", [])
                logger.info(f"Retrieved {len(processes)} processes from SUT")
                return processes
            else:
                error_msg = result.get("error", "Unknown error")
                raise RuntimeError(f"Process listing failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error listing processes: {str(e)}")
            raise RuntimeError(f"Process listing error: {str(e)}")