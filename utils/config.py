import os
from pathlib import Path

from dotenv import load_dotenv
from dynaconf import Dynaconf, Validator

load_dotenv()

_UTILS_DIR = Path(__file__).parent

settings = Dynaconf(
    environments=True,
    merge_enabled=True,
    default_env="default",
    env=os.getenv("DYNACONF_ENV", "default"),
    settings_files=[str(_UTILS_DIR / "settings.toml"), str(_UTILS_DIR / ".secrets.toml")],
    obj_name_for_autocompletion="settings",
    validators=[
        Validator("llm.PROVIDER", must_exist=True, is_in=["scripted", "litellm"]),
        Validator("agentic.FREE_TEXT_CONFIDENCE_THRESHOLD", must_exist=True, gte=0, lte=1),
        Validator("agentic.RECURSION_LIMIT", must_exist=True, gt=0),
        Validator("data_platform.DUCKDB_PATH", must_exist=True),
        Validator("data_platform.LOCAL_TIMEZONE", must_exist=True),
    ],
)
