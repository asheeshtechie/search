import functools
import logging
import time
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)

# Disable boto3 and botocore debug messages
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

def debug(func):
    """
    Debug decorator that logs function entry, exit, execution time, and any errors
    
    :param func: Function to be decorated
    :return: Decorated function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Get logger for the function's module
        logger = logging.getLogger(func.__module__)
        
        # Log function entry
        func_args = ', '.join([
            f"{k}={v!r}" for k, v in kwargs.items()
        ] + [repr(a) for a in args])
        logger.debug(f"Entering {func.__name__}({func_args})")
        
        start_time = time.time()
        try:
            # Execute the function
            result = func(*args, **kwargs)
            
            # Log function exit and execution time
            execution_time = time.time() - start_time
            logger.debug(f"Exiting {func.__name__} - Execution time: {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            # Log any errors
            execution_time = time.time() - start_time
            logger.error(f"Error in {func.__name__} - Execution time: {execution_time:.2f}s")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
            
    return wrapper 