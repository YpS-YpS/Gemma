"""
Main entry point for the modular backend system
"""

import argparse
import logging
import sys
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


def main():
    """Main entry point"""
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
    controller = BackendController(config)
    
    try:
        controller.run_server(
            host=config.host,
            port=config.port,
            debug=config.debug
        )
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        logger.info("Shutdown complete")


if __name__ == '__main__':
    main()