"""Tests voor de API-microcache (backend/cache.py) en de middleware-integratie.

De unit-tests draaien direct op ResponseCache (TTL, alleen-200, single-flight).
De integratietest zet de cache gericht aan op de app (in conftest staat hij uit
voor alle andere tests) en gebruikt een maintenance-endpoint: dat werkt zonder
database en zit in de cacheable prefixes.
"""

import asyncio

import pytest

import backend.main as main_module
from backend.cache import ResponseCache


def _payload(status=200, body=b'{"ok":true}'):
    return (status, body, "application/json")


class TestResponseCache:
    def test_ttl_hit(self):
        async def run():
            cache = ResponseCache(ttl_seconds=30)
            calls = 0

            async def producer():
                nonlocal calls
                calls += 1
                return _payload()

            first, hit1 = await cache.get_or_produce("k", producer)
            second, hit2 = await cache.get_or_produce("k", producer)
            assert calls == 1
            assert (hit1, hit2) == (False, True)
            assert first == second

        asyncio.run(run())

    def test_non_200_niet_gecached(self):
        async def run():
            cache = ResponseCache(ttl_seconds=30)
            calls = 0

            async def producer():
                nonlocal calls
                calls += 1
                return _payload(status=503)

            _, hit1 = await cache.get_or_produce("k", producer)
            _, hit2 = await cache.get_or_produce("k", producer)
            assert calls == 2, "fout-antwoorden mogen nooit onthouden worden"
            assert (hit1, hit2) == (False, False)

        asyncio.run(run())

    def test_ttl_nul_is_passthrough(self):
        async def run():
            cache = ResponseCache(ttl_seconds=0)
            calls = 0

            async def producer():
                nonlocal calls
                calls += 1
                return _payload()

            _, hit1 = await cache.get_or_produce("k", producer)
            _, hit2 = await cache.get_or_produce("k", producer)
            assert calls == 2
            assert (hit1, hit2) == (False, False)
            assert not cache.enabled

        asyncio.run(run())

    def test_single_flight_collapst_gelijktijdige_verzoeken(self):
        async def run():
            cache = ResponseCache(ttl_seconds=30)
            calls = 0

            async def slow_producer():
                nonlocal calls
                calls += 1
                await asyncio.sleep(0.05)
                return _payload()

            results = await asyncio.gather(
                *(cache.get_or_produce("k", slow_producer) for _ in range(5))
            )
            assert calls == 1, "5 gelijktijdige identieke verzoeken horen 1 query te worden"
            assert all(payload == _payload() for payload, _ in results)
            # Precies één uitvoerder (MISS), de rest lift mee (HIT).
            assert sum(1 for _, hit in results if not hit) == 1

        asyncio.run(run())

    def test_producer_fout_bereikt_meelifters_en_wordt_niet_gecached(self):
        async def run():
            cache = ResponseCache(ttl_seconds=30)

            async def failing_producer():
                await asyncio.sleep(0.05)
                raise RuntimeError("db kapot")

            results = await asyncio.gather(
                *(cache.get_or_produce("k", failing_producer) for _ in range(3)),
                return_exceptions=True,
            )
            assert all(isinstance(r, RuntimeError) for r in results)

            # Na de fout is er niets gecached: een nieuwe poging draait gewoon weer.
            async def ok_producer():
                return _payload()

            payload, hit = await cache.get_or_produce("k", ok_producer)
            assert payload == _payload()
            assert hit is False

        asyncio.run(run())


@pytest.fixture
def cache_aan():
    """Zet de app-cache gericht aan voor één test en laat hem schoon achter."""
    cache = main_module._api_cache
    cache.ttl = 30
    cache.clear()
    yield cache
    cache.ttl = 0
    cache.clear()


class TestCacheMiddleware:
    def test_miss_dan_hit_op_data_endpoint(self, client, cache_aan):
        eerste = client.get("/api/maintenance/motors?days=30")
        tweede = client.get("/api/maintenance/motors?days=30")
        assert eerste.status_code == 200
        assert eerste.headers.get("X-Cache") == "MISS"
        assert tweede.headers.get("X-Cache") == "HIT"
        assert eerste.json() == tweede.json()

    def test_andere_parameters_eigen_cache_entry(self, client, cache_aan):
        a = client.get("/api/maintenance/motors?days=30")
        b = client.get("/api/maintenance/motors?days=60")
        assert a.headers.get("X-Cache") == "MISS"
        assert b.headers.get("X-Cache") == "MISS", "andere query-parameters = andere key"

    def test_health_blijft_buiten_de_cache(self, client, cache_aan):
        resp = client.get("/api/health")
        assert "X-Cache" not in resp.headers, "/api/health moet altijd live zijn"
