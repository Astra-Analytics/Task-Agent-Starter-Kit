from colorlog import ColoredFormatter

# Define a mapping from thread names to colors
THREAD_COLOR_MAPPING = {
    "EmailProcessor": "cyan",
    "email_fetcher": "purple",
    "EntityExtraction": "blue",
    # Add other thread name to color mappings here
}


class ThreadNameColoredFormatter(ColoredFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the default log colors based on log levels
        self.default_log_colors = {
            "DEBUG": "light_white",
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
