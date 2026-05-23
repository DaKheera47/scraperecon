import re
from dataclasses import dataclass

from .types import PlainResult, ScrapablePatternResult, TlsResult, Verdict


@dataclass(frozen=True)
class PatternDefinition:
    name: str
    signal: str
    extraction_hint: str
    regexes: tuple[str, ...]


PATTERN_DEFINITIONS: tuple[PatternDefinition, ...] = (
    PatternDefinition(
        name="JSON-LD",
        signal='script[type="application/ld+json"]',
        extraction_hint="Parse schema payloads for product, article, job, or org fields.",
        regexes=(r'<script[^>]+type=["\']application/ld\+json["\']',),
    ),
    PatternDefinition(
        name="Next.js hydration",
        signal='script#__NEXT_DATA__',
        extraction_hint="Read props/pageProps from the Next.js bootstrap JSON.",
        regexes=(r'id=["\']__NEXT_DATA__["\']',),
    ),
    PatternDefinition(
        name="Nuxt payload",
        signal="window.__NUXT__ or data-nuxt-data",
        extraction_hint="Inspect the Nuxt payload for server-rendered entities and route data.",
        regexes=(r"__NUXT__\s*=", r"data-nuxt-data"),
    ),
    PatternDefinition(
        name="Apollo/Relay cache",
        signal="window.__APOLLO_STATE__ or __RELAY_PAYLOADS__",
        extraction_hint="Extract normalized GraphQL entities from the hydrated client cache.",
        regexes=(r"__APOLLO_STATE__\s*=", r"__RELAY_PAYLOADS__\s*="),
    ),
    PatternDefinition(
        name="Bootstrapped app state",
        signal="window.__INITIAL_STATE__ or __PRELOADED_STATE__",
        extraction_hint="Mine the initial Redux-style store for records already sent to the client.",
        regexes=(r"__INITIAL_STATE__\s*=", r"__PRELOADED_STATE__\s*="),
    ),
)


def _pick_body(plain: PlainResult | None, tls: TlsResult | None) -> tuple[str, str]:
    if tls and tls.verdict not in (Verdict.SKIPPED, Verdict.ERROR) and tls.full_body:
        return tls.full_body, f"Stage 2 ({tls.profile_used})"
    if plain and plain.verdict != Verdict.ERROR and plain.full_body:
        return plain.full_body, "Stage 1"
    return "", "Unavailable"


def detect_scrapable_patterns(
    plain: PlainResult | None, tls: TlsResult | None
) -> tuple[list[ScrapablePatternResult], str]:
    body, source = _pick_body(plain, tls)
    results: list[ScrapablePatternResult] = []

    for definition in PATTERN_DEFINITIONS:
        detected = any(re.search(regex, body, re.IGNORECASE) for regex in definition.regexes)
        results.append(
            ScrapablePatternResult(
                name=definition.name,
                detected=detected,
                signal=definition.signal,
                extraction_hint=definition.extraction_hint,
            )
        )

    return results, source
