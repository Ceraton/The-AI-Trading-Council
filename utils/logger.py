import logging
import os
import sys

def setup_logger(name=__name__, log_level=logging.INFO):
    """
    Sets up a logger with the specified name and log level.
    """
    # Fix for Windows Unicode errors (emojis in logs)
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            # Fallback for very old python or restricted streams
            pass

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Prevent adding multiple handlers to the same logger
    if not logger.handlers:
        # Console Handler
        c_handler = logging.StreamHandler(sys.stdout)
        c_handler.setLevel(log_level)

        # File Handler
        log_dir = os.path.join(os.getcwd(), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        # Explicitly set UTF-8 for file storage
        f_handler = logging.FileHandler(os.path.join(log_dir, 'bot.log'), encoding='utf-8')
        f_handler.setLevel(log_level)

        # Formatter
        c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        f_handler.setFormatter(c_format)

        logger.addHandler(c_handler)
        logger.addHandler(f_handler)

    return logger
