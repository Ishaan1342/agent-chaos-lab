import os
import sys
import unittest

try:
    from mcp import Client, StdioServerParameters

    HAS_MCP = True
except ImportError:
    HAS_MCP = False


@unittest.skipUnless(
    HAS_MCP, "Install optional mcp==2.3.0 for real transport integration"
)
class MCPTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_timeout_retry_and_cancellation(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "chaoslab.server"],
            env={**os.environ, "CHAOS_SCENARIO": "timeout_after_commit"},
        )
        async with Client(params) as client:
            tools = await client.list_tools()
            self.assertEqual(
                {t.name for t in tools.tools},
                {"quote", "book", "cancel", "get_booking", "snapshot"},
            )
            args = dict(
                slot="court-1-1900",
                expected_price_cents=4000,
                idempotency_key="wire-intent",
            )
            first = (await client.call_tool("book", args)).structured_content
            self.assertFalse(first["ok"])
            self.assertTrue(first["error"]["may_have_committed"])
            second = (await client.call_tool("book", args)).structured_content
            self.assertEqual(second["result"]["booking_id"], "B001")
            state = (await client.call_tool("snapshot", {})).structured_content
            self.assertEqual(len(state["bookings"]), 1)
            result = (
                await client.call_tool(
                    "cancel", dict(booking_id="B001", idempotency_key="cancel-wire")
                )
            ).structured_content
            self.assertEqual(result["result"]["status"], "cancelled")
