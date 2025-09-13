# -*- coding: utf-8 -*-
"""
Screenshot management module for capturing and saving screenshots from the SUT.
"""

import os
import logging
from typing import Optional
from pathlib import Path

from modules.network import NetworkManager

logger = logging.getLogger(__name__)

class ScreenshotManager:
    """Manages screenshot operations."""
    
    def __init__(self, network_manager: NetworkManager):
        """
        Initialize the screenshot manager.
        
        Args:
            network_manager: NetworkManager instance for communication with SUT
        """
        self.network_manager = network_manager
        logger.info("ScreenshotManager initialized")
    
    def capture(self, output_path: str) -> bool:
        """
        Capture a screenshot from the SUT and save it to the specified path.
        
        Args:
            output_path: Path where the screenshot should be saved
        
        Returns:
            True if the screenshot was successfully captured and saved
        
        Raises:
            IOError: If there's an error saving the screenshot
        """
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Get screenshot from the SUT
            screenshot_data = self.network_manager.get_screenshot()
            
            # Save the screenshot
            with open(output_path, 'wb') as f:
                f.write(screenshot_data)
            
            logger.info(f"Screenshot saved to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to capture or save screenshot: {str(e)}")
            raise IOError(f"Screenshot capture failed: {str(e)}")
    
    def capture_region(self, output_path: str, x: int, y: int, width: int, height: int) -> bool:
        """
        Capture a specific region of the screen from the SUT.
        This is a placeholder for a potential future feature that would require SUT-side implementation.
        
        Args:
            output_path: Path where the screenshot should be saved
            x, y: Top-left coordinates of the region
            width, height: Dimensions of the region
        
        Returns:
            True if the region was successfully captured and saved
        
        Raises:
            NotImplementedError: This feature is not yet implemented
        """
        # This would require additional API support on the SUT side
        raise NotImplementedError("Region capture is not yet implemented")