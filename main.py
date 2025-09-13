#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main orchestration script for Game UI Navigation Automation Tool.
Enhanced to support multiple games with benchmarks.
"""

import os
import time
import logging
import argparse
import glob
import datetime
from pathlib import Path

from modules.network import NetworkManager
from modules.screenshot import ScreenshotManager
from modules.gemma_client import GemmaClient
from modules.qwen_client import QwenClient
from modules.omniparser_client import OmniparserClient
from modules.annotator import Annotator
from modules.decision_engine import DecisionEngine
from modules.game_launcher import GameLauncher
from modules.config_parser import ConfigParser

def create_directory_structure(game_name):
    """
    Create the necessary directory structure for a specific game run.
    
    Args:
        game_name: Name of the game for organizing logs
        
    Returns:
        Dictionary with paths for different directories
    """
    # Create timestamp for this run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create base directories
    os.makedirs("logs", exist_ok=True)
    game_dir = f"logs/{game_name}"
    os.makedirs(game_dir, exist_ok=True)
    
    # Create run-specific directory
    run_dir = f"{game_dir}/run_{timestamp}"
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(f"{run_dir}/screenshots", exist_ok=True)
    os.makedirs(f"{run_dir}/annotated", exist_ok=True)
    
    return {
        "game_dir": game_dir,
        "run_dir": run_dir,
        "screenshots_dir": f"{run_dir}/screenshots",
        "annotated_dir": f"{run_dir}/annotated"
    }

def parse_arguments():
    """
    Parse command-line arguments with game selection support.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Game UI Navigation Automation Tool')
    
    # Required arguments
    parser.add_argument('--sut-ip', type=str, required=True, help='IP address of the SUT')
    parser.add_argument('--game-path', type=str, required=True, help='Path to the game executable on the SUT')
    
    # Game selection
    parser.add_argument('--game', type=str, help='Game name (will use matching YAML from config/games/)')
    parser.add_argument('--config', type=str, help='Path to a specific YAML configuration file')
    
    # Optional arguments with sensible defaults
    parser.add_argument('--sut-port', type=int, default=8080, help='Port for communication with SUT')
    parser.add_argument('--vision-model', type=str, choices=['gemma', 'qwen', 'omniparser'], default='gemma',
                      help='Vision model to use for UI detection (default: gemma)')
    parser.add_argument('--model-url', type=str, default='http://127.0.0.1:1234', 
                      help='URL for the vision model API (default: http://127.0.0.1:1234)')
    parser.add_argument('--max-iterations', type=int, default=50,
                      help='Maximum number of iterations before terminating')
    
    return parser.parse_args()

def setup_game_specific_logging(run_dir):
    """
    Configure logging for a specific game run.
    
    Args:
        run_dir: Path to the run-specific directory
        
    Returns:
        Path to the log file
    """
    # Create file handler for run-specific logs
    log_file = f"{run_dir}/automation.log"
    
    file_handler = logging.FileHandler(log_file)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Add handler to root logger
    logger = logging.getLogger()
    logger.addHandler(file_handler)
    
    return log_file

def find_game_config(game_name):
    """
    Find the YAML configuration file for a specific game.
    
    Args:
        game_name: Name of the game to find configuration for
        
    Returns:
        Path to the game configuration file or None if not found
    """
    # First try: Search in config/games/ directory
    game_configs = glob.glob(f"config/games/{game_name}*.yaml")
    if game_configs:
        return game_configs[0]
        
    # Second try: Check in the config directory directly
    alt_configs = glob.glob(f"config/{game_name}*.yaml")
    if alt_configs:
        return alt_configs[0]
        
    # No game-specific config found
    return None

def list_available_games():
    """
    List all available game configurations.
    
    Returns:
        List of available game names
    """
    games = []
    
    # Check in config/games/ directory
    os.makedirs("config/games", exist_ok=True)
    for config in glob.glob("config/games/*.yaml"):
        game_name = os.path.basename(config).replace('.yaml', '')
        games.append(game_name)
    
    # Check in config directory directly
    for config in glob.glob("config/*.yaml"):
        if "template" not in config.lower():  # Skip template files
            game_name = os.path.basename(config).replace('.yaml', '')
            if game_name not in games:
                games.append(game_name)
    
    return games

def main():
    """Main execution function with game-specific support."""
    # Setup
    args = parse_arguments()
    
    # Determine which config file to use
    config_path = args.config
    if not config_path and args.game:
        config_path = find_game_config(args.game)
        if not config_path:
            print(f"No configuration found for game: {args.game}")
            print("Available game configurations:")
            for game in list_available_games():
                print(f"  - {game}")
            return
    elif not config_path:
        # Default to CS2
        config_path = "config/games/cs2_benchmark.yaml"
        if not os.path.exists(config_path):
            config_path = "config/cs2_benchmark.yaml"
        
        if not os.path.exists(config_path):
            print("No default configuration found. Available game configurations:")
            for game in list_available_games():
                print(f"  - {game}")
            return
    
    # Load game configuration
    config_parser = ConfigParser(config_path)
    game_name = config_parser.game_name
    
    # Create directory structure
    dirs = create_directory_structure(game_name)
    run_dir = dirs["run_dir"]
    
    # Setup logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler()])
    log_file = setup_game_specific_logging(run_dir)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting Game UI Navigation for: {game_name}")
    logger.info(f"Using configuration: {config_path}")
    logger.info(f"Run directory: {run_dir}")
    logger.info(f"Log file: {log_file}")
    logger.info(f"SUT: {args.sut_ip}:{args.sut_port}")
    logger.info(f"Game path: {args.game_path}")
    logger.info(f"Vision model: {args.vision_model} at {args.model_url}")
    
    # Initialize components
    try:
        network = NetworkManager(args.sut_ip, args.sut_port)
        screenshot_mgr = ScreenshotManager(network)
        
        # Initialize the vision model based on user selection
        if args.vision_model == 'gemma':
            logger.info("Using Gemma for UI detection")
            vision_model = GemmaClient(args.model_url)
        elif args.vision_model == 'qwen':
            logger.info("Using Qwen VL for UI detection")
            vision_model = QwenClient(args.model_url)
        elif args.vision_model == 'omniparser':
            logger.info("Using Omniparser for UI detection")
            vision_model = OmniparserClient(args.model_url)
        
        annotator = Annotator()
        decision_engine = DecisionEngine(config_parser.get_config())
        game_launcher = GameLauncher(network)
        
        # Extract benchmark metadata
        game_metadata = config_parser.get_config().get("metadata", {})
        benchmark_duration = game_metadata.get("benchmark_duration", 120)
        logger.info(f"Expected benchmark duration: {benchmark_duration} seconds")
        
        # Main execution loop
        iteration = 0
        current_state = "initial"
        target_state = decision_engine.get_target_state()
        
        # Track time spent in each state to detect timeouts
        state_start_time = time.time()
        max_time_in_state = 60  # Default maximum seconds to remain in the same state
        
        try:
            # Launch the game
            logger.info(f"Launching game from: {args.game_path}")
            game_launcher.launch(args.game_path)
            
            # Get startup wait time from config or use default
            startup_wait = game_metadata.get("startup_wait", 30)
            logger.info(f"Waiting {startup_wait} seconds for game to fully initialize...")
            time.sleep(startup_wait)
            
            while current_state != target_state and iteration < args.max_iterations:
                iteration += 1
                logger.info(f"Iteration {iteration}: Current state: {current_state}")
                
                # Get state-specific timeout from config or use default
                state_def = config_parser.get_state_definition(current_state)
                state_timeout = state_def.get("timeout", max_time_in_state) if state_def else max_time_in_state
                
                # Check for timeout in current state
                time_in_state = time.time() - state_start_time
                if time_in_state > state_timeout:
                    logger.warning(f"Timeout in state {current_state} after {time_in_state:.1f} seconds (limit: {state_timeout}s)")
                    
                    # Get state-specific or general fallback action
                    fallback_action = decision_engine.get_fallback_action(current_state)
                    logger.info(f"Using fallback action for timeout: {fallback_action}")
                    
                    # Execute fallback action
                    network.send_action(fallback_action)
                    logger.info("Executed timeout recovery action")
                    time.sleep(2)
                    
                    # Reset timeout timer
                    state_start_time = time.time()
                    continue
                    
                # Capture screenshot - USE RUN DIRECTORY
                screenshot_path = f"{dirs['screenshots_dir']}/screenshot_{iteration}.png"
                screenshot_mgr.capture(screenshot_path)
                logger.info(f"Screenshot captured: {screenshot_path}")
                
                # Process with vision model
                bounding_boxes = vision_model.detect_ui_elements(screenshot_path)
                logger.info(f"Detected {len(bounding_boxes)} UI elements")
                
                # Annotate screenshot - USE RUN DIRECTORY
                annotated_path = f"{dirs['annotated_dir']}/annotated_{iteration}.png"
                annotator.draw_bounding_boxes(screenshot_path, bounding_boxes, annotated_path)
                logger.info(f"Annotated screenshot saved: {annotated_path}")
                
                # Determine next action
                previous_state = current_state
                next_action, new_state = decision_engine.determine_next_action(
                    current_state, bounding_boxes
                )
                
                # Format the action for better logging
                action_str = ""
                if next_action:
                    if next_action.get("type") == "click":
                        action_str = f"Click at ({next_action.get('x')}, {next_action.get('y')})"
                    elif next_action.get("type") == "key":
                        action_str = f"Press key {next_action.get('key')}"
                    elif next_action.get("type") == "wait":
                        action_str = f"Wait for {next_action.get('duration')} seconds"
                    else:
                        action_str = str(next_action)
                
                logger.info(f"Next action: {action_str}, transitioning to state: {new_state}")
                
                # Execute action
                if next_action:
                    logger.info(f"Executing action: {action_str}")
                    
                    # Handle "wait" actions locally instead of sending to SUT
                    if next_action.get("type") == "wait":
                        duration = next_action.get("duration", 1)
                        logger.info(f"Waiting for {duration} seconds...")
                        
                        # Simple wait for main.py (no interruption check needed)
                        for i in range(duration):
                            time.sleep(1)
                            if i % 10 == 0 and i > 0:  # Log every 10 seconds for long waits
                                logger.info(f"Still waiting... {i}/{duration} seconds elapsed")
                                
                        logger.info(f"Wait completed")
                    else:
                        # Send other action types to SUT
                        network.send_action(next_action)
                        
                    logger.info(f"Action completed: {action_str}")
                
                # Update state
                current_state = new_state
                if previous_state != current_state:
                    # Reset timeout timer when state changes
                    state_start_time = time.time()
                    logger.info(f"State changed from {previous_state} to {current_state}")
                
                # Get delay from transition if specified
                transition_key = f"{previous_state}->{current_state}"
                transition = config_parser.get_config().get("transitions", {}).get(transition_key, {})
                delay = transition.get("expected_delay", 1)
                
                time.sleep(delay)  # Wait before next iteration
            
            # Check if we reached the target state
            if current_state == target_state:
                logger.info(f"Successfully reached target state: {target_state}")
                
                # Report benchmark results if available
                if hasattr(decision_engine, "state_context") and "benchmark_duration" in decision_engine.state_context:
                    benchmark_duration = decision_engine.state_context["benchmark_duration"]
                    logger.info(f"Benchmark completed in {benchmark_duration:.2f} seconds")
            else:
                logger.warning(f"Failed to reach target state. Stopped at: {current_state}")
            
        except Exception as e:
            logger.error(f"Error in main execution: {str(e)}", exc_info=True)
        finally:
            # Cleanup
            logger.info("Cleaning up resources")
            network.close()
            if hasattr(vision_model, 'close'):
                vision_model.close()
            logger.info("Execution completed")
            
    except Exception as e:
        logger.error(f"Error initializing components: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()