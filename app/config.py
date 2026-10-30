'''import os
from dotenv import load_dotenv

load_dotenv()

PARSER_PROVIDER = os.getenv(
    "PARSER_PROVIDER", "llamaparse"
).strip().lower()

PARSER_MODEL = os.getenv("PARSER_MODEL", "").strip()

MAX_FILE_SIZE_MB = int(
    os.getenv("MAX_FILE_SIZE_MB", "100")
)

LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY", "")

LLAMAPARSE_TIER = os.getenv(
    "LLAMAPARSE_TIER", "cost_effective"
)

LLAMAPARSE_VERSION = os.getenv(
    "LLAMAPARSE_VERSION", "latest"
)'''