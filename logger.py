import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Configure the logging settings
def setup_logger(name, log_file, level=logging.INFO):
    """Function to set up a logger with file and console handlers"""
    # Create a custom logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create handlers
    # File handler for persistent logging
    # file_handler = RotatingFileHandler(
    #     os.path.join(logs_dir, log_file), 
    #     maxBytes=10485760,  # 10MB
    #     backupCount=5,      # Keep 5 backup logs
    #     encoding='utf-8'
    # )
    # file_handler.setLevel(level)
    
    # Console handler for immediate feedback
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # Create formatters and add to handlers
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    console_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # file_handler.setFormatter(file_format)
    console_handler.setFormatter(console_format)
    
    # Add handlers to the logger
    # logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create loggers for different components
api_logger = setup_logger('api', 'api.log')
scraper_logger = setup_logger('scraper', 'scraper.log')
ui_logger = setup_logger('ui', 'ui.log')

# General application logger
app_logger = setup_logger('app', 'app.log')
