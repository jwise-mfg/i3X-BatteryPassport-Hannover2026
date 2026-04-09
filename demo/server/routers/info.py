from fastapi import APIRouter, Request
from .utils import success_response

info = APIRouter(prefix="", tags=["Info"])

I3X_SPEC_VERSION = "1.0"


# RFC - Server Capabilities
@info.get("/info", summary="Server Info", operation_id="getInfo")
def get_info(request: Request):
    """Returns the server version and capabilities. May be used as a health check.
    This endpoint does not require authentication."""
    app_config = getattr(request.app.state, "app_config", {})
    capabilities_config = getattr(request.app.state, "capabilities_config", {})

    query_cap = capabilities_config.get("query", {})
    update_cap = capabilities_config.get("update", {})
    subscribe_cap = capabilities_config.get("subscribe", {})

    # Capabilities may be booleans (shorthand) or dicts (granular).
    # Normalize: if a boolean is provided, expand it into the detailed form.
    if not isinstance(query_cap, dict):
        query_cap = {"history": bool(query_cap)}
    if not isinstance(update_cap, dict):
        update_cap = {"current": bool(update_cap), "history": False}
    if not isinstance(subscribe_cap, dict):
        subscribe_cap = {"stream": bool(subscribe_cap)}

    return success_response({
        "specVersion": I3X_SPEC_VERSION,
        "serverVersion": app_config.get("version"),
        "serverName": app_config.get("title"),
        "capabilities": {
            "query": {
                "history": query_cap.get("history", True),
            },
            "update": {
                "current": update_cap.get("current", True),
                "history": update_cap.get("history", False),
            },
            "subscribe": {
                "stream": subscribe_cap.get("stream", True),
            },
        },
    })
