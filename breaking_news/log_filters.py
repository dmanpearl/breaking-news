import logging


class SuppressPollFilter(logging.Filter):
    """
    Drop access log entries for the poll endpoint.

    Handles both loggers:
    - django.server (runserver): record.args is a tuple where args[0]
      is the full request line e.g. "GET /messages/poll/ HTTP/1.1"
    - uvicorn.access: record.args is a tuple where args[2] is the path

    Without this filter, polling at 2s produces ~30 log lines per minute
    per user, burying real entries in both dev and production.
    """

    _SUPPRESSED = ("/messages/poll/",)

    def filter(self, record: logging.LogRecord) -> bool:
        # Build a single string from whatever args format the logger uses.
        msg = ""
        args = record.args
        if isinstance(args, tuple):
            msg = " ".join(str(a) for a in args)
        elif isinstance(args, str):
            msg = args
        else:
            try:
                msg = record.getMessage()
            except Exception:
                pass
        for suppressed in self._SUPPRESSED:
            if suppressed in msg:
                return False
        return True
