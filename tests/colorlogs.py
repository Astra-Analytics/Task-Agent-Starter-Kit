import colorlog
from colorlog import ColoredFormatter

# Define a mapping from thread names to colors
THREAD_COLOR_MAPPING = {
    "EmailProcessor": "red",
    "email_fetcher": "green",
    "EntityExtraction": "blue",
    # Add other thread name to color mappings here
}


class ThreadNameColoredFormatter(ColoredFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the default log colors based on log levels
        self.default_log_colors = {
            "DEBUG": "cyan",
            "INFO": "white",  # Default color for INFO, will be overridden by thread color if available
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        }

    def format(self, record):
        # Set the log color based on log level
        self.log_colors = self.default_log_colors.copy()

        # Override the log color for INFO based on thread name if applicable
        if record.levelname == "INFO":
            thread_name = (
                record.threadName.split("-")[0] if record.threadName else "Thread"
            )  # Use the base name for mapping
            thread_log_color = THREAD_COLOR_MAPPING.get(thread_name, "white")
            self.log_colors["INFO"] = thread_log_color

        return super().format(record)


# Configure the formatter
formatter = ThreadNameColoredFormatter(
    "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Usage example in the main application setup
if __name__ == "__main__":
    import logging
    import threading

    # Set up the handler and logger
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    # Define a test function to generate logs in different threads
    def log_messages(logger):
        logger.debug("This is a DEBUG message")
        logger.info("This is an INFO message")
        logger.warning("This is a WARNING message")
        logger.error("This is an ERROR message")
        logger.critical("This is a CRITICAL message")

    # Create and start threads
    threads = []
    for thread_name in ["EmailProcessor", "email_fetcher", "EntityExtraction"]:
        thread_logger = logging.getLogger(thread_name)
        thread = threading.Thread(
            name=thread_name, target=log_messages, args=(thread_logger,)
        )
        threads.append(thread)
        thread.start()

    # Log from the main thread
    log_messages(logger)

    # Wait for all threads to complete
    for thread in threads:
        thread.join()
