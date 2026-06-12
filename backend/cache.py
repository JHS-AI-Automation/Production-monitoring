"""In-memory micro-cache met single-flight voor de lees-API.

Waarom: op het edge-device is de database de bottleneck, niet de webserver. Als
20 gebruikers tegelijk dezelfde dagcijfers openen, draaien er zonder cache 20
identieke zware queries. Deze cache lost dat tweeledig op:

1. **TTL-cache**: een antwoord wordt kort onthouden (default 30s, instelbaar via
   `API_CACHE_TTL_SECONDS`, 0 = uit). Productiecijfers van "maximaal een halve
   minuut oud" zijn voor dit dashboard ruim acceptabel.
2. **Single-flight**: gelijktijdige identieke verzoeken wachten op één
   uitvoering in plaats van allemaal zelf de query te draaien. Dit is de echte
   wachtrij-killer bij piekgebruik.

Bewust simpel gehouden: process-lokaal (er draait één uvicorn-worker), geen
Redis, begrensde omvang (oudste entry eruit bij overloop). Alleen succesvolle
antwoorden (HTTP 200) worden onthouden; fouten worden nooit gecached.
"""
import asyncio
import time

_MAX_ENTRIES = 256

# Payload = (status_code, body_bytes, media_type). Bewust een kant-en-klare
# HTTP-respons en geen Python-objecten: replayen is dan triviaal en goedkoop.
Payload = tuple[int, bytes, str | None]


class ResponseCache:
    def __init__(self, ttl_seconds: float):
        self.ttl = ttl_seconds
        self._entries: dict[str, tuple[float, Payload]] = {}
        self._inflight: dict[str, asyncio.Future] = {}

    @property
    def enabled(self) -> bool:
        return self.ttl > 0

    def clear(self) -> None:
        self._entries.clear()

    async def get_or_produce(self, key: str, producer) -> tuple[Payload, bool]:
        """Geef (payload, was_cache_hit). `producer` is een async callable zonder
        argumenten die de payload maakt; hij draait hooguit één keer per key
        tegelijk, ook bij N gelijktijdige aanroepen (single-flight)."""
        if not self.enabled:
            return await producer(), False

        now = time.monotonic()
        cached = self._entries.get(key)
        if cached and cached[0] > now:
            return cached[1], True

        inflight = self._inflight.get(key)
        if inflight is not None:
            # Iemand anders draait deze query al: meeliften op het resultaat.
            return await asyncio.shield(inflight), True

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            payload = await producer()
        except BaseException as e:
            # Fout doorduwen naar alle meelifters; niets cachen.
            if not future.done():
                future.set_exception(e)
            # Voorkom "exception was never retrieved"-ruis als niemand meelift.
            future.exception()
            raise
        else:
            if payload[0] == 200:
                self._entries[key] = (now + self.ttl, payload)
                self._evict_if_needed()
            if not future.done():
                future.set_result(payload)
            return payload, False
        finally:
            self._inflight.pop(key, None)

    def _evict_if_needed(self) -> None:
        if len(self._entries) <= _MAX_ENTRIES:
            return
        oldest_key = min(self._entries, key=lambda k: self._entries[k][0])
        del self._entries[oldest_key]
