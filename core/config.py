import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv()


def _get_list(env_name: str, default: list[str]) -> list[str]:
    raw = os.getenv(env_name)
    if not raw:
        return default
    return [x.strip() for x in raw.split(",") if x.strip()]


class Settings:
    # --- модель ---
    MODEL_SIGNAL_PATH: str = str(BASE_DIR / "weights" / "ecg_signal" / "best.pth")
    THRESHOLDS_SIGNAL_PATH: str = str(
        BASE_DIR / "weights" / "ecg_signal" / "thresholds.json"
    )
    SUPERCLASSES: list[str] = _get_list(
        "SUPERCLASSES", ["NORM", "MI", "CD", "HYP", "STTC"]
    )
    NUM_LEAD: int = int(os.getenv("NUM_LEAD", "12"))
    DEVICE: str = os.getenv(
        "DEVICE", "cuda" if os.getenv("USE_GPU", "1") == "1" else "cpu"
    )

    # --- исходная (не дообученная) ECGFounder, 150 классов претрейна ---
    MODEL_150_PATH: str = str(
        BASE_DIR / "weights" / "ecg_founder_150" / "12_lead_ECGFounder.pth"
    )
    CLASS_NAMES_150_PATH: str = str(
        BASE_DIR / "weights" / "ecg_founder_150" / "tasks.txt"
    )
    NUM_CLASSES_150: int = int(os.getenv("NUM_CLASSES_150", "150"))
    TOP_K_150: int = int(os.getenv("TOP_K_150", "10"))

    # --- препроцессинг сигнала (должно совпадать с тем, на чём обучалась модель!) ---
    TARGET_FS: int = int(os.getenv("TARGET_FS", "500"))
    TARGET_DURATION_SEC: float = float(os.getenv("TARGET_DURATION_SEC", "10.0"))

    # --- PACS ---
    PACS_BASE_URL: str = os.getenv(
        "PACS_BASE_URL", "http://195.158.10.39:8080/dcm4chee-arc/aets/DCM4CHEE/rs"
    )
    PACS_TIMEOUT_CONNECT: float = float(os.getenv("PACS_TIMEOUT_CONNECT", "5"))
    PACS_TIMEOUT_READ: float = float(os.getenv("PACS_TIMEOUT_READ", "30"))

    # --- WFDB (локальные записи, напр. для внутреннего тестирования на PTB-XL) ---
    WFDB_ROOT: str = os.getenv("WFDB_ROOT", "./wfdb_data")

    # --- логирование в файл (WARNING+, для /logs/download) ---
    LOG_DIR: str = str(BASE_DIR / "logs")
    LOG_FILE_NAME: str = "app.log"
    LOG_FILE_MAX_BYTES: int = int(
        os.getenv("LOG_FILE_MAX_BYTES", str(10 * 1024 * 1024))
    )  # 10 МБ на файл
    LOG_FILE_BACKUP_COUNT: int = int(
        os.getenv("LOG_FILE_BACKUP_COUNT", "5")
    )  # + 5 архивных ротаций

    # --- сервис ---
    PORT: int = int(os.getenv("PORT", "8000"))
    ENV: str = os.getenv("APP_ENV", "development")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()

TARGET_LEN = int(settings.TARGET_FS * settings.TARGET_DURATION_SEC)
LOG_FILE_PATH = os.path.join(settings.LOG_DIR, settings.LOG_FILE_NAME)
