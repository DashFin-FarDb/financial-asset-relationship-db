import logging

from .events import ObservabilityEvent


def get_logger(name: str) -> logging.Logger:
    """
    Get a standard library logger configured for the given name.

    Parameters:
        name (str): Name of the logger.

    Returns:
        logging.Logger: Logger instance associated with the provided name.
    """
    return logging.getLogger(name)


def log_event(logger: logging.Logger, level: int, event: ObservabilityEvent) -> None:
    """
    Emit a structured observability event.

    Args:
        logger: The logger instance to use.
        level: The logging level (e.g., logging.INFO).
        event: The ObservabilityEvent instance to log.
    """
    # We pass the human-readable message as the primary log message to ensure
    # that standard library logging utilities (like pytest's caplog) still
    # see the descriptive text. The 'event' slug in to_extra() will overwrite
    # the top-level 'event' key in the final structured JSON output.
    logger.log(level, event.message, extra=event.to_extra())
