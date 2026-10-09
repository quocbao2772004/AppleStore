"""Opt-in consultation trace. Set AGENT_DEBUG_REQUIREMENTS=1 while diagnosing."""
import json
import logging
import os


def debug(event, **fields):
    if os.environ.get("AGENT_DEBUG_REQUIREMENTS") != "1":
        return
    logging.getLogger("agent.requirements").warning(
        "%s %s", event, json.dumps(fields, ensure_ascii=False, default=str)
    )
