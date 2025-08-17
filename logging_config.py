"""
Enhanced Logging Configuration
Centralized logging setup with different levels for different components
"""

import logging
import sys
from typing import Dict, Any, Optional


class GameLogger:
    """Enhanced logging for WWII Text Adventure with component-specific levels."""
    
    def __init__(self):
        self.loggers = {}
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging configuration for the application."""
        # Main application logger
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Component-specific loggers
        self.loggers['app'] = logging.getLogger('wwii_game.app')
        self.loggers['ai'] = logging.getLogger('wwii_game.ai')
        self.loggers['session'] = logging.getLogger('wwii_game.session')
        self.loggers['database'] = logging.getLogger('wwii_game.database')
        self.loggers['performance'] = logging.getLogger('wwii_game.performance')
        
        # Set specific levels for different components
        self.loggers['ai'].setLevel(logging.INFO)  # Reduce AI logging noise
        self.loggers['performance'].setLevel(logging.WARNING)  # Only show warnings
    
    def get_logger(self, component: str) -> logging.Logger:
        """Get logger for specific component."""
        return self.loggers.get(component, logging.getLogger(f'wwii_game.{component}'))
    
    def log_ai_request(self, prompt_type: str, prompt_length: int, response_length: int = 0):
        """Log AI request with performance metrics."""
        logger = self.get_logger('ai')
        logger.info(f"AI Request - Type: {prompt_type}, Prompt Length: {prompt_length}, Response Length: {response_length}")
    
    def log_session_operation(self, operation: str, session_size: int, data: Optional[Dict[str, Any]] = None):
        """Log session operations with size tracking."""
        logger = self.get_logger('session')
        logger.debug(f"Session {operation} - Size: {session_size} bytes" + 
                    (f", Data: {data}" if data else ""))
    
    def log_performance_metric(self, metric_name: str, value: float, context: str = ""):
        """Log performance metrics."""
        logger = self.get_logger('performance')
        logger.info(f"Performance - {metric_name}: {value}" + (f" ({context})" if context else ""))
    
    def log_game_event(self, event_type: str, details: Dict[str, Any]):
        """Log significant game events."""
        logger = self.get_logger('app')
        logger.info(f"Game Event - {event_type}: {details}")


# Global logger instance
game_logger = GameLogger()