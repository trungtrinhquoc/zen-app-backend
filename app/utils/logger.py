"""
Logging Configuration
"""
import logging
import sys
from app.core.config import settings

# Configure logger
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("zen-app")
logging.getLogger("httpx").setLevel(logging.WARNING)