"""Optional real MCP transport through the official SDK, never hand-rolled JSON-RPC."""

import os
from typing import Any
from mcp.server import MCPServer
from .core import BookingWorld, ToolFault

server = MCPServer("Agent Chaos Lab")
world = BookingWorld(os.environ.get("CHAOS_SCENARIO", "timeout_after_commit"))


def invoke(tool, arguments):
    try:
        return {"ok": True, "result": world.call(tool, arguments)}
    except ToolFault as exc:
        return {"ok": False, "error": exc.as_dict()}


@server.tool(structured_output=True)
def quote(slot: str) -> dict[str, Any]:
    """Get a quote in EUR cents for the simulated slot court-1-1900."""
    return invoke("quote", {"slot": slot})


@server.tool(structured_output=True)
def book(slot: str, expected_price_cents: int, idempotency_key: str) -> dict[str, Any]:
    """Simulate a booking. A timeout may happen AFTER the booking commits."""
    return invoke(
        "book",
        dict(
            slot=slot,
            expected_price_cents=expected_price_cents,
            idempotency_key=idempotency_key,
        ),
    )


@server.tool(structured_output=True)
def get_booking(booking_id: str) -> dict[str, Any]:
    """Inspect a simulated booking after an uncertain response."""
    return invoke("get_booking", {"booking_id": booking_id})


@server.tool(structured_output=True)
def cancel(booking_id: str, idempotency_key: str) -> dict[str, Any]:
    """Cancel a simulated booking idempotently."""
    return invoke(
        "cancel", dict(booking_id=booking_id, idempotency_key=idempotency_key)
    )


@server.tool(structured_output=True)
def snapshot() -> dict[str, Any]:
    """Inspect the simulator ledger and event trace (test use only)."""
    return world.snapshot()


if __name__ == "__main__":
    server.run()
