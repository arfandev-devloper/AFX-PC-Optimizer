import unittest

from optimizer_core import bytes_to_human


class CoreTests(unittest.TestCase):
    def test_bytes_to_human(self):
        self.assertEqual(bytes_to_human(0), "0.0 B")
        self.assertEqual(bytes_to_human(1024), "1.0 KB")
        self.assertEqual(bytes_to_human(1024 ** 3), "1.0 GB")


if __name__ == "__main__":
    unittest.main()
