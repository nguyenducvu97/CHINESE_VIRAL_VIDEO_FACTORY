"""Custom exception classes for CHINESE_VIRAL_VIDEO_FACTORY."""

class CVVFError(Exception):
    """Base exception for all CVVF errors."""
    pass


class DiscoveryError(CVVFError):
    """Base error occurred during video discovery."""
    pass


class RateLimitExceededError(DiscoveryError):
    """Raised when request rate exceeds configured thresholds."""
    pass


class SourceBlockedError(DiscoveryError):
    """Raised when an external source blocks or challenges requests (anti-crawler, -352, 403)."""
    pass


class InvalidResponseError(DiscoveryError):
    """Raised when source response is malformed or invalid."""
    pass


class DuplicateItemError(CVVFError):
    """Raised when duplicate video item cannot be processed."""
    pass
