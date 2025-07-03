import logging
import uuid
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

def get_logger(name: str):
    return structlog.get_logger(name).bind(trace_id=str(uuid.uuid4()))
