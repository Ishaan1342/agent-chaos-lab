# Agent Chaos Lab

Python 3.11+ · MIT · Experimental

An offline, stateful booking simulator for testing agent recovery policies.
The key case: a booking succeeds, its response is lost, and a retry creates a
second booking unless the client keeps the same idempotency key.

[![Tests](https://github.com/Ishaan1342/agent-chaos-lab/actions/workflows/test.yml/badge.svg)](https://github.com/Ishaan1342/agent-chaos-lab/actions/workflows/test.yml)

## Install from this repository

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

See [Contributing](CONTRIBUTING.md), [Security](SECURITY.md) and the
[Changelog](CHANGELOG.md).

## Run the demo

Python 3.11+; the core has no third-party dependencies.

```sh
python -m chaoslab demo --output artifacts/demo.json
python -m unittest discover -s tests -v
```

The demo runs seven reference-policy scenarios and an intentionally broken
negative control. The reference is deterministic Python, not an evaluated model.
It tests clean booking, pre-commit timeout, post-commit timeout, rate limiting,
price changes, a slot taken after quoting, and a lost cancellation response.
Every scenario emits booking state, a tool-call trace and invariant results.

## Connect an actual agent through MCP

```sh
python -m venv .venv
.venv/bin/pip install -e '.[mcp]'
CHAOS_SCENARIO=timeout_after_commit .venv/bin/python -m chaoslab.server
```

Use that command as a stdio MCP server in your host. Set the working directory
to this repository or install the package. `mcp==2.3.0` is the tested SDK.
It owns MCP framing and schemas. All tools explicitly return structured output.
Business faults are `{ok:false,error:{code,retryable,may_have_committed}}`, not
transport failures. Success is `{ok:true,result:...}`. `snapshot` is an inspection
tool exposing the simulator state, not something a production booking service
should expose. A new subprocess creates a fresh isolated world.

Tools: `quote`, `book`, `get_booking`, `cancel`, `snapshot`. The test slot is
`court-1-1900`, the original price is 4000 EUR cents. Hold one idempotency key per
user intent across retries. The price-change scenario requires confirmation of
a new quote; it never authorizes a higher price automatically.

```sh
.venv/bin/python -m unittest discover -s tests -v
```

This includes a real subprocess stdio integration test. Without the SDK that
one test is explicitly skipped. An alternative `serve-jsonl --scenario ...`
adapter accepts one `{tool,arguments}` object per line for non-MCP harnesses;
that adapter is NOT the MCP protocol.

## Scope and relationship to existing tools

Cisco's [mcptoolkit-mock](https://github.com/cisco-open/mcptoolkit-mock) already
provides mocking, recording and replay. This repository is a complementary
stateful domain fixture, not a replacement for those capabilities and not an
upstream patch. Its [stateful-response request](https://github.com/cisco-open/mcptoolkit-mock/issues/15)
motivates the use case. A Cisco fixture/export adapter is future work.

Faults are simulated protocol outcomes, not measured network latency, a real
proxy, or a benchmark of a particular model. State is in memory; no persistence
or actual bookings. Multiple bookings are deliberately permitted so naive
retries remain observable. No background service or model API is needed.
