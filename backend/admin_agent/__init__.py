"""Admin agent: offline router, read-only reports, and the model tool loop."""

from .answer import TOOLS, _run_tool, answer_admin
from .format import STATUS_LABEL, _fold, _money, _period_start
from .route import local_calls
