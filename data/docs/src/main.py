"""Main Module - Application entry point and initialization.

Provides application startup and configuration:
- Environment setup
- Logging configuration
- Service initialization
- Health monitoring

Author: Platform Team
Version: 2.0.0
"""

import logging
import logging.config
import os
import sys
from pathlib import Path
import yaml
from typing import Dict, Any

from api import app

# Application metadata
APP_NAME = "ai-assistant-demo"
APP_VERSION = "2.0.0"


def load_config(config_path: str = None) -> Dict[str, Any]:
    """Load application configuration.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        if config_path is None:
            config_path = os.getenv('CONFIG_PATH', 'config/settings.yaml')
        
        config_file = Path(config_path)
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            print(f"Loaded configuration from {config_path}")
            return config
        else:
            print(f"Configuration file not found: {config_path}, using defaults")
            return get_default_config()
            
    except Exception as e:
        print(f"Error loading configuration: {str(e)}, using defaults")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """Get default configuration.
    
    Returns:
        Default configuration dictionary
    """
    return {
        'app': {
            'name': APP_NAME,
            'version': APP_VERSION,
            'environment': os.getenv('ENVIRONMENT', 'development')
        },
        'server': {
            'host': os.getenv('HOST', '0.0.0.0'),
            'port': int(os.getenv('PORT', 8000)),
            'debug': os.getenv('DEBUG', 'true').lower() == 'true'
        },
        'logging': {
            'level': os.getenv('LOG_LEVEL', 'INFO'),
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'storage': {
            'backend': os.getenv('STORAGE_BACKEND', 'memory'),
            'path': os.getenv('STORAGE_PATH', './data/storage')
        }
    }


def setup_logging(config: Dict[str, Any]) -> None:
    """Setup logging configuration.
    
    Args:
        config: Application configuration
    """
    try:
        logging_config_path = os.getenv('LOGGING_CONFIG', 'config/logging.yaml')
        logging_config_file = Path(logging_config_path)
        
        if logging_config_file.exists():
            with open(logging_config_file, 'r') as f:
                logging_config = yaml.safe_load(f)
            logging.config.dictConfig(logging_config)
            print(f"Loaded logging configuration from {logging_config_path}")
        else:
            # Use basic configuration
            logging_level = config.get('logging', {}).get('level', 'INFO')
            logging_format = config.get('logging', {}).get('format')
            
            logging.basicConfig(
                level=getattr(logging, logging_level),
                format=logging_format,
                handlers=[
                    logging.StreamHandler(sys.stdout),
                    logging.FileHandler('app.log')
                ]
            )
            print("Using basic logging configuration")
            
    except Exception as e:
        print(f"Error setting up logging: {str(e)}")
        logging.basicConfig(level=logging.INFO)


def initialize_app(config: Dict[str, Any]) -> None:
    """Initialize application components.
    
    Args:
        config: Application configuration
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Log startup information
        logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
        logger.info(f"Environment: {config.get('app', {}).get('environment')}")
        logger.info(f"Storage backend: {config.get('storage', {}).get('backend')}")
        
        # Initialize storage directories
        storage_path = config.get('storage', {}).get('path', './data/storage')
        Path(storage_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"Storage path: {storage_path}")
        
        # Configure Flask app
        app.config.update(config.get('flask', {}))
        
        logger.info("Application initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing application: {str(e)}", exc_info=True)
        raise


def main():
    """Main application entry point."""
    try:
        # Load configuration
        config = load_config()
        
        # Setup logging
        setup_logging(config)
        
        # Initialize application
        initialize_app(config)
        
        # Get logger after logging is configured
        logger = logging.getLogger(__name__)
        
        # Get server configuration
        server_config = config.get('server', {})
        host = server_config.get('host', '0.0.0.0')
        port = server_config.get('port', 8000)
        debug = server_config.get('debug', True)
        
        # Start server
        logger.info(f"Starting server on {host}:{port}")
        app.run(host=host, port=port, debug=debug)
        
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
