import unittest

from log import Log


class Test(unittest.TestCase):

    def test_manager_init(self):
        log = Log()
        self.assertTrue(log is not None, "Log object not initialized")
        self.assertTrue(log.commit_index == 0, "Invalid initialization for commit_index")
        self.assertTrue(log.last_applied == 0, "Invalid initialization for last_applied")
        self.assertTrue(log.entries is not None and len(log.entries) == 0,
                        "Log entries not initialized")
        self.assertTrue(log.get_earliest_unapplied() is None, "Earliest unapplied shouldn't exist")
        self.assertTrue(log.get_earliest_unapplied() is None, "Earliest commit shouldn't exist")


if __name__ == '__main__':
    unittest.main()
