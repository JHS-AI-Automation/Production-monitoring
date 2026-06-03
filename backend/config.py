import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    app_port: int
    app_host: str
    openrouter_api_key: str
    chat_model: str
    # Aparte read-only rol voor de AI-chat. Valt terug op de hoofd-credentials
    # als ze niet zijn gezet (dan deelt de chat de hoofd-pool).
    chat_db_user: str
    chat_db_password: str
    # TLS naar OpenRouter. Default veilig (verify=True). Achter SSL-inspectie/proxy
    # kan een CA-bundle-pad worden gezet (aanbevolen) of, als laatste redmiddel,
    # verificatie worden uitgezet via CHAT_TLS_VERIFY=false.
    chat_tls_verify: bool
    chat_ca_bundle: str

    @classmethod
    def from_env(cls) -> "Settings":
        missing = [v for v in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not os.environ.get(v)]
        if missing:
            print(f"FOUT: Verplichte environment variabelen ontbreken: {', '.join(missing)}", file=sys.stderr)
            print("Kopieer .env.example naar .env en vul de waardes in.", file=sys.stderr)
            sys.exit(1)

        return cls(
            db_host=os.environ["DB_HOST"],
            db_port=int(os.environ.get("DB_PORT", "5432")),
            db_name=os.environ["DB_NAME"],
            db_user=os.environ["DB_USER"],
            db_password=os.environ["DB_PASSWORD"],
            app_port=int(os.environ.get("APP_PORT", "8080")),
            app_host=os.environ.get("APP_HOST", "0.0.0.0"),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            chat_model=os.environ.get("CHAT_MODEL", "anthropic/claude-sonnet-4"),
            chat_db_user=os.environ.get("CHAT_DB_USER", ""),
            chat_db_password=os.environ.get("CHAT_DB_PASSWORD", ""),
            chat_tls_verify=os.environ.get("CHAT_TLS_VERIFY", "true").lower() != "false",
            chat_ca_bundle=os.environ.get("CHAT_CA_BUNDLE", ""),
        )
