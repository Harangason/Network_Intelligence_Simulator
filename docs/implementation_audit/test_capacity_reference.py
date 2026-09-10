import unittest
from capacity_reference import (PeriodicTransmission, event_load_percent,
                                lin_nominal_bits, periodic_lin_demand,
                                serialize_can_requests, unique_transmissions)


class CapacityReferenceTests(unittest.TestCase):
    def stream(self, name='m', period=20, port='sensor'):
        return PeriodicTransmission('lin', port, name, 2, period)

    def test_complete_lin_frame(self):
        self.assertEqual(lin_nominal_bits(2), 64)
        self.assertEqual(lin_nominal_bits(8), 124)
        with self.assertRaises(ValueError):
            lin_nominal_bits(9)

    def test_subscribers_do_not_multiply_load(self):
        one = self.stream()
        result = periodic_lin_demand([one, one, one])
        self.assertEqual(result['physical_transmissions'], 1)
        self.assertAlmostEqual(result['nominal_demand_percent'], 100 / 6)

    def test_distinct_publishers_remain_distinct(self):
        self.assertEqual(len(unique_transmissions([self.stream(port='a'), self.stream(port='b')])), 2)

    def test_conflicting_periods_are_not_silently_merged(self):
        with self.assertRaises(ValueError):
            unique_transmissions([self.stream(period=20), self.stream(period=50)])

    def test_minimum_interval_preserves_slower_messages(self):
        result = periodic_lin_demand([self.stream('a', 5), self.stream('b', 50)])
        self.assertEqual([row['period_ms'] for row in result['details']], [20, 50])

    def test_brake_branch_still_exceeds_capacity_with_20_ms_floor(self):
        streams = [self.stream(str(i), period) for i, period in enumerate([5, 5, 5, 5, 10, 50, 50, 50])]
        result = periodic_lin_demand(streams)
        self.assertAlmostEqual(result['nominal_demand_percent'], 103 + 1/3)
        self.assertEqual(result['slot_reservation_percent'], 155)
        self.assertEqual(result['assessment'], 'OVERLOAD')

    def test_free_capacity_is_not_a_verified_schedule(self):
        result = periodic_lin_demand([self.stream(period=100)])
        self.assertEqual(result['assessment'], 'SCHEDULE_NOT_VERIFIED')

    def test_unknown_event_rate_does_not_turn_into_zero_load(self):
        self.assertIsNone(event_load_percent(3))
        self.assertEqual(event_load_percent(3, expected_events_per_second=0), 0)
        self.assertEqual(event_load_percent(3, expected_events_per_second=2), 0.6)

    def test_simultaneous_can_requests_serialize_by_priority(self):
        timeline = serialize_can_requests([(0, 30, 1, 'low'), (0, 10, 1, 'high')])
        self.assertEqual([row['name'] for row in timeline], ['high', 'low'])
        self.assertEqual(timeline[1]['start_ms'], timeline[0]['end_ms'])

    def test_bus_waiting_requests_rearbitrate_without_preemption(self):
        timeline = serialize_can_requests([(0, 30, 3, 'running'), (1, 20, 1, 'medium'), (2, 10, 1, 'high')])
        self.assertEqual([row['name'] for row in timeline], ['running', 'high', 'medium'])
        self.assertEqual(timeline[0]['end_ms'], 3)
        self.assertEqual(timeline[1]['waiting_ms'], 1)


if __name__ == '__main__':
    unittest.main()
