"""pacs_client.py - fetch DICOM instances from PACS via WADO-RS (портировано из старого app.py)."""

import email
import logging

import requests

from core.config import settings

logger = logging.getLogger(__name__)


class PacsFetchError(Exception):
    pass


def fetch_dicom_from_pacs(study_uid: str, series_uid: str, instance_uid: str) -> bytes:
    """Возвращает сырые байты DICOM-инстанса. Бросает PacsFetchError при неудаче."""
    url = f"{settings.PACS_BASE_URL}/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}"
    logger.info("Fetching from PACS: %s", url)

    try:
        headers = {"Accept": 'multipart/related; type="application/dicom"'}
        response = requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=(settings.PACS_TIMEOUT_CONNECT, settings.PACS_TIMEOUT_READ),
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as e:
        raise PacsFetchError("Timeout при обращении к PACS") from e
    except requests.exceptions.RequestException as e:
        raise PacsFetchError(f"Ошибка запроса к PACS: {e}") from e
    except Exception as e:
        # Подстраховка от любых непредвиденных сбоев соединения (DNS, сброс сокета и т.п.),
        # которые не являются подклассами requests.exceptions.RequestException -
        # без этого такие ошибки уходили бы наверх как 500 вместо понятного 502.
        raise PacsFetchError(f"Непредвиденная ошибка при обращении к PACS: {e}") from e

    content = response.content
    if len(content) == 0:
        raise PacsFetchError("PACS вернул 0 байт")

    content_type = response.headers.get("Content-Type", "")
    if "multipart" in content_type.lower():
        msg_data = (
            b"Content-Type: " + content_type.encode("utf-8") + b"\r\n\r\n" + content
        )
        msg = email.message_from_bytes(msg_data)
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "application/dicom":
                    return part.get_payload(decode=True)
            parts = msg.get_payload()
            if isinstance(parts, list) and len(parts) > 0:
                return parts[0].get_payload(decode=True)

    # Fallback: некоторые серверы отдают "сырой" DICOM без multipart-обёртки
    return content
