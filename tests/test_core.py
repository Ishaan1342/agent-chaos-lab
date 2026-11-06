import unittest
from concurrent.futures import ThreadPoolExecutor
from chaoslab.core import BookingWorld, SCENARIOS, ToolFault, run_scenario


class ReliabilityTests(unittest.TestCase):
    def test_all_reference_scenarios(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                self.assertTrue(run_scenario(scenario)["passed"])

    def test_negative_control_exposes_duplicate_commit(self):
        result = run_scenario("timeout_after_commit", naive=True)
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["bookings"]), 2)

    def test_same_key_under_concurrency_commits_once(self):
        world = BookingWorld()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(
                pool.map(
                    lambda _: world.call(
                        "book",
                        dict(
                            slot="court-1-1900",
                            expected_price_cents=4000,
                            idempotency_key="intent",
                        ),
                    ),
                    range(30),
                )
            )
        self.assertEqual(len(world.bookings), 1)
        self.assertEqual({r["booking_id"] for r in results}, {"B001"})

    def test_reused_key_for_changed_operation_is_rejected(self):
        world = BookingWorld()
        world.call(
            "book",
            dict(
                slot="court-1-1900", expected_price_cents=4000, idempotency_key="intent"
            ),
        )
        with self.assertRaises(ToolFault) as caught:
            world.call(
                "book",
                dict(
                    slot="court-1-1900",
                    expected_price_cents=5000,
                    idempotency_key="intent",
                ),
            )
        self.assertEqual(caught.exception.code, "KEY_CONFLICT")

    def test_response_mutation_cannot_change_world(self):
        world = BookingWorld()
        result = world.call(
            "book",
            dict(
                slot="court-1-1900", expected_price_cents=4000, idempotency_key="intent"
            ),
        )
        result["status"] = "forged"
        self.assertEqual(world.snapshot()["bookings"]["B001"]["status"], "confirmed")

    def test_bad_arguments_do_not_mutate_ledger(self):
        world = BookingWorld()
        for price in (True, -1, "4000"):
            with self.assertRaises(ToolFault):
                world.call(
                    "book",
                    dict(
                        slot="court-1-1900",
                        expected_price_cents=price,
                        idempotency_key="x",
                    ),
                )
        self.assertFalse(world.bookings)

    def test_non_object_arguments_fail_without_crashing_adapter(self):
        world = BookingWorld()
        for arguments in (None, [], "bad"):
            with self.assertRaises(ToolFault) as caught:
                world.call("get_booking", arguments)
            self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")
        self.assertFalse(world.bookings)


if __name__ == "__main__":
    unittest.main()
