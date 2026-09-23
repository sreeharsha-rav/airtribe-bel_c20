import os
from pathlib import Path

from dotenv import load_dotenv


class Settings:
    def __init__(self):
        load_dotenv()

        self.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
        if not self.OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY is not set. Please set it in the environment "
                "variables or in a .env file."
            )

        self.MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
        self.MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
        # The agent always talks to the host-published Docker port, regardless
        # of what MCP_HOST is bound to inside the container.
        self.MCP_SERVER_URL = f"http://localhost:{self.MCP_PORT}/mcp"

        self.ROOT_DIR = (Path(__file__).parent / os.getenv("ROOT_DIR", "sample_data/resumes")).resolve()

        self.ALLOWED_EXTENSIONS = {
            ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
            for ext in os.getenv("ALLOWED_EXTENSIONS", ".txt,.docx,.pdf").split(",")
            if ext.strip()
        }
        self.MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_BYTES", "10485760"))
        self.BATCH_MAX_CONCURRENCY = int(os.getenv("BATCH_MAX_CONCURRENCY", "4"))
        self.WATCH_POLL_INTERVAL_SECONDS = float(os.getenv("WATCH_POLL_INTERVAL_SECONDS", "5"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
