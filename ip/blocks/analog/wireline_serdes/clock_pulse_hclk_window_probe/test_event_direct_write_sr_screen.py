#!/usr/bin/env python3

import unittest

import run_event_direct_write_sr_screen as screen


class DirectWriteSrScreenTest(unittest.TestCase):
    def test_digest_is_content_identity(self) -> None:
        self.assertEqual(len(screen.digest(screen.Path(__file__))), 64)


if __name__ == "__main__":
    unittest.main()
