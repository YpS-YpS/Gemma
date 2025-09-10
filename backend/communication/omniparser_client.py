# -*- coding: utf-8 -*-
"""
Omniparser client for the backend system
"""

import os
import base64
import logging
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OmniparserResult:
    """Result from Omniparser processing"""
    success: bool
    elements: Optional[List[Dict[str, Any]]] = None
    annotated_image_data: Optional[bytes] = None
    response_time: Optional[float] = None
    error: Optional[str] = None


class OmniparserClient:
    """Client for communicating with Omniparser server"""
    
    def __init__(self, api_url: str = "http://localhost:8000", timeout: float = 60.0):
        self.api_url = api_url
        self.timeout = timeout
        self.session = requests.Session()
        
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Gemma-Backend-Client/2.0'
        })
        
        logger.debug(f"OmniparserClient initialized with URL: {api_url}")
        
    def test_connection(self) -> bool:
        """Test connection to Omniparser server"""
        try:
            response = self.session.get(
                f"{self.api_url}/probe",
                timeout=5.0
            )
            return response.status_code == 200
        except:
            return False
            
    def analyze_screenshot(self, image_path: str) -> OmniparserResult:
        """Analyze a screenshot with Omniparser"""
        try:
            if not os.path.exists(image_path):
                return OmniparserResult(
                    success=False,
                    error=f"Image file not found: {image_path}"
                )
                
            # Encode image to base64
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
                
            # Prepare payload
            payload = {
                "base64_image": image_data
            }
            
            # Send request
            response = self.session.post(
                f"{self.api_url}/parse/",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Extract elements
                elements = self._parse_elements(response_data)
                
                # Extract annotated image if available
                annotated_image_data = None
                if "som_image_base64" in response_data:
                    try:
                        annotated_image_data = base64.b64decode(response_data["som_image_base64"])
                    except Exception as e:
                        logger.warning(f"Failed to decode annotated image: {e}")
                        
                return OmniparserResult(
                    success=True,
                    elements=elements,
                    annotated_image_data=annotated_image_data,
                    response_time=response.elapsed.total_seconds()
                )
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                return OmniparserResult(
                    success=False,
                    error=error_msg
                )
                
        except requests.RequestException as e:
            return OmniparserResult(
                success=False,
                error=str(e)
            )
        except Exception as e:
            return OmniparserResult(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
            
    def _parse_elements(self, response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse UI elements from Omniparser response"""
        elements = []
        parsed_content_list = response_data.get("parsed_content_list", [])
        
        for item in parsed_content_list:
            if 'bbox' in item:
                element = {
                    'bbox': item['bbox'],
                    'type': item.get('type', 'unknown'),
                    'content': item.get('content', ''),
                    'interactive': item.get('interactivity', False),
                    'confidence': item.get('confidence', 1.0)
                }
                elements.append(element)
                
        logger.debug(f"Parsed {len(elements)} UI elements")
        return elements
        
    def save_annotated_image(self, result: OmniparserResult, output_path: str) -> bool:
        """Save annotated image from result"""
        if not result.success or not result.annotated_image_data:
            return False
            
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(result.annotated_image_data)
            return True
        except Exception as e:
            logger.error(f"Failed to save annotated image: {e}")
            return False
            
    def get_server_status(self) -> Dict[str, Any]:
        """Get Omniparser server status"""
        try:
            response = self.session.get(
                f"{self.api_url}/probe",
                timeout=5.0
            )
            
            if response.status_code == 200:
                return {
                    "status": "online",
                    "url": self.api_url,
                    "response_time": response.elapsed.total_seconds()
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "status": "offline",
                "error": str(e)
            }
            
    def close(self):
        """Close the session"""
        self.session.close()