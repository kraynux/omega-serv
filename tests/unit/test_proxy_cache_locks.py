import asyncio
import unittest

from omega_serv.application.server.proxy_cache_locks import ProxyCacheLocks


class TestProxyCacheLocks(unittest.TestCase):
    def test_same_key_returns_the_same_lock_instance(self):
        locks = ProxyCacheLocks()
        first = locks.get_lock("/api/", "abc")
        second = locks.get_lock("/api/", "abc")
        self.assertIs(first, second)

    def test_different_keys_return_different_locks(self):
        locks = ProxyCacheLocks()
        first = locks.get_lock("/api/", "abc")
        second = locks.get_lock("/api/", "def")
        self.assertIsNot(first, second)

    def test_different_zones_with_the_same_cache_key_are_independent(self):
        locks = ProxyCacheLocks()
        first = locks.get_lock("/a/", "same")
        second = locks.get_lock("/b/", "same")
        self.assertIsNot(first, second)


class TestProxyCacheLocksConcurrency(unittest.IsolatedAsyncioTestCase):
    async def test_only_one_coroutine_holds_the_lock_at_a_time(self):
        locks = ProxyCacheLocks()
        order: list[str] = []

        async def worker(name: str) -> None:
            lock = locks.get_lock("/api/", "k")
            async with lock:
                order.append(f"{name}-start")
                await asyncio.sleep(0.01)
                order.append(f"{name}-end")

        await asyncio.gather(worker("a"), worker("b"))
        # jamais "a-start", "b-start", "a-end", "b-end" (entrelace) - un seul
        # travailleur a la fois, l'autre attend la liberation du verrou.
        self.assertIn(order, (
            ["a-start", "a-end", "b-start", "b-end"],
            ["b-start", "b-end", "a-start", "a-end"],
        ))


if __name__ == "__main__":
    unittest.main()
