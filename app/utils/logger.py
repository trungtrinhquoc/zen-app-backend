"""
Logging Configuration
"""
import logging
import sys
from app.core.config import settings

# Create logger
logger = logging.getLogger("zen-app")
logger.setLevel(getattr(logging, settings.LOG_LEVEL))

# Create console handler with formatting
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))

# Create formatter
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
console_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(console_handler)

# Suppress noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)