# -*- coding: utf-8 -*-
"""
Main entry point for the modular backend system
"""

import argparse
import logging
import sys
import signal
from .core.config import ConfigManager
from .core.controller import BackendController


def setup_logging(config):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific log levels for noisy libraries
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('socketio').setLevel(logging.WARNING)
    logging.getLogger('engineio').setLevel(logging.WARNING)


# Global controller reference for signal handling
_controller_instance = None

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, initiating shutdown...")
    
    # Stop the controller if it exists
    global _controller_instance
    if _controller_instance:
        try:
            logger.info("Stopping controller from signal handler...")
            _controller_instance.stop()
        except Exception as e:
            logger.error(f"Error stopping controller in signal handler: {e}")
    
    # Force exit after a short delay
    import threading
    import time
    
    def force_exit():
        time.sleep(3)  # Give 3 seconds for cleanup
        logger.warning("Force exiting due to signal - some threads may not have cleaned up properly")
        
        # Log remaining threads for debugging
        remaining_threads = threading.enumerate()
        if len(remaining_threads) > 1:
            logger.warning(f"Remaining threads during force exit:")
            for thread in remaining_threads:
                if thread != threading.current_thread():
                    logger.warning(f"  - {thread.name} (daemon: {thread.daemon})")
        
        import os
        logger.warning("Calling os._exit(1) to force termination")
        os._exit(1)
    
    # Start force exit thread
    threading.Thread(target=force_exit, daemon=True).start()
    
    # More forceful exit - don't rely on sys.exit(0) 
    import os
    logger.info("Calling os._exit(0) from signal handler")
    os._exit(0)

def main():
    """Main entry point"""
    # Set up signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    parser = argparse.ArgumentParser(description='Gemma Backend Server v2.0')
    parser.add_argument('--host', help='Host to bind to (default: from config)')
    parser.add_argument('--port', type=int, help='Port to bind to (default: from config)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--config-file', help='Path to configuration file')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       help='Set logging level')
    args = parser.parse_args()
    
    # Load configuration
    config = ConfigManager.load_config()
    
    # Override with command line arguments
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.debug:
        config.debug = args.debug
    if args.log_level:
        config.log_level = args.log_level
        
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("Gemma Backend Server v2.0 - Modular Communication Platform")
    logger.info("=" * 60)
    logger.info(f"Configuration:")
    logger.info(f"  Host: {config.host}:{config.port}")
    logger.info(f"  Debug: {config.debug}")
    logger.info(f"  Discovery interval: {config.discovery_interval}s")
    logger.info(f"  Discovery timeout: {config.discovery_timeout}s")
    logger.info(f"  SUT port: {config.sut_port}")
    logger.info(f"  Omniparser URL: {config.omniparser_url}")
    logger.info(f"  Network ranges: {config.network_ranges}")
    logger.info("=" * 60)
    
    # Create and run the backend controller
    controller = None
    try:
        controller = BackendController(config)
        global _controller_instance
        _controller_instance = controller
        controller.run_server(
            host=config.host,
            port=config.port,
            debug=config.debug
        )
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        if controller:
            try:
                logger.info("Starting shutdown sequence...")
                controller.stop()
                logger.info("Controller stopped successfully")
            except Exception as e:
                logger.error(f"Error during final cleanup: {e}")
        
        logger.info("Shutdown complete")
        
        # Force exit if still hanging
        import threading
        if len(threading.enumerate()) > 1:
            logger.warning(f"Still have {len(threading.enumerate())} threads running, forcing exit")
            for thread in threading.enumerate():
                if thread != threading.current_thread():
                    logger.warning(f"Thread still alive: {thread.name}")
        
        # Give a moment for cleanup, then force exit
        import time
        time.sleep(0.5)
        logger.info("Exiting application")
        sys.exit(0)


if __name__ == '__main__':
    main()