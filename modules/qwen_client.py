# -*- coding: utf-8 -*-
"""
Client for interacting with the Qwen VL model running in LMStudio.
Uses the OpenAI-compatible API to send images and get UI element detections.
"""

import os
import base64
import logging
import requests
import json
import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from modules.gemma_client import BoundingBox  # Reuse the BoundingBox class

logger = logging.getLogger(__name__)

class QwenClient:
    """Client for the Qwen VL API running in LM Studio."""
    
    def __init__(self, api_url: str = "http://127.0.0.1:1234"):
        """
        Initialize the Qwen client.
        
        Args:
            api_url: URL of the LM Studio API (default: http://127.0.0.1:1234)
        """
        self.api_url = api_url
        self.session = requests.Session()
        self.system_prompt = """You are a computer vision system specialized in identifying UI elements in game screenshots with extreme precision.
For each UI element you detect, return a JSON object with these properties:
- box: {x, y, width, height} coordinates with (0,0) at top-left. Be extremely precise with coordinates.
- type: the element type (button, label, slider, checkbox, etc.)
- text: any text content in the element (keep it short)
- confidence: your confidence score from 0.0 to 1.0

CRITICALLY IMPORTANT: Be extremely precise about the coordinates. Look at the actual pixels in the image to determine the exact position and size. The coordinates must correspond to the EXACT location of elements in the image.

IMPORTANT: LIMIT YOUR DETECTION TO MAX 15 ELEMENTS to avoid response truncation.
Focus on the most important UI elements like buttons, menus, and interactive components.

Your entire response must be valid JSON in this format:
{
  "elements": [
    {
      "box": {"x": 100, "y": 200, "width": 150, "height": 50},
      "type": "button", 
      "text": "Start Game",
      "confidence": 0.95
    },
    ...more elements (MAX 15 TOTAL)...
  ]
}

Respond ONLY with JSON and nothing else."""
        
        logger.info(f"QwenClient initialized with API URL: {api_url}")
        
        # Test connection to the API
        try:
            self._test_connection()
            logger.info("Successfully connected to LM Studio API for Qwen VL")
        except Exception as e:
            logger.error(f"Failed to connect to LM Studio API: {str(e)}")
            logger.error(f"Please ensure LM Studio is running at {api_url}")
    
    def _test_connection(self):
        """Test connection to the API."""
        response = self.session.get(f"{self.api_url}/v1/models")
        response.raise_for_status()
        
        # Check if Qwen VL is available
        models = response.json().get("data", [])
        qwen_models = [m for m in models if "qwen" in m.get("id", "").lower() and "vl" in m.get("id", "").lower()]
        
        if qwen_models:
            self.model_id = qwen_models[0].get("id")
            logger.info(f"Found Qwen VL model: {self.model_id}")
        else:
            logger.warning("No Qwen VL model found. Using default model.")
            self.model_id = "Qwen/Qwen-VL"
            
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
    
    def _extract_json_from_text(self, text: str) -> Dict:
        """
        Extract JSON from text that might contain additional content or be truncated.
        
        Args:
            text: Text that may contain JSON
            
        Returns:
            Parsed JSON dictionary
        """
        # Look for JSON object pattern
        json_pattern = r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\}'
        match = re.search(json_pattern, text)
        
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        # If no valid JSON found, try to extract elements array directly
        elements_pattern = r'"elements"\s*:\s*\[(.*?)\]'
        elements_match = re.search(elements_pattern, text, re.DOTALL)
        
        if elements_match:
            # Try to recover elements array
            elements_text = elements_match.group(1)
            elements_items = []
            
            # Extract individual element objects
            element_pattern = r'\{(.*?)\}'
            for element_match in re.finditer(element_pattern, elements_text, re.DOTALL):
                try:
                    # Add curly braces back and try to parse
                    element_text = '{' + element_match.group(1) + '}'
                    element = json.loads(element_text)
                    elements_items.append(element)
                except json.JSONDecodeError:
                    # Skip invalid elements
                    continue
            
            if elements_items:
                return {"elements": elements_items}
        
        # Last resort: Try to create a minimal valid JSON with any bounding boxes mentioned
        boxes = []
        box_pattern = r'"box"\s*:\s*\{\s*"x"\s*:\s*(\d+)\s*,\s*"y"\s*:\s*(\d+)\s*,\s*"width"\s*:\s*(\d+)\s*,\s*"height"\s*:\s*(\d+)\s*\}'
        for box_match in re.finditer(box_pattern, text):
            try:
                x, y, width, height = map(int, box_match.groups())
                boxes.append({
                    "box": {"x": x, "y": y, "width": width, "height": height},
                    "type": "unknown",
                    "confidence": 0.5
                })
            except (ValueError, IndexError):
                continue
        
        if boxes:
            return {"elements": boxes}
                
        # If all recovery attempts fail, raise error
        logger.error(f"Could not extract valid JSON from response: {text[:200]}...")
        return {"elements": []}
    
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
                f"[{i+1}] {bbox.element_type} (conf: {bbox.confidence:.2f}) at ({bbox.x},{bbox.y},{bbox.width}x{bbox.height}): '{element_text}'"
            )
        
        return "\n".join(formatted)
    
    def detect_ui_elements(self, image_path: str) -> List[BoundingBox]:
        """
        Send an image to Qwen VL and get UI element detections.
        
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
            
            # Prepare the prompt with the image
            prompt = f"Analyze this game screenshot and identify all UI elements with exact coordinates."
            
            # Prepare the API payload for LM Studio (OpenAI-compatible format)
            payload = {
                "model": self.model_id,  # Using the detected Qwen VL model
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", 
                         "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]}
                ],
                "temperature": 0.01,  # Very low temperature for consistent results
                "max_tokens": 1000     # More tokens to avoid truncation
            }
            
            # Send the request to LM Studio API
            logger.info(f"Sending request to {self.api_url}/v1/chat/completions")
            response = self.session.post(
                f"{self.api_url}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60  # Longer timeout for vision models
            )
            response.raise_for_status()
            
            # Parse the response
            response_data = response.json()
            if "choices" in response_data and len(response_data["choices"]) > 0:
                content = response_data["choices"][0]["message"]["content"]
                logger.debug(f"Received response: {content[:200]}...")
                
                # Log token usage if available
                if "usage" in response_data:
                    logger.info(f"Token usage: {response_data['usage']}")
                
                # Extract JSON from the response
                try:
                    result = self._extract_json_from_text(content)
                    num_elements = len(result.get("elements", []))
                    logger.info(f"Successfully parsed {num_elements} UI elements from response")
                except ValueError as e:
                    logger.error(f"Failed to extract JSON from response: {str(e)}")
                    logger.error(f"Raw response: {content}")
                    return []
                
                # Convert to BoundingBox objects
                bounding_boxes = []
                for element in result.get("elements", []):
                    try:
                        if "box" in element:
                            bbox = BoundingBox(
                                x=element["box"]["x"],
                                y=element["box"]["y"],
                                width=element["box"]["width"],
                                height=element["box"]["height"],
                                confidence=element.get("confidence", 0.8),
                                element_type=element.get("type", "unknown"),
                                element_text=element.get("text", "")
                            )
                            bounding_boxes.append(bbox)
                    except KeyError as e:
                        logger.warning(f"Missing key in element data: {e}, skipping this element")
                
                # Log detected elements in a human-readable format
                formatted_boxes = self._format_bounding_boxes(bounding_boxes)
                logger.info(f"Detected {len(bounding_boxes)} UI elements in {image_path}:")
                for line in formatted_boxes.split('\n'):
                    logger.info(f"  {line}")
                
                return bounding_boxes
            else:
                logger.error("No choices in response")
                return []
                
        except requests.RequestException as e:
            logger.error(f"LM Studio API request failed: {str(e)}")
            raise
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse LM Studio API response: {str(e)}")
            raise ValueError(f"Invalid response from LM Studio API: {str(e)}")
    
    def close(self):
        """Close the session."""
        self.session.close()
        logger.info("Qwen client session closed")