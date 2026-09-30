"""Customer agent: slots, tool policy, action router, catalog search, and the model tool loop."""

from .model import TOOLS, _merge_search, answer_with_openai, split_advice
from .policy import CHAT_REPLY, needs_tool
from .retrieve import (
    _ai_score,
    _battery_wh,
    _brand_like,
    _budget_band,
    _judge,
    _line_key,
    _name_query,
    _ram_gb,
    _rank_near,
    _split_budget,
    search_products,
)
from .route import route
from .slots import interpret, resolve_request
from .tools import (
    check_inventory,
    compare_products,
    find_product,
    follow_lead,
    get_checkout_requirements,
    get_product,
    lead_fits,
    list_orders,
    matches_request,
    place_order,
    prepare_checkout_request,
    refuse_request,
)
