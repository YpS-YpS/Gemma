"""
Client for interacting with the Omniparser server.
Sends screenshots and receives UI element detections.
"""

import os
import base64
import logging
import requests
import json
import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from io import BytesIO
from PIL import Image

from modules.gemma_client import BoundingBox  # Reuse the BoundingBox class

logger = logging.getLogger(__name__)

class OmniparserClient:
    """Client for the Omniparser API server."""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        """
        Initialize the Omniparser client.
        
        Args:
            api_url: URL of the Omniparser API server
        """
        self.api_url = api_url
        self.session = requests.Session()
        # Assuming 1920x1080 resolution - adjust as needed for your target resolution
        self.screen_width = 2560
        self.screen_height = 1600
        logger.info(f"OmniparserClient initialized with API URL: {api_url}")
        
        # Test connection to the API
        try:
            self._test_connection()
            logger.info("Successfully connected to Omniparser API")
        except Exception as e:
            logger.error(f"Failed to connect to Omniparser API: {str(e)}")
            logger.error(f"Please ensure Omniparser server is running at {api_url}")
    
    def _test_connection(self):
        """Test connection to the API."""
        response = self.session.get(f"{self.api_url}/probe")
        response.raise_for_status()
        return response.json()
    
    def _encode_image(self, image_path: str) -> str:
        """
        Encode an image file to base64.
        
        Args:
            image_path: Path to the image file
        
        Returns:
            Base64-encoded image string
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def _parse_omniparser_response(self, response_data: Dict) -> List[BoundingBox]:
        """
        Parse the response from Omniparser into BoundingBox objects.
        
        Args:
            response_data: Response JSON from Omniparser
            
        Returns:
            List of BoundingBox objects
        """
        bounding_boxes = []
        
        # Extract parsed content list from response
        parsed_content_list = response_data.get("parsed_content_list", [])
        logger.info(f"Omniparser returned {len(parsed_content_list)} items in parsed_content_list")
        
        # Log first item as sample if available
        if parsed_content_list and len(parsed_content_list) > 0:
            logger.debug(f"First item example: {json.dumps(parsed_content_list[0], indent=2)}")
        
        # Process each detected element
        for i, element in enumerate(parsed_content_list):
            try:
                # Process only elements that have bbox data
                if 'bbox' in element:
                    # Get normalized coordinates (0-1 range)
                    bbox_coords = element['bbox']
                    logger.debug(f"Element {i} bbox: {bbox_coords}")
                    
                    # Omniparser uses normalized coordinates [x1, y1, x2, y2]
                    x1, y1, x2, y2 = bbox_coords
                    
                    # Convert normalized to absolute coordinates
                    abs_x1 = int(x1 * self.screen_width)
                    abs_y1 = int(y1 * self.screen_height)
                    abs_x2 = int(x2 * self.screen_width)
                    abs_y2 = int(y2 * self.screen_height)
                    
                    # Check for interactivity - prefer interactive elements
                    is_interactive = element.get('interactivity', False)
                    
                    # Only include interactive elements if they have content
                    if is_interactive and element.get('content'):
                        # Create BoundingBox object
                        if 'bbox' in element:
                            # Create BoundingBox object for ALL elements
                            bbox = BoundingBox(
                                x=abs_x1,
                                y=abs_y1,
                                width=abs_x2 - abs_x1,
                                height=abs_y2 - abs_y1,
                                confidence=1.0,
                                element_type=element.get('type', 'unknown'),
                                element_text=element.get('content', '')
                            )
                            bounding_boxes.append(bbox)
                        logger.debug(f"Added interactive element: {element.get('content')}")
                else:
                    logger.debug(f"Element {i} has no bbox field, skipping")
                    
            except (KeyError, ValueError, IndexError) as e:
                logger.warning(f"Error parsing element {i}: {str(e)}")
        
        logger.info(f"Successfully extracted {len(bounding_boxes)} interactive UI elements")
        return bounding_boxes
    
    def _format_bounding_boxes(self, bboxes: List[BoundingBox]) -> str:
        """
        Format bounding boxes into a readable string for logging.
        
        Args:
            bboxes: List of BoundingBox objects
            
        Returns:
            Formatted string representation
        """
        if not bboxes:
            return "No UI elements detected"
            
        formatted = []
        for i, bbox in enumerate(bboxes):
            element_text = bbox.element_text if bbox.element_text else "N/A"
            # Truncate long text
            if element_text and len(element_text) > 30:
                element_text = element_text[:27] + "..."
                
            formatted.append(
                f"[{i+1}] {bbox.element_type} at ({bbox.x},{bbox.y},{bbox.width}x{bbox.height}): '{element_text}'"
            )
        
        return "\n".join(formatted)
    
    def detect_ui_elements(self, image_path: str) -> List[BoundingBox]:
        """
        Send an image to Omniparser and get UI element detections.
        
        Args:
            image_path: Path to the screenshot image
        
        Returns:
            List of detected UI elements with bounding boxes
        
        Raises:
            RequestException: If the API request fails
            ValueError: If the response cannot be parsed
        """
        try:
            # Check if the image file exists
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")
            
            # Encode the image
            base64_image = self._encode_image(image_path)
            
            # Prepare the payload for Omniparser
            payload = {
                "base64_image": base64_image
            }
            
            # Send the request to Omniparser API
            logger.info(f"Sending request to {self.api_url}/parse/")
            response = self.session.post(
                f"{self.api_url}/parse/",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60  # Longer timeout for image processing
            )
            response.raise_for_status()
            
            # Parse the response
            response_data = response.json()
            
            # Create a clean copy without the base64 image data
            clean_response = response_data.copy()
            if "som_image_base64" in clean_response:
                clean_response.pop("som_image_base64")
                clean_response["som_image_base64_present"] = True
            
            # Save the clean JSON response to a file
            json_path = os.path.splitext(image_path)[0] + ".json"
            with open(json_path, "w", encoding="utf-8") as json_file:
                json.dump(clean_response, json_file, indent=2)
            logger.info(f"Saved clean Omniparser JSON response to {json_path}")

            # Log performance metrics if available
            if "latency" in response_data:
                logger.info(f"Omniparser processing time: {response_data['latency']:.2f} seconds")
            
            # Extract and convert bounding boxes
            bounding_boxes = self._parse_omniparser_response(response_data)
            
            # Save the annotated image if provided
            if "som_image_base64" in response_data:
                try:
                    annotated_dir = os.path.dirname(image_path)
                    annotated_path = os.path.join(annotated_dir, f"omniparser_{os.path.basename(image_path)}")
                    
                    # Decode and save the annotated image
                    img_data = base64.b64decode(response_data["som_image_base64"])
                    with open(annotated_path, "wb") as f:
                        f.write(img_data)
                    logger.info(f"Saved Omniparser annotated image to {annotated_path}")
                except Exception as e:
                    logger.warning(f"Failed to save annotated image: {str(e)}")
            
            # Log decision engine input data
            logger.debug("=== DECISION ENGINE INPUT DATA ===")
            logger.debug(f"Sending {len(bounding_boxes)} UI elements to decision engine:")
            for i, bbox in enumerate(bounding_boxes):
                logger.debug(f"  Element {i+1}:")
                logger.debug(f"    Type: {bbox.element_type}")
                logger.debug(f"    Text: '{bbox.element_text}'")
                logger.debug(f"    Position: (x={bbox.x}, y={bbox.y}, w={bbox.width}, h={bbox.height})")
            logger.debug("=== END OF DECISION ENGINE INPUT ===")

            # Log detected elements in compact format
            formatted_boxes = self._format_bounding_boxes(bounding_boxes)
            logger.info(f"Detected {len(bounding_boxes)} UI elements in {image_path}:")
            for line in formatted_boxes.split('\n'):
                logger.info(f"  {line}")

            return bounding_boxes
            
        except requests.RequestException as e:
            logger.error(f"Omniparser API request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse Omniparser response: {str(e)}")
            raise ValueError(f"Invalid response from Omniparser API: {str(e)}")
    
    def close(self):
        """Close the session."""
        self.session.close()
        logger.info("Omniparser client session closed")