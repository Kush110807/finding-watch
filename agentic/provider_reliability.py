"""Process-local Gemini request pacing and bounded, redacted retry policy.

A rate limiter here is NOT a quota counter: it cannot see other processes,
other apps, project-wide token usage or remaining daily requests.
"""
from __future__ import annotations

import math
import os
import random
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from collections.abc import Mapping


def _number_setting(name, default, low, high):
    try:
        value = float(os.getenv(name, str(default)))
        if not math.isfinite(value) or not low <= value <= high:
            return default
        return value
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class RetryPolicy:
    interval: float = 13.0  # conservative pacing for a stated 5 RPM allowance
    attempts: int = 3        # first attempt inclusive; 429 gets at most one retry
    max_requests_per_analysis: int = 6  # includes retries over every agent round
    request_budget: float = 95.0
    analysis_budget: float = 180.0
    timeout_ms: int = 30000
    backoff_initial: float = 2.0
    backoff_cap: float = 30.0

    @classmethod
    def from_environment(cls):
        return cls(
            interval=_number_setting('FW_GEMINI_INTERVAL_SECONDS', 13, 12, 60),
            attempts=int(_number_setting('FW_GEMINI_ATTEMPTS', 3, 1, 4)),
            max_requests_per_analysis=int(_number_setting('FW_GEMINI_MAX_REQUESTS_PER_ANALYSIS', 6, 1, 12)),
            request_budget=_number_setting('FW_GEMINI_REQUEST_BUDGET_SECONDS', 95, 15, 180),
            analysis_budget=_number_setting('FW_GEMINI_ANALYSIS_BUDGET_SECONDS', 180, 30, 300),
            timeout_ms=int(_number_setting('FW_GEMINI_TIMEOUT_MS', 30000, 5000, 90000)),
        )


class RequestPacer:
    """Reserve spaced request start times atomically; sleep WITHOUT holding lock."""
    def __init__(self, *, clock=time.monotonic, sleep=time.sleep):
        self.clock, self.sleep = clock, sleep
        self._lock = threading.Lock()
        self._next = 0.0

    def acquire(self, interval, deadline, notify=None, attempt=1):
        with self._lock:
            now = self.clock()
            target = max(now, self._next)
            if target >= deadline:
                return False
            self._next = target + interval
        wait = max(0.0, target - self.clock())
        if wait:
            if notify:
                notify({'event':'waiting', 'seconds':round(wait, 1), 'attempt':attempt})
            self.sleep(wait)
        return self.clock() < deadline


PROCESS_PACER = RequestPacer()


def _status_code(exc):
    code = getattr(exc, 'code', None)
    if code is None:
        code = getattr(exc, 'status_code', None)
    if code is None:
        code = getattr(getattr(exc, 'response', None), 'status_code', None)
    try:
        result = int(code)
        return result if 100 <= result <= 599 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _provider_details(exc):
    """Inspect only structured quota and retry fields. Never return raw payloads."""
    obj = getattr(exc, 'details', None)
    if not isinstance(obj, Mapping):
        return []
    root = obj.get('error', obj)
    if not isinstance(root, Mapping):
        return []
    details = root.get('details', [])
    return details if isinstance(details, list) else []


def _daily_quota(exc):
    for item in _provider_details(exc):
        if not isinstance(item, Mapping) or 'QuotaFailure' not in str(item.get('@type', '')):
            continue
        violations = item.get('violations')
        if not isinstance(violations, list):
            continue
        for violation in violations:
            if not isinstance(violation, Mapping):
                continue
            text = ' '.join(str(violation.get(k, '')) for k in ('quotaId', 'quotaMetric')).lower()
            if any(term in text for term in ('perday', 'per_day', 'daily', 'requests_per_day')):
                return True
    return False


def _retry_delay(exc, wall_time=time.time):
    candidates = []
    for item in _provider_details(exc):
        if not isinstance(item, Mapping) or 'RetryInfo' not in str(item.get('@type', '')):
            continue
        value = item.get('retryDelay')
        if isinstance(value, str):
            match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)s', value.strip())
            if match:
                candidates.append(float(match.group(1)))
    response = getattr(exc, 'response', None)
    headers = getattr(response, 'headers', None)
    if isinstance(headers, Mapping):
        value = next((v for k, v in headers.items() if str(k).lower() == 'retry-after'), None)
        if value is not None:
            try:
                seconds = float(value)
                if math.isfinite(seconds) and seconds >= 0:
                    candidates.append(seconds)
            except (ValueError, TypeError):
                try:
                    date = parsedate_to_datetime(str(value))
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=timezone.utc)
                    candidates.append(max(0.0, date.timestamp() - wall_time()))
                except (ValueError, TypeError, OverflowError):
                    pass
    return max(candidates) if candidates else None


def _transport_failure(exc):
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    try:
        import httpx
        return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))
    except ImportError:
        return False


def classify(exc):
    code = _status_code(exc)
    daily = code == 429 and _daily_quota(exc)
    if code == 400:
        category = 'invalid_request'
    elif code == 401:
        category = 'authentication'
    elif code == 403:
        category = 'permission'
    elif code == 404:
        category = 'unsupported_model'
    elif code == 429:
        category = 'daily_quota' if daily else 'rate_limit_or_quota'
    elif code in (408, 500, 502, 503, 504):
        category = 'provider_transient'
    elif _transport_failure(exc) and code is None:
        category = 'transport_timeout_or_connection'
    else:
        category = 'other_failure'
    return category, code, category in ('rate_limit_or_quota', 'provider_transient', 'transport_timeout_or_connection')


MESSAGES = {
    'invalid_request':'Gemini rejected this request (400). Check its model and tool compatibility; retrying unchanged will not help.',
    'authentication':'Gemini authentication failed (401). Check private API configuration.',
    'permission':'Gemini access was denied (403). Check account permissions and availability.',
    'unsupported_model':'The selected Gemini model is not available (404). Check the configured model.',
    'daily_quota':'Gemini reported that a daily request quota was exhausted (429). Automatic retries stopped; check AI Studio quota.',
    'rate_limit_or_quota':'Quota or rate limit (429) from Gemini. Automatic attempts are limited; check usage before trying again.',
    'provider_transient':'Gemini returned a temporary service or gateway error. Please try again later.',
    'transport_timeout_or_connection':'The connection to Gemini timed out or failed. Check the network and try again.',
    'other_failure':'Gemini could not complete the request. Check your connection and provider configuration.',
    'time_budget':'The Gemini request exceeded the app’s bounded waiting budget. Use local analysis or retry later.',
    'analysis_request_limit':'The Gemini analysis reached its request safety limit. Ask a narrower question or use local analysis.',
}


class ProviderFailure(Exception):
    def __init__(self, category, status, attempts, elapsed, partial=False):
        self.category = category
        self.status = status
        self.attempts = attempts
        self.elapsed = round(max(0.0, elapsed), 2)
        self.partial = partial
        super().__init__(MESSAGES.get(category, MESSAGES['other_failure']))

    def diagnostic(self):
        return {'category':self.category, 'http_status':self.status,
                'attempts':self.attempts, 'elapsed_seconds':self.elapsed,
                'partial_tools_completed':self.partial}


def invoke_with_retries(request, *, policy=None, pacer=None, clock=time.monotonic,
                        sleep=time.sleep, random_float=random.random, notify=None,
                        analysis_deadline=None, wall_time=time.time, request_guard=None):
    """Only repeat the failed provider HTTP request, never Python tool execution."""
    policy = policy or RetryPolicy.from_environment()
    pacer = pacer or PROCESS_PACER
    start = clock()
    deadline = min(start + policy.request_budget, analysis_deadline or float('inf'))
    attempts = 0
    last_category, last_code = 'time_budget', None
    while attempts < policy.attempts:
        if clock() >= deadline:
            break
        if not pacer.acquire(policy.interval, deadline, notify=notify, attempt=attempts+1):
            last_category = 'time_budget'
            break
        if request_guard is not None and not request_guard():
            raise ProviderFailure('analysis_request_limit', None, attempts, clock()-start)
        attempts += 1
        try:
            result = request()
        except Exception as exc:
            category, code, transient = classify(exc)
            last_category, last_code = category, code
            if not transient or attempts >= policy.attempts or (code == 429 and attempts >= 2):
                raise ProviderFailure(category, code, attempts, clock()-start) from None
            guidance = _retry_delay(exc, wall_time)
            # Treat Retry-After as a minimum. Never retry earlier than guidance
            # when it exceeds the app's finite wait/budget caps.
            base = min(policy.backoff_cap, policy.backoff_initial * (2 ** (attempts-1)))
            backoff = base * (0.75 + 0.5 * random_float())
            wait = max(backoff, guidance or 0.0)
            if wait > policy.backoff_cap or clock()+wait >= deadline:
                raise ProviderFailure(category, code, attempts, clock()-start) from None
            if notify:
                notify({'event':'retrying', 'seconds':round(wait,1), 'attempt':attempts+1,
                        'category':category, 'http_status':code})
            sleep(wait)
            continue
        # A successful provider response after the budget is not promoted to an
        # accepted result. Synchronous SDK calls may exceed the deadline by up
        # to one configured HTTP timeout; they cannot be interrupted safely.
        if clock() >= deadline:
            raise ProviderFailure('time_budget', None, attempts, clock()-start)
        return result
    raise ProviderFailure(last_category, last_code, attempts, clock()-start)
