"""The module that contains the exceptions for the framework."""


class EventCannotBeProcessed(Exception):
    """The exception that is raised when the event cannot be processed."""


class DisabledButtonClick(Exception):
    """The exception that is raised when the button click is disabled."""
