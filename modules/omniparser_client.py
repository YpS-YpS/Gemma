"""
Client for interacting with the Omniparser server.
Sends screenshots and receives UI element detections.
Enhanced with streamlined annotation handling to eliminate redundant processing.
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
    """Client for the Omniparser API server with streamlined annotation handling."""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        """
        Initialize the Omniparser client.
        
        Args:
            api_url: URL of the Omniparser API server
        """
        self.api_url = api_url
        self.session = requests.Session()
        # Assuming 2560x1600 resolution - adjust as needed for your target resolution
        self.screen_width = 1920
        self.screen_height = 1080
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
        COMPREHENSIVE filtering to capture ALL useful elements for gaming performance analysis.
        
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
        
        # Counters for different element types
        interactive_count = 0
        text_count = 0
        performance_data_count = 0
        
        # Process each detected element
        for i, element in enumerate(parsed_content_list):
            try:
                # Process ALL elements that have bbox data
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
                    
                    # Get element properties
                    is_interactive = element.get('interactivity', False)
                    element_type = element.get('type', 'unknown')
                    element_content = element.get('content', '').strip()
                    
                    # COMPREHENSIVE INCLUSION LOGIC - Capture everything useful
                    should_include = False
                    inclusion_reason = ""
                    
                    if is_interactive:
                        # Include ALL interactive elements (UI buttons, icons, etc.)
                        should_include = True
                        inclusion_reason = "interactive"
                        interactive_count += 1
                    elif element_content:
                        # Include ALL elements with text content - critical for performance data
                        should_include = True
                        inclusion_reason = "has_content"
                        text_count += 1
                        
                        # Check if this looks like performance data
                        if any(keyword in element_content.lower() for keyword in [
                            'fps', 'avg', 'p1', 'p99', 'frame', 'ms', 'hz', 'performance',
                            'rendering', 'simulation', 'client', 'server', 'prof'
                        ]):
                            performance_data_count += 1
                            inclusion_reason = "performance_data"
                    elif element_type in ['icon', 'image', 'graphic', 'button']:
                        # Include visual elements that might be important for state detection
                        should_include = True
                        inclusion_reason = "visual_element"
                    elif (abs_x2 - abs_x1) > 30 and (abs_y2 - abs_y1) > 15:
                        # Include reasonably-sized elements (might be containers, progress bars, etc.)
                        should_include = True
                        inclusion_reason = "significant_size"
                    
                    if should_include:
                        # Create BoundingBox object
                        bbox = BoundingBox(
                            x=abs_x1,
                            y=abs_y1,
                            width=abs_x2 - abs_x1,
                            height=abs_y2 - abs_y1,
                            confidence=1.0,
                            element_type=element_type,
                            element_text=element_content
                        )
                        bounding_boxes.append(bbox)
                        
                        # Log important elements
                        if inclusion_reason == "performance_data":
                            logger.info(f"🎯 PERFORMANCE DATA: '{element_content[:50]}...'")
                        else:
                            logger.debug(f"Added element ({inclusion_reason}): type='{element_type}', content='{element_content[:30]}...'")
                    else:
                        logger.debug(f"Skipped element {i}: type='{element_type}', interactive={is_interactive}, content='{element_content[:20]}...'")
                        
                else:
                    logger.debug(f"Element {i} has no bbox field, skipping")
                    
            except (KeyError, ValueError, IndexError) as e:
                logger.warning(f"Error parsing element {i}: {str(e)}")
        
        # Enhanced logging with breakdown
        logger.info(f"Successfully extracted {len(bounding_boxes)} UI elements:")
        logger.info(f"  - Interactive elements: {interactive_count}")
        logger.info(f"  - Text/content elements: {text_count}")
        logger.info(f"  - Performance data elements: {performance_data_count}")
        logger.info(f"  - Total useful elements: {len(bounding_boxes)}")
        
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
    
    def detect_ui_elements(self, image_path: str, annotation_path: str = None) -> List[BoundingBox]:
        """
        Send an image to Omniparser and get UI element detections with streamlined annotation handling.
        
        Args:
            image_path: Path to the screenshot image
            annotation_path: Optional path to save server annotation (NEW STREAMLINED APPROACH)
        
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
            
            # Log performance metrics if available
            if "latency" in response_data:
                logger.info(f"Omniparser processing time: {response_data['latency']:.2f} seconds")
            
            # Extract and convert bounding boxes
            bounding_boxes = self._parse_omniparser_response(response_data)
            
            # STREAMLINED ANNOTATION HANDLING - Single source of truth
            if "som_image_base64" in response_data:
                if annotation_path:
                    # Save server annotation to the specified path (NEW STREAMLINED APPROACH)
                    try:
                        os.makedirs(os.path.dirname(annotation_path), exist_ok=True)
                        img_data = base64.b64decode(response_data["som_image_base64"])
                        with open(annotation_path, "wb") as f:
                            f.write(img_data)
                        logger.info(f"Saved Omniparser server annotation to {annotation_path}")
                    except Exception as e:
                        logger.warning(f"Failed to save server annotation: {str(e)}")
                else:
                    # Backward compatibility: save with old naming convention for non-SimpleAutomation usage
                    try:
                        annotated_dir = os.path.dirname(image_path)
                        fallback_path = os.path.join(annotated_dir, f"omniparser_{os.path.basename(image_path)}")
                        img_data = base64.b64decode(response_data["som_image_base64"])
                        with open(fallback_path, "wb") as f:
                            f.write(img_data)
                        logger.info(f"Saved Omniparser annotation to {fallback_path} (fallback mode)")
                    except Exception as e:
                        logger.warning(f"Failed to save fallback annotation: {str(e)}")
            
            # Save clean JSON response (without base64 data for debugging)
            self._save_clean_json_response(response_data, image_path)
            
            # Log detected elements in compact format
            logger.info(f"Detected {len(bounding_boxes)} UI elements from Omniparser server")
            self._log_detected_elements(bounding_boxes)
            
            return bounding_boxes
            
        except requests.RequestException as e:
            logger.error(f"Omniparser API request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse Omniparser response: {str(e)}")
            raise ValueError(f"Invalid response from Omniparser API: {str(e)}")
    
    def _save_clean_json_response(self, response_data: Dict, image_path: str):
        """Save JSON response without base64 image data for debugging."""
        clean_response = response_data.copy()
        if "som_image_base64" in clean_response:
            clean_response.pop("som_image_base64")
            clean_response["som_image_base64_present"] = True
        
        json_path = os.path.splitext(image_path)[0] + ".json"
        with open(json_path, "w", encoding="utf-8") as json_file:
            json.dump(clean_response, json_file, indent=2)
        logger.debug(f"Saved clean JSON response to {json_path}")
    
    def _log_detected_elements(self, bounding_boxes: List[BoundingBox]):
        """Log detected elements in a compact format."""
        if bounding_boxes:
            for i, bbox in enumerate(bounding_boxes):
                element_text = bbox.element_text if bbox.element_text else "(no text)"
                if len(element_text) > 30:
                    element_text = element_text[:27] + "..."
                logger.info(f"  [{i+1}] {bbox.element_type} at ({bbox.x},{bbox.y},{bbox.width}x{bbox.height}): '{element_text}'")
        else:
            logger.info("  No UI elements detected")
    
    def close(self):
        """Close the session."""
        self.session.close()
        logger.info("Omniparser client session closed")