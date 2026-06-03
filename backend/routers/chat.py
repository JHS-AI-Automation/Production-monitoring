import asyncio
import json
import logging
import re
import time
from collections import defaultdict
from contextlib import asynccontextmanager

import asyncpg
from openai import AsyncOpenAI
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.config import Settings
from backend.database import create_db_pool, get_connection

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None
_model: str = "anthropic/claude-sonnet-4"
_chat_pool: asyncpg.Pool | None = None

MAX_TOOL_LOOPS = 5
# Rate limit is per client-IP. Let op: meerdere gebruikers achter hetzelfde
# kantoor-NAT delen één IP en dus dit budget. 30/min laat ~5 gebruikers vlot chatten.
RATE_LIMIT_MAX = 30
RATE_LIMIT_WINDOW = 60

# Maximaal aantal gelijktijdige LLM-conversaties. Beschermt de chat-pool (max 5) en
# de OpenRouter-quota: een chat-call kan tot MAX_TOOL_LOOPS rondes + SQL duren.
# Extra verzoeken wachten (async) i.p.v. de pool/quota te overspoelen.
LLM_CONCURRENCY = 4

_rate_limits: dict[str, list[float]] = defaultdict(list)
_llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

SCHEMA_CONTEXT = """Je bent een data-analist voor DGS, een vleesverwerkingsbedrijf in Haaksbergen.
Je hebt read-only toegang tot een PostgreSQL database (db_dgs_01) met PLC-data van de productielijn.

Beschikbare tabellen:

1. plc_alarms - Alle PLC alarmen
   - time (timestamp): moment dat het alarm optrad
   - incomingstate (int): 1 = alarm geactiveerd, 0 = alarm verholpen
   - alarmmessage (text): beschrijving van het alarm
   - severityclass (varchar): ernst (Error, Warning, Info)

2. plc_alarms_mp1 - Alarmen specifiek voor MP1 machine (meer detail)
   - time (timestamp): moment dat het alarm optrad
   - alarmid (int): numeriek alarm-ID
   - alarmmessage (text): beschrijving van het alarm
   - severityclass (varchar): ernst
   - incomingstate (int): 1 = actief, 0 = verholpen
   - eventid (varchar): unieke event identifier (hex)

3. capacity_perminutev2 - Productie-tellers per minuut
   - time (timestamp): meetmoment
   - counter0 (int): productieteller Lijn 1 (overflow)
   - counter1 (int): productieteller Lijn 2 (invoer)
   - counter2 (int): productieteller Lijn 3 (invoer)
   - counter3 (int): productieteller Lijn 4 (overflow)

4. palletstatus - Palletposities op 4 stations
   - time (timestamp): meetmoment
   - pallet6000 (int): status palletstation 6000 (100=geen pallet, 200=leeg, 300=klaar)
   - pallet6005 (int): status palletstation 6005 (zelfde statuscodes)
   - pallet6010 (int): status palletstation 6010 (zelfde statuscodes)
   - pallet6015 (int): status palletstation 6015 (zelfde statuscodes)

Regels:
- Antwoord in het Nederlands
- Gebruik alleen SELECT queries
- Bij datum-vragen zonder specifieke datum: gebruik gisteren (CURRENT_DATE - 1)
- Geef concrete cijfers, geen vage antwoorden
- Bij vergelijkingen: toon altijd beide periodes
- Shift is 18 uur per dag (05:00 tot 23:00 bij benadering)
- Voeg altijd een LIMIT toe aan je queries (max 1000 rijen)"""

SQL_TOOL = {
    "type": "function",
    "function": {
        "name": "run_sql",
        "description": "Voer een read-only SQL query uit op de DGS database. Alleen SELECT is toegestaan.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "De SQL SELECT query om uit te voeren",
                }
            },
            "required": ["query"],
        },
    },
}

_COMMENT_PATTERN = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
_LIMIT_PATTERN = re.compile(r"\bLIMIT\b", re.IGNORECASE)


def _sanitize_sql(sql: str) -> str:
    """Valideer en sanitize AI-gegenereerde SQL. Gooit ValueError bij ongeldige queries."""
    stripped = _COMMENT_PATTERN.sub(" ", sql).strip()

    if not stripped.upper().startswith("SELECT"):
        raise ValueError("Alleen SELECT queries zijn toegestaan")

    forbidden = re.findall(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
        stripped,
        re.IGNORECASE,
    )
    if forbidden:
        raise ValueError(f"Niet-toegestane SQL operatie: {forbidden[0].upper()}")

    if not _LIMIT_PATTERN.search(stripped):
        stripped = stripped.rstrip(";") + " LIMIT 1000"

    return stripped


def _check_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    # Verlopen tijdstempels van alle IP's opruimen, anders blijven inactieve IP's
    # voor altijd in het geheugen staan (geheugenlek bij veel wisselende clients).
    for ip in list(_rate_limits):
        fresh = [t for t in _rate_limits[ip] if now - t < RATE_LIMIT_WINDOW]
        if fresh:
            _rate_limits[ip] = fresh
        else:
            del _rate_limits[ip]

    if len(_rate_limits[client_ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(429, "Te veel verzoeken. Probeer het over een minuut opnieuw.")
    _rate_limits[client_ip].append(now)


def _resolve_tls_verify(settings: Settings):
    """Bepaal de TLS-verify-waarde voor httpx: CA-bundle-pad, of bool.

    Default veilig (True). Een CA-bundle is de juiste oplossing achter SSL-inspectie;
    verify=False is een gedocumenteerd laatste redmiddel en logt een waarschuwing.
    """
    if settings.chat_ca_bundle:
        return settings.chat_ca_bundle
    if not settings.chat_tls_verify:
        logger.warning(
            "TLS-verificatie naar OpenRouter staat UIT (CHAT_TLS_VERIFY=false). "
            "Alleen gebruiken achter een vertrouwde proxy; liever CHAT_CA_BUNDLE zetten."
        )
        return False
    return True


async def init_chat(settings: Settings) -> None:
    global _client, _model, _chat_pool
    _model = settings.chat_model
    if settings.openrouter_api_key:
        import httpx
        _client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
            timeout=30.0,
            http_client=httpx.AsyncClient(verify=_resolve_tls_verify(settings)),
        )

    # Aparte read-only rol voor AI-gegenereerde SQL. Zonder CHAT_DB_USER valt de chat
    # terug op de hoofd-pool (zie _get_chat_connection).
    if not settings.chat_db_user:
        logger.info("CHAT_DB_USER niet gezet, chat gebruikt de hoofd-pool")
        _chat_pool = None
        return
    try:
        _chat_pool = await create_db_pool(
            settings,
            user=settings.chat_db_user,
            password=settings.chat_db_password,
            min_size=2,
            max_size=5,
        )
        logger.info("Chat read-only pool created (user=%s)", settings.chat_db_user)
    except Exception:
        logger.warning("Chat read-only pool niet beschikbaar, fallback naar hoofdpool")
        _chat_pool = None


async def close_chat_pool() -> None:
    global _chat_pool
    if _chat_pool:
        await _chat_pool.close()
        _chat_pool = None


@asynccontextmanager
async def _get_chat_connection():
    if _chat_pool:
        async with _chat_pool.acquire() as conn:
            yield conn
    else:
        async with get_connection() as conn:
            yield conn


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    sql: str | None = None
    data: list[dict] | None = None


async def _execute_query(sql: str) -> list[dict]:
    safe_sql = _sanitize_sql(sql)
    async with _get_chat_connection() as conn:
        rows = await conn.fetch(safe_sql)
        return [dict(r) for r in rows]


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    if not _client:
        raise HTTPException(503, "Chat niet beschikbaar: OPENROUTER_API_KEY niet geconfigureerd")

    if not req.message.strip():
        raise HTTPException(400, "Bericht mag niet leeg zijn")

    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # Begrens gelijktijdige LLM-conversaties; extra verzoeken wachten kort i.p.v.
    # de chat-pool (max 5) en de OpenRouter-quota te overspoelen.
    async with _llm_semaphore:
        return await _run_conversation(req.message)


async def _run_conversation(message: str) -> ChatResponse:
    messages = [
        {"role": "system", "content": SCHEMA_CONTEXT},
        {"role": "user", "content": message},
    ]

    response = await _client.chat.completions.create(
        model=_model,
        max_tokens=2048,
        tools=[SQL_TOOL],
        messages=messages,
    )

    sql_used = None
    query_data = None
    loop_count = 0

    while response.choices[0].finish_reason == "tool_calls":
        loop_count += 1
        if loop_count > MAX_TOOL_LOOPS:
            logger.warning("Chat tool-call loop limiet bereikt (%d)", MAX_TOOL_LOOPS)
            break

        assistant_msg = response.choices[0].message
        messages.append(assistant_msg)

        for tool_call in assistant_msg.tool_calls:
            if tool_call.function.name != "run_sql":
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": "Onbekende tool"}),
                })
                continue

            args = json.loads(tool_call.function.arguments)
            sql_used = args["query"]
            logger.info("Chat SQL: %s", sql_used)

            try:
                rows = await _execute_query(sql_used)
                query_data = rows[:200]
                tool_result = json.dumps(query_data, default=str, ensure_ascii=False)
            except ValueError as e:
                logger.warning("SQL geblokkeerd: %s", e)
                tool_result = json.dumps({"error": str(e)})
            except Exception:
                logger.exception("SQL execution failed")
                tool_result = json.dumps({"error": "Er ging iets mis bij het uitvoeren van de query"})

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })

        response = await _client.chat.completions.create(
            model=_model,
            max_tokens=2048,
            tools=[SQL_TOOL],
            messages=messages,
        )

    answer = response.choices[0].message.content or "Geen antwoord gegenereerd."

    return ChatResponse(answer=answer, sql=sql_used, data=query_data)
