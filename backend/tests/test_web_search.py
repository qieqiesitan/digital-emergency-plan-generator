"""Test suite for BingSearch (Scrapling backend)."""
import sys, os, time, threading, unittest

sys.path.insert(0, r"C:\Users\55061\Documents\数字化预案自动生成 2\backend")
os.chdir(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend")

from app.services.web_search import BingSearch, MIN_INTERVAL


class TestBasicSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bs = BingSearch(min_interval=0.1)

    def test_chinese_query(self):
        results = self.bs.search("台风应急预案", 3)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("title", r)
            self.assertIn("url", r)
            self.assertIn("snippet", r)
            self.assertTrue(r["url"].startswith("http"))

    def test_english_query(self):
        results = self.bs.search("emergency response plan", 3)
        self.assertGreater(len(results), 0)

    def test_mixed_query(self):
        results = self.bs.search("AI 灾害预警", 3)
        self.assertGreater(len(results), 0)

    def test_max_results_capped(self):
        for n in [1, 3, 5]:
            results = self.bs.search("地震", n)
            self.assertLessEqual(len(results), n)

    def test_result_structure(self):
        results = self.bs.search("洪水", 5)
        for r in results:
            self.assertTrue(r["title"])
            self.assertTrue(r["url"])

    def test_no_bing_internal_links(self):
        results = self.bs.search("应急预案", 5)
        for r in results:
            self.assertNotIn("bing.com", r["url"])


class TestRateLimiting(unittest.TestCase):
    def test_minimum_interval_enforced(self):
        bs = BingSearch(min_interval=1.5)
        bs.search("test", 1)
        t0 = time.time()
        bs.search("test2", 1)
        elapsed = time.time() - t0
        self.assertGreaterEqual(elapsed, 0.8)

    def test_burst_calls_queued(self):
        bs = BingSearch(min_interval=2.0)
        t0 = time.time()
        results = [bs.search(q, 1) for q in ("A", "B", "C")]
        total = time.time() - t0
        self.assertEqual(len(results), 3)
        self.assertGreaterEqual(total, 3.5)


class TestThreadSafety(unittest.TestCase):
    def test_concurrent_searches(self):
        bs = BingSearch(min_interval=0.1)
        errors = []
        results_by_thread = {}

        def worker(tid):
            try:
                results_by_thread[tid] = bs.search(f"test query {tid}", 2)
            except Exception as e:
                errors.append((tid, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results_by_thread), 4)
        for tid, results in results_by_thread.items():
            self.assertGreater(len(results), 0)


class TestEdgeCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bs = BingSearch(min_interval=0.1)

    def test_empty_query(self):
        results = self.bs.search("", 3)
        self.assertIsInstance(results, list)

    def test_special_characters(self):
        results = self.bs.search('test <>" and query', 2)
        self.assertIsInstance(results, list)

    def test_very_long_query(self):
        results = self.bs.search("应急 " * 50, 2)
        self.assertIsInstance(results, list)

    def test_zero_max_results(self):
        results = self.bs.search("测试", 0)
        self.assertEqual(len(results), 0)

    def test_unicode_query(self):
        results = self.bs.search("fire emergency", 2)
        self.assertIsInstance(results, list)


if __name__ == "__main__":
    print("=" * 60)
    print("   BingSearch (Scrapling) Test Suite")
    print("=" * 60)
    unittest.main(verbosity=2)
