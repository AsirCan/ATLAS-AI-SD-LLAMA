"""Application-level exceptions with stable, user-safe messages."""


class AtlasError(Exception):
    """Base class for errors that can safely cross application boundaries."""

    code = "atlas_error"
    user_message = "İşlem tamamlanamadı."

    def __init__(self, detail: str | None = None):
        self.detail = detail
        super().__init__(detail or self.user_message)


class CancelledError(AtlasError):
    """Raised when a cooperative cancellation is requested."""

    code = "cancelled"
    user_message = "İşlem iptal edildi."


class LLMUnavailableError(AtlasError):
    """Raised when the local Ollama API cannot be reached or times out."""

    code = "ollama_unavailable"
    user_message = "Ollama bağlantısı kurulamadı."


class LLMResponseError(AtlasError):
    """Raised when Ollama responds but its payload cannot be used."""

    code = "ollama_invalid_response"
    user_message = "Ollama geçerli bir yanıt üretemedi."


class ServiceStartupError(AtlasError):
    """Raised when a required local service cannot be started in time."""

    code = "service_startup_failed"
    user_message = "Gerekli servis başlatılamadı."
