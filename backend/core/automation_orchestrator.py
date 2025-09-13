# -*- coding: utf-8 -*-
"""
Automation Orchestrator - Integrates the existing automation engine with the backend
"""

import logging
import threading
import time
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Add the main directory to the path to import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from .run_manager import AutomationRun, RunResult, RunStatus

logger = logging.getLogger(__name__)


class AutomationOrchestrator:
    """Orchestrates automation execution using the existing engine from modules/"""
    
    def __init__(self, game_manager, device_registry, omniparser_client):
        self.game_manager = game_manager
        self.device_registry = device_registry
        self.omniparser_client = omniparser_client
        
        # Import paths for the automation modules
        self.modules_path = os.path.join(os.path.dirname(__file__), '../..', 'modules')
        
        logger.info("AutomationOrchestrator initialized")
    
    def execute_run(self, run: AutomationRun) -> tuple[bool, Optional[RunResult], Optional[str]]:
        """
        Execute a single automation run using the existing automation engine
        
        Returns:
            (success, results, error_message)
        """
        logger.info(f"Starting execution of {run.game_name} on SUT {run.sut_ip}")
        
        try:
            # Get game configuration
            game_config = self.game_manager.get_game(run.game_name)
            if not game_config:
                return False, None, f"Game '{run.game_name}' not found"
            
            # Get SUT device
            device = self.device_registry.get_device_by_ip(run.sut_ip)
            if not device:
                return False, None, f"SUT {run.sut_ip} not found"
            
            if not device.is_online:
                return False, None, f"SUT {run.sut_ip} is not online"
            
            # Execute multiple iterations
            successful_runs = 0
            total_runs = run.iterations
            error_logs = []
            
            for iteration in range(run.iterations):
                logger.info(f"Starting iteration {iteration + 1}/{run.iterations} for run {run.run_id}")
                
                # Check if run was stopped
                if run.status != RunStatus.RUNNING:
                    logger.info(f"Run {run.run_id} was stopped during iteration {iteration + 1}")
                    break
                
                try:
                    # Execute single iteration
                    iteration_success = self._execute_single_iteration(
                        run, game_config, device, iteration + 1
                    )
                    
                    if iteration_success:
                        successful_runs += 1
                        logger.info(f"Iteration {iteration + 1} completed successfully")
                    else:
                        error_msg = f"Iteration {iteration + 1} failed"
                        error_logs.append(error_msg)
                        logger.warning(error_msg)
                        
                except FileNotFoundError as e:
                    error_msg = f"Game file not found (iteration {iteration + 1}): {str(e)}"
                    error_logs.append(error_msg)
                    logger.error(error_msg)
                    # For file not found, fail fast - no point retrying other iterations
                    break
                except RuntimeError as e:
                    error_msg = f"Game launch failed (iteration {iteration + 1}): {str(e)}"
                    error_logs.append(error_msg)
                    logger.error(error_msg)
                    # For launch failures, also fail fast
                    break
                except Exception as e:
                    error_msg = f"Unexpected error in iteration {iteration + 1}: {str(e)}"
                    error_logs.append(error_msg)
                    logger.error(error_msg, exc_info=True)
            
            # Calculate results
            success_rate = successful_runs / total_runs if total_runs > 0 else 0.0
            
            results = RunResult(
                success_rate=success_rate,
                successful_runs=successful_runs,
                total_iterations=total_runs,
                run_directory=self._get_run_directory(run),
                error_logs=error_logs
            )
            
            overall_success = successful_runs > 0  # At least one iteration succeeded
            
            return overall_success, results, None
            
        except Exception as e:
            error_msg = f"Critical error in run execution: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg
    
    def _execute_single_iteration(self, run: AutomationRun, game_config, device, iteration_num: int) -> bool:
        """Execute a single automation iteration"""
        try:
            # Import automation modules dynamically
            from modules.network import NetworkManager
            from modules.screenshot import ScreenshotManager  
            from modules.omniparser_client import OmniparserClient
            from modules.annotator import Annotator
            from modules.simple_automation import SimpleAutomation
            from modules.game_launcher import GameLauncher
            
            # Create run directory
            run_dir = self._create_run_directory(run, iteration_num)
            
            # Initialize components
            logger.info(f"Connecting to SUT at {device.ip}:{device.port}")
            network = NetworkManager(device.ip, device.port)
            screenshot_mgr = ScreenshotManager(network)
            
            # Get actual screen resolution from SUT
            try:
                screen_width, screen_height = network.get_screen_resolution()
                logger.info(f"Using SUT screen resolution: {screen_width}x{screen_height}")
            except Exception as e:
                logger.warning(f"Failed to get SUT resolution, using default 1920x1080: {e}")
                screen_width, screen_height = 1920, 1080
            
            # Use OmniParser for vision with correct resolution
            vision_model = OmniparserClient(
                self.omniparser_client.api_url, 
                screen_width=screen_width, 
                screen_height=screen_height
            )
            annotator = Annotator()
            game_launcher = GameLauncher(network)
            
            # Create a stop event for this iteration
            stop_event = threading.Event()
            
            # Initialize SimpleAutomation
            automation = SimpleAutomation(
                config_path=game_config.yaml_path,
                network=network,
                screenshot_mgr=screenshot_mgr,
                vision_model=vision_model,
                stop_event=stop_event,
                run_dir=run_dir,
                annotator=annotator
            )
            
            # Launch game if path is specified
            if game_config.path:
                logger.info(f"Launching game: {game_config.path}")
                
                # Note: Skip path validation here since we're on the backend (Linux) 
                # but the game will be launched on the SUT (Windows)
                logger.info(f"Game path configured: {game_config.path} (will be validated on SUT)")
                
                try:
                    game_launcher.launch(game_config.path)
                    logger.info(f"Game launched successfully: {game_config.path}")
                except Exception as e:
                    error_msg = f"Failed to launch game '{game_config.name}': {str(e)}"
                    logger.error(error_msg)
                    
                    # Check if it's a 404 error (SUT service issue)
                    if "404" in str(e) or "NOT FOUND" in str(e):
                        error_msg = f"SUT service error: /launch endpoint not found on {device.ip}:{device.port}. Please ensure gemma_sut_service.py is running on the SUT."
                    elif "Connection" in str(e) or "timeout" in str(e).lower():
                        error_msg = f"Connection error: Cannot reach SUT at {device.ip}:{device.port}. Please check if the SUT service is running."
                    
                    raise RuntimeError(error_msg)
                
                # Wait for game startup
                startup_wait = 30  # Default startup wait
                if hasattr(game_config, 'startup_wait'):
                    startup_wait = game_config.startup_wait
                
                logger.info(f"Waiting {startup_wait}s for game initialization...")
                time.sleep(startup_wait)
            
            # Check if run was stopped during initialization
            if run.status != RunStatus.RUNNING:
                return False
            
            # Execute the automation
            logger.info(f"Starting automation execution for iteration {iteration_num}")
            success = automation.run()
            
            logger.info(f"Iteration {iteration_num} completed with result: {success}")
            return success
            
        except Exception as e:
            logger.error(f"Error in iteration {iteration_num}: {str(e)}", exc_info=True)
            return False
        finally:
            # Comprehensive cleanup to prevent hanging resources
            try:
                logger.debug(f"Cleaning up resources for iteration {iteration_num}")
                
                # Close network connection
                if 'network' in locals():
                    network.close()
                    
                # Close vision model/omniparser client
                if 'vision_model' in locals():
                    try:
                        vision_model.close()
                    except:
                        pass
                        
                # Clean up automation object
                if 'automation' in locals():
                    try:
                        # Set stop event to interrupt any running operations
                        if hasattr(automation, 'stop_event'):
                            automation.stop_event.set()
                    except:
                        pass
                        
                # Force garbage collection
                import gc
                gc.collect()
                
                logger.debug(f"Cleanup completed for iteration {iteration_num}")
                
            except Exception as cleanup_error:
                logger.warning(f"Error during cleanup: {cleanup_error}")
                pass
    
    def _create_run_directory(self, run: AutomationRun, iteration_num: int) -> str:
        """Create directory structure for run outputs"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create base logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Create game-specific directory
        game_dir = logs_dir / run.game_name.replace(" ", "_")
        game_dir.mkdir(exist_ok=True)
        
        # Create run-specific directory
        run_dir = game_dir / f"run_{run.run_id}_{timestamp}_iter{iteration_num}"
        run_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (run_dir / "screenshots").mkdir(exist_ok=True)
        (run_dir / "annotated").mkdir(exist_ok=True)
        
        return str(run_dir)
    
    def _get_run_directory(self, run: AutomationRun) -> str:
        """Get the base run directory path"""
        return f"logs/{run.game_name.replace(' ', '_')}/run_{run.run_id}"
    
    def validate_prerequisites(self, run: AutomationRun) -> tuple[bool, Optional[str]]:
        """Validate that all prerequisites are met for running automation"""
        try:
            # Check game exists
            game_config = self.game_manager.get_game(run.game_name)
            if not game_config:
                return False, f"Game '{run.game_name}' not found"
            
            # Check game YAML file exists
            if not os.path.exists(game_config.yaml_path):
                return False, f"Game configuration file not found: {game_config.yaml_path}"
            
            # Check SUT is available
            device = self.device_registry.get_device_by_ip(run.sut_ip)
            if not device:
                return False, f"SUT {run.sut_ip} not found in device registry"
            
            if not device.is_online:
                return False, f"SUT {run.sut_ip} is not online"
            
            # Check OmniParser is available
            omniparser_status = self.omniparser_client.get_server_status()
            if omniparser_status.get('status') != 'online':
                logger.warning("OmniParser is not online - automation may fail")
            
            # Check modules directory exists
            if not os.path.exists(self.modules_path):
                return False, f"Automation modules not found at {self.modules_path}"
            
            return True, None
            
        except Exception as e:
            return False, f"Error validating prerequisites: {str(e)}"
    
    def get_estimated_duration(self, game_name: str, iterations: int) -> int:
        """Estimate total duration for a run in seconds"""
        try:
            game_config = self.game_manager.get_game(game_name)
            if not game_config:
                return 300  # Default 5 minutes per iteration
            
            # Use benchmark duration from config + overhead
            base_duration = getattr(game_config, 'benchmark_duration', 120)
            startup_overhead = 60  # Startup, shutdown, etc.
            
            return (base_duration + startup_overhead) * iterations
            
        except Exception:
            return 300 * iterations  # Fallback estimate