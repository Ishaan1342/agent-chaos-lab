"""Deterministic, in-memory fault model. No real bookings or network calls."""
from copy import deepcopy
from threading import RLock


class ToolFault(Exception):
    def __init__(self, code, message, *, retryable=False, may_have_committed=False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.may_have_committed = may_have_committed

    def as_dict(self):
        return dict(code=self.code, message=str(self), retryable=self.retryable,
                    may_have_committed=self.may_have_committed)


SCENARIOS = ("clean", "timeout_before_commit", "timeout_after_commit",
             "rate_limit_once", "price_change", "slot_taken", "cancel_timeout")


class BookingWorld:
    """One isolated simulation. Prices are integer EUR cents; lock models atomic writes."""
    def __init__(self, scenario="clean"):
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")
        self.scenario = scenario
        self.bookings = {}
        self.ledger = {}
        self.events = []
        self._fired = set()
        self._lock = RLock()

    def call(self, tool, arguments):
        if not isinstance(tool, str) or not isinstance(arguments, dict):
            raise ToolFault("INVALID_ARGUMENT", "Tool name must be a string and arguments an object")
        with self._lock:
            event = {"sequence": len(self.events) + 1, "tool": tool,
                     "arguments": deepcopy(arguments)}
            self.events.append(event)
            try:
                if tool == "quote":
                    if arguments != {"slot": "court-1-1900"}:
                        raise ToolFault("INVALID_ARGUMENT", "Unknown slot")
                    result = {"slot": arguments["slot"], "price_cents": 4000,
                              "currency": "EUR"}
                elif tool == "book":
                    result = self._book(**arguments)
                elif tool == "cancel":
                    result = self._cancel(**arguments)
                elif tool == "get_booking":
                    result = deepcopy(self.bookings.get(arguments.get("booking_id")))
                    if result is None:
                        raise ToolFault("NOT_FOUND", "Booking not found")
                else:
                    raise ToolFault("UNKNOWN_TOOL", tool)
                event["result"] = deepcopy(result)
                return deepcopy(result)
            except ToolFault as exc:
                event["error"] = exc.as_dict()
                raise
            except (TypeError, KeyError) as exc:
                fault = ToolFault("INVALID_ARGUMENT", "Invalid tool arguments")
                event["error"] = fault.as_dict()
                raise fault from exc

    def _once(self, name):
        if self.scenario == name and name not in self._fired:
            self._fired.add(name)
            return True
        return False

    def _replay(self, key, fingerprint):
        if not isinstance(key, str) or not key.strip():
            raise ToolFault("INVALID_ARGUMENT", "A non-empty idempotency key is required")
        if key in self.ledger:
            prior, response = self.ledger[key]
            if prior != fingerprint:
                raise ToolFault("KEY_CONFLICT", "Key already used for a different operation")
            return deepcopy(response)
        return None

    def _book(self, slot, expected_price_cents, idempotency_key):
        if slot != "court-1-1900" or type(expected_price_cents) is not int or expected_price_cents < 0:
            raise ToolFault("INVALID_ARGUMENT", "Unknown slot or invalid integer price")
        fingerprint = ("book", slot, expected_price_cents)
        replay = self._replay(idempotency_key, fingerprint)
        if replay is not None:
            return replay
        if self._once("timeout_before_commit"):
            raise ToolFault("TIMEOUT", "No commit occurred", retryable=True)
        if self._once("rate_limit_once"):
            raise ToolFault("RATE_LIMIT", "Retry after one virtual tick", retryable=True)
        if self.scenario == "slot_taken":
            raise ToolFault("UNAVAILABLE", "Slot was taken after the quote")
        actual_price = 5000 if self.scenario == "price_change" else 4000
        if expected_price_cents != actual_price:
            raise ToolFault("PRICE_CHANGED", "Fresh price requires new user confirmation")
        booking_id = f"B{len(self.bookings) + 1:03d}"
        result = dict(booking_id=booking_id, slot=slot, price_cents=actual_price,
                      currency="EUR", status="confirmed")
        self.bookings[booking_id] = deepcopy(result)
        self.ledger[idempotency_key] = (fingerprint, deepcopy(result))
        if self._once("timeout_after_commit"):
            raise ToolFault("TIMEOUT", "Response lost after commit", retryable=True,
                            may_have_committed=True)
        return result

    def _cancel(self, booking_id, idempotency_key):
        fingerprint = ("cancel", booking_id)
        replay = self._replay(idempotency_key, fingerprint)
        if replay is not None:
            return replay
        if booking_id not in self.bookings:
            raise ToolFault("NOT_FOUND", "Booking not found")
        self.bookings[booking_id]["status"] = "cancelled"
        result = deepcopy(self.bookings[booking_id])
        self.ledger[idempotency_key] = (fingerprint, deepcopy(result))
        if self._once("cancel_timeout"):
            raise ToolFault("TIMEOUT", "Cancellation committed; response lost",
                            retryable=True, may_have_committed=True)
        return result

    def snapshot(self):
        with self._lock:
            return deepcopy(dict(scenario=self.scenario, bookings=self.bookings,
                                 events=self.events))


def run_scenario(scenario, *, naive=False):
    """Reference policies, not an LLM benchmark. Naive intentionally rotates retry keys."""
    world = BookingWorld(scenario)
    quote = world.call("quote", {"slot": "court-1-1900"})
    outcome = "failed"
    booking = None
    for attempt in range(3):
        key = f"user-intent-1-{attempt}" if naive else "user-intent-1"
        try:
            booking = world.call("book", dict(slot=quote["slot"],
                expected_price_cents=quote["price_cents"], idempotency_key=key))
            outcome = "booked"
            break
        except ToolFault as exc:
            if exc.code == "PRICE_CHANGED":
                outcome = "needs_confirmation"
                break
            if exc.code == "UNAVAILABLE":
                outcome = "unavailable"
                break
            if not exc.retryable:
                break
    if scenario == "cancel_timeout" and booking:
        for _ in range(3):
            try:
                world.call("cancel", dict(booking_id=booking["booking_id"],
                                          idempotency_key="cancel-intent-1"))
                outcome = "cancelled"
                break
            except ToolFault as exc:
                if not exc.retryable:
                    break
    expected = {"price_change": "needs_confirmation", "slot_taken": "unavailable",
                "cancel_timeout": "cancelled"}.get(scenario, "booked")
    state = world.snapshot()
    checks = {"at_most_one_booking": len(state["bookings"]) <= 1,
              "expected_outcome": outcome == expected,
              "no_unapproved_price": all(b["price_cents"] == 4000 for b in state["bookings"].values())}
    return dict(policy="naive" if naive else "idempotent", outcome=outcome,
                passed=all(checks.values()), checks=checks, **state)
