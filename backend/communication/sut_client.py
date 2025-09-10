# -*- coding: utf-8 -*-
"""
SUT client for communication with SUT devices
"""

import logging
import requests
from typing import Dict, Any, Optional, List
import json
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Result of an action performed on a SUT"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    response_time: Optional[float] = None


class SUTClient:
    """Client for communicating with SUT devices"""
    
    def __init__(self, timeout: float = 10.0):
        self.session = requests.Session()
        self.timeout = timeout
        
        # Set reasonable defaults
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Gemma-Backend-Client/2.0'
        })
        
        logger.debug("SUT client initialized")
        
    def get_status(self, ip: str, port: int = 8080) -> ActionResult:
        """Get status from SUT device"""
        try:
            response = self.session.get(
                f"http://{ip}:{port}/status",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return ActionResult(
                    success=True,
                    data=data,
                    response_time=response.elapsed.total_seconds()
                )
            else:
                return ActionResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
                
        except requests.RequestException as e:
            return ActionResult(
                success=False,
                error=str(e)
            )
            
    def take_screenshot(self, ip: str, port: int = 8080, save_path: Optional[str] = None) -> ActionResult:
        """Take a screenshot from SUT device"""
        try:
            response = self.session.get(
                f"http://{ip}:{port}/screenshot",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                screenshot_data = response.content
                
                result_data = {
                    'content_type': response.headers.get('content-type', 'image/png'),
                    'size': len(screenshot_data)
                }
                
                if save_path:
                    try:
                        with open(save_path, 'wb') as f:
                            f.write(screenshot_data)
                        result_data['saved_to'] = save_path
                    except IOError as e:
                        logger.warning(f"Failed to save screenshot to {save_path}: {e}")
                        
                return ActionResult(
                    success=True,
                    data=result_data,
                    response_time=response.elapsed.total_seconds()
                )
            else:
                return ActionResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
                
        except requests.RequestException as e:
            return ActionResult(
                success=False,
                error=str(e)
            )
            
    def launch_application(self, ip: str, port: int, app_path: str, process_id: Optional[str] = None) -> ActionResult:
        """Launch an application on SUT device"""
        try:
            payload = {
                'path': app_path
            }
            if process_id:
                payload['process_id'] = process_id
                
            response = self.session.post(
                f"http://{ip}:{port}/launch",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return ActionResult(
                    success=True,
                    data=data,
                    response_time=response.elapsed.total_seconds()
                )
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg += f": {error_data['error']}"
                except:
                    error_msg += f": {response.text}"
                    
                return ActionResult(
                    success=False,
                    error=error_msg
                )
                
        except requests.RequestException as e:
            return ActionResult(
                success=False,
                error=str(e)
            )
            
    def perform_action(self, ip: str, port: int, action: Dict[str, Any]) -> ActionResult:
        """Perform an action on SUT device"""
        try:
            response = self.session.post(
                f"http://{ip}:{port}/action",
                json=action,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except:
                    # Some actions might return empty response
                    data = {}
                    
                return ActionResult(
                    success=True,
                    data=data,
                    response_time=response.elapsed.total_seconds()
                )
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg += f": {error_data['error']}"
                except:
                    error_msg += f": {response.text}"
                    
                return ActionResult(
                    success=False,
                    error=error_msg
                )
                
        except requests.RequestException as e:
            return ActionResult(
                success=False,
                error=str(e)
            )
            
    def perform_click(self, ip: str, port: int, x: int, y: int, button: str = 'left', **kwargs) -> ActionResult:
        """Perform a click action"""
        action = {
            'type': 'click',
            'x': x,
            'y': y,
            'button': button,
            **kwargs
        }
        return self.perform_action(ip, port, action)
        
    def perform_key_press(self, ip: str, port: int, key: str) -> ActionResult:
        """Perform a key press action"""
        action = {
            'type': 'key',
            'key': key
        }
        return self.perform_action(ip, port, action)
        
    def perform_hotkey(self, ip: str, port: int, keys: List[str]) -> ActionResult:
        """Perform a hotkey combination"""
        action = {
            'type': 'hotkey',
            'keys': keys
        }
        return self.perform_action(ip, port, action)
        
    def type_text(self, ip: str, port: int, text: str, clear_first: bool = False) -> ActionResult:
        """Type text"""
        action = {
            'type': 'text',
            'text': text,
            'clear_first': clear_first
        }
        return self.perform_action(ip, port, action)
        
    def perform_drag(self, ip: str, port: int, start_x: int, start_y: int, end_x: int, end_y: int, **kwargs) -> ActionResult:
        """Perform a drag operation"""
        action = {
            'type': 'drag',
            'start_x': start_x,
            'start_y': start_y,
            'end_x': end_x,
            'end_y': end_y,
            **kwargs
        }
        return self.perform_action(ip, port, action)
        
    def perform_scroll(self, ip: str, port: int, x: int, y: int, direction: str, clicks: int = 3) -> ActionResult:
        """Perform a scroll action"""
        action = {
            'type': 'scroll',
            'x': x,
            'y': y,
            'direction': direction,
            'clicks': clicks
        }
        return self.perform_action(ip, port, action)
        
    def wait(self, ip: str, port: int, duration: float) -> ActionResult:
        """Wait for specified duration"""
        action = {
            'type': 'wait',
            'duration': duration
        }
        return self.perform_action(ip, port, action)
        
    def perform_sequence(self, ip: str, port: int, actions: List[Dict[str, Any]], delay_between: float = 0.5) -> ActionResult:
        """Perform a sequence of actions"""
        action = {
            'type': 'sequence',
            'actions': actions,
            'delay_between': delay_between
        }
        return self.perform_action(ip, port, action)
        
    def terminate_application(self, ip: str, port: int) -> ActionResult:
        """Terminate running application on SUT"""
        action = {
            'type': 'terminate_game'
        }
        return self.perform_action(ip, port, action)
        
    def get_performance_metrics(self, ip: str, port: int) -> ActionResult:
        """Get performance metrics from SUT"""
        try:
            response = self.session.get(
                f"http://{ip}:{port}/performance",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return ActionResult(
                    success=True,
                    data=data,
                    response_time=response.elapsed.total_seconds()
                )
            else:
                return ActionResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
                
        except requests.RequestException as e:
            return ActionResult(
                success=False,
                error=str(e)
            )
            
    def health_check(self, ip: str, port: int) -> ActionResult:
        """Perform health check on SUT"""
        try:
            response = self.session.get(
                f"http://{ip}:{port}/health",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return ActionResult(
                    success=True,
                    data=data,
                    response_time=response.elapsed.total_seconds()
                )
            else:
                return ActionResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
                
        except requests.RequestException as e:
            return ActionResult(
                success=False,
                error=str(e)
            )
            
    def set_timeout(self, timeout: float):
        """Set request timeout"""
        self.timeout = timeout
        
    def close(self):
        """Close the session"""
        self.session.close()