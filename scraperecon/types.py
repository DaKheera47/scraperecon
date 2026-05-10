from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class Verdict(Enum):
    OPEN = "Open"
    BLOCKED = "Blocked"
    CHALLENGED = "Challenged"
    REDIRECTED = "Redirected"
    UNCERTAIN = "Uncertain"
    SKIPPED = "Skipped"
    ERROR = "Error"

class Confidence(Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class BlockType(Enum):
    HARD_BLOCK = "HardBlock"
    RATE_LIMITED = "RateLimited"
    SOFT_REDIRECT = "SoftRedirect"
    SILENT = "Silent"

@dataclass
class RobotsResult:
    blocked: bool
    robots_url: str
    sitemap_url_count: int = 0
    sitemaps_checked: int = 0
    sitemap_sources: list[str] = field(default_factory=list)
    error: Optional[str] = None

@dataclass
class PlainResult:
    verdict: Verdict
    status: Optional[int]
    response_time_ms: int
    headers: dict[str, str]
    cookies: list[str]
    body_preview: str
    final_url: str
    full_body: str = ""
    error: Optional[str] = None

@dataclass
class TlsResult:
    verdict: Verdict
    status: Optional[int]
    response_time_ms: int
    headers: dict[str, str]
    cookies: list[str]
    body_preview: str
    tls_was_blocker: bool
    profile_used: str
    full_body: str = ""
    error: Optional[str] = None

@dataclass
class VendorResult:
    vendor: Optional[str]
    confidence: Optional[Confidence]
    matched_signals: list[str]
    all_scores: list[tuple[str, float]]

@dataclass
class RateLimitResult:
    total_requests: int
    successful: int
    blocked: int
    block_type: Optional[BlockType]
    estimated_safe_rps: Optional[float]
    retry_after_secs: Optional[int]
    median_response_ms: int

@dataclass
class Recommendation:
    use_tls_impersonation: bool
    profile: Optional[str]
    captcha_detected: bool
    proxy_recommended: bool
    notes: list[str] = field(default_factory=list)

@dataclass
class ReconReport:
    target: str
    robots: Optional[RobotsResult]
    plain: Optional[PlainResult]
    tls: Optional[TlsResult]
    vendor: Optional[VendorResult]
    rate_limit: Optional[RateLimitResult]
    recommendation: Recommendation
