import html
import json
import re
from dataclasses import dataclass
from typing import Any

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


def _extract_script_contents(body: str, attrs_pattern: str) -> list[str]:
    pattern = re.compile(
        rf"<script[^>]*{attrs_pattern}[^>]*>(.*?)</script>",
        re.IGNORECASE | re.DOTALL,
    )
    return [match.group(1).strip() for match in pattern.finditer(body) if match.group(1).strip()]


def _extract_assignment_values(body: str, variable_names: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for variable_name in variable_names:
        pattern = re.compile(
            rf"{re.escape(variable_name)}\s*=\s*(\{{.*?\}}|\[.*?\])\s*;",
            re.DOTALL,
        )
        values.extend(match.group(1).strip() for match in pattern.finditer(body))
    return values


def _parse_json_blob(blob: str) -> Any | None:
    text = html.unescape(blob).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _collect_top_level_keys(payload: Any) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()

    def add_keys(obj: Any) -> None:
        if isinstance(obj, dict):
            for key in obj.keys():
                key_text = str(key)
                if key_text not in seen:
                    seen.add(key_text)
                    keys.append(key_text)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    for key in item.keys():
                        key_text = str(key)
                        if key_text not in seen:
                            seen.add(key_text)
                            keys.append(key_text)

    add_keys(payload)
    return keys


def _format_keys_summary(keys: list[str]) -> str:
    if not keys:
        return ""
    visible = keys[:7]
    remainder = len(keys) - len(visible)
    summary = ", ".join(visible)
    if remainder > 0:
        summary += f" + {remainder} more"
    return summary


def _extract_json_ld_keys(body: str) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for content in _extract_script_contents(body, r'type=["\']application/ld\+json["\']'):
        payload = _parse_json_blob(content)
        if payload is None:
            continue
        for key in _collect_top_level_keys(payload):
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def _extract_nextjs_keys(body: str) -> list[str]:
    contents = _extract_script_contents(body, r'id=["\']__NEXT_DATA__["\']')
    for content in contents:
        payload = _parse_json_blob(content)
        if payload is not None:
            return _collect_top_level_keys(payload)
    return []


def _extract_nuxt_keys(body: str) -> list[str]:
    contents = _extract_script_contents(body, r'data-nuxt-data')
    for content in contents:
        payload = _parse_json_blob(content)
        if payload is not None:
            return _collect_top_level_keys(payload)

    for blob in _extract_assignment_values(body, ("window.__NUXT__", "__NUXT__")):
        payload = _parse_json_blob(blob)
        if payload is not None:
            return _collect_top_level_keys(payload)
    return []


def _extract_apollo_or_relay_keys(body: str) -> list[str]:
    for blob in _extract_assignment_values(
        body, ("window.__APOLLO_STATE__", "__APOLLO_STATE__", "__RELAY_PAYLOADS__")
    ):
        payload = _parse_json_blob(blob)
        if payload is not None:
            return _collect_top_level_keys(payload)
    return []


def _extract_bootstrapped_state_keys(body: str) -> list[str]:
    for blob in _extract_assignment_values(
        body, ("window.__INITIAL_STATE__", "__INITIAL_STATE__", "window.__PRELOADED_STATE__", "__PRELOADED_STATE__")
    ):
        payload = _parse_json_blob(blob)
        if payload is not None:
            return _collect_top_level_keys(payload)
    return []


def detect_scrapable_patterns(
    plain: PlainResult | None, tls: TlsResult | None
) -> tuple[list[ScrapablePatternResult], str]:
    body, source = _pick_body(plain, tls)
    extracted_keys = {
        "JSON-LD": _extract_json_ld_keys(body),
        "Next.js hydration": _extract_nextjs_keys(body),
        "Nuxt payload": _extract_nuxt_keys(body),
        "Apollo/Relay cache": _extract_apollo_or_relay_keys(body),
        "Bootstrapped app state": _extract_bootstrapped_state_keys(body),
    }

    results: list[ScrapablePatternResult] = []
    for definition in PATTERN_DEFINITIONS:
        detected = any(re.search(regex, body, re.IGNORECASE) for regex in definition.regexes)
        keys_summary = _format_keys_summary(extracted_keys.get(definition.name, []))
        results.append(
            ScrapablePatternResult(
                name=definition.name,
                detected=detected,
                signal=definition.signal,
                extraction_hint=definition.extraction_hint,
                keys_summary=keys_summary,
            )
        )

    return results, source
