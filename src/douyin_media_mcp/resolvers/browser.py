from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Response,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from ..candidates import candidate_from_response, deduplicate_candidates
from ..config import Settings
from ..errors import MediaMCPError, safe_error
from ..models import MediaCandidate, ResolvedMedia


class BrowserResolver:
    """Resolve signed media streams by observing a real Chromium page."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def resolve(self, canonical_url: str, aweme_id: str) -> ResolvedMedia:
        candidates: list[MediaCandidate] = []
        tasks: set[asyncio.Task[None]] = set()

        async def capture(response: Response) -> None:
            try:
                headers: dict[str, str] = {}
                request_headers: dict[str, str] = {}
                with suppress(Exception):
                    headers = await response.all_headers()
                with suppress(Exception):
                    request_headers = await response.request.all_headers()
                candidate = candidate_from_response(
                    response.url,
                    content_type=headers.get("content-type"),
                    content_length=headers.get("content-length"),
                    content_range=headers.get("content-range"),
                    request_headers=request_headers,
                )
                if candidate:
                    candidates.append(candidate)
            except Exception:
                # Individual responses can disappear while the page navigates.
                return

        async with async_playwright() as playwright:
            browser: Browser | None = None
            context: BrowserContext | None = None
            page: Page | None = None
            owns_context = False
            owns_browser = False
            try:
                browser, context, owns_browser, owns_context = await self._open_context(playwright)
                page = await context.new_page()

                def on_response(response: Response) -> None:
                    task = asyncio.create_task(capture(response))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)

                page.on("response", on_response)
                # A playable page may keep long-lived requests open; continue observing.
                with suppress(PlaywrightTimeoutError):
                    await page.goto(
                        canonical_url,
                        wait_until="domcontentloaded",
                        timeout=int(self.settings.browser_timeout_seconds * 1000),
                    )

                await self._encourage_playback(page)
                deadline = asyncio.get_running_loop().time() + self.settings.browser_timeout_seconds
                video_found_at: float | None = None
                while asyncio.get_running_loop().time() < deadline:
                    kinds = {item.kind for item in candidates}
                    if "video" in kinds:
                        video_found_at = video_found_at or asyncio.get_running_loop().time()
                        elapsed = asyncio.get_running_loop().time() - video_found_at
                        if elapsed >= self.settings.browser_settle_seconds:
                            break
                    await asyncio.sleep(0.25)

                performance_urls = await self._performance_urls(page)
                for url in performance_urls:
                    candidate = candidate_from_response(url, content_type=None)
                    if candidate:
                        candidates.append(candidate)

                if tasks:
                    await asyncio.gather(*list(tasks), return_exceptions=True)
                candidates = deduplicate_candidates(candidates)
                candidates = await self._inject_download_headers(
                    context, page, canonical_url, candidates
                )
                metadata = await self._metadata(page)

                if not candidates:
                    page_text = (await page.locator("body").inner_text(timeout=3000)).lower()
                    challenge_tokens = ("验证码", "扫码登录", "登录后", "verify")
                    if any(token in page_text for token in challenge_tokens):
                        raise MediaMCPError(
                            "HUMAN_ACTION_REQUIRED",
                            "页面要求登录或人工验证；服务不会自动绕过。",
                        )
                    raise MediaMCPError(
                        "RESOLVER_CHANGED",
                        "作品页已打开，但没有捕获到可识别的媒体网络响应。",
                        retryable=True,
                    )
                return ResolvedMedia(
                    canonical_url=canonical_url,
                    aweme_id=aweme_id,
                    title=metadata.get("title"),
                    duration_seconds=metadata.get("duration_seconds"),
                    candidates=candidates,
                    resolver_used="playwright_cdp" if self.settings.cdp_url else "playwright",
                    warnings=[],
                )
            except MediaMCPError:
                raise
            except Exception as exc:
                raise safe_error(exc) from exc
            finally:
                if page is not None:
                    with suppress(Exception):
                        await page.close()
                if owns_context and context is not None:
                    with suppress(Exception):
                        await context.close()
                if owns_browser and browser is not None:
                    with suppress(Exception):
                        await browser.close()

    async def _open_context(
        self, playwright: Any
    ) -> tuple[Browser | None, BrowserContext, bool, bool]:
        if self.settings.cdp_url:
            browser = await playwright.chromium.connect_over_cdp(self.settings.cdp_url)
            if not browser.contexts:
                raise MediaMCPError(
                    "HUMAN_ACTION_REQUIRED",
                    "CDP 浏览器没有可用上下文，请先启动带远程调试的 Chromium。",
                )
            return browser, browser.contexts[0], False, False

        launch_options: dict[str, Any] = {"headless": self.settings.browser_headless}
        if self.settings.browser_channel:
            launch_options["channel"] = self.settings.browser_channel
        if self.settings.browser_profile_dir:
            self.settings.browser_profile_dir.mkdir(parents=True, exist_ok=True)
            context = await playwright.chromium.launch_persistent_context(
                str(self.settings.browser_profile_dir), **launch_options
            )
            return None, context, False, True
        browser = await playwright.chromium.launch(**launch_options)
        context = await browser.new_context(locale="zh-CN")
        return browser, context, True, True

    async def _inject_download_headers(
        self,
        context: BrowserContext,
        page: Page,
        canonical_url: str,
        candidates: list[MediaCandidate],
    ) -> list[MediaCandidate]:
        user_agent = await page.evaluate("navigator.userAgent")
        cookie_header: str | None = None
        if self.settings.use_browser_cookies:
            cookies = await context.cookies([canonical_url])
            cookie_header = "; ".join(
                f"{cookie['name']}={cookie['value']}" for cookie in cookies if cookie.get("name")
            )
        enriched: list[MediaCandidate] = []
        for candidate in candidates:
            headers = dict(candidate.request_headers)
            headers["User-Agent"] = user_agent
            headers["Referer"] = canonical_url
            if cookie_header:
                headers["Cookie"] = cookie_header
            elif not self.settings.use_browser_cookies:
                headers.pop("cookie", None)
                headers.pop("Cookie", None)
            enriched.append(
                MediaCandidate(
                    kind=candidate.kind,
                    url=candidate.url,
                    mime_type=candidate.mime_type,
                    width=candidate.width,
                    height=candidate.height,
                    bitrate=candidate.bitrate,
                    content_length=candidate.content_length,
                    request_headers=headers,
                )
            )
        return enriched

    @staticmethod
    async def _encourage_playback(page: Page) -> None:
        with suppress(Exception):
            await page.evaluate(
                """
                () => {
                  for (const video of document.querySelectorAll('video')) {
                    video.muted = true;
                    const result = video.play();
                    if (result && result.catch) result.catch(() => {});
                  }
                }
                """
            )

    @staticmethod
    async def _performance_urls(page: Page) -> list[str]:
        with suppress(Exception):
            values = await page.evaluate(
                "performance.getEntriesByType('resource').map(item => item.name)"
            )
            return [str(value) for value in values if isinstance(value, str)]
        return []

    @staticmethod
    async def _metadata(page: Page) -> dict[str, Any]:
        title: str | None = None
        duration: float | None = None
        with suppress(Exception):
            title = (await page.title()).strip() or None
        with suppress(Exception):
            raw_duration = await page.evaluate(
                """
                () => {
                  const values = [...document.querySelectorAll('video')]
                    .map(video => Number(video.duration))
                    .filter(value => Number.isFinite(value) && value > 0);
                  return values.length ? Math.max(...values) : null;
                }
                """
            )
            if raw_duration:
                duration = float(raw_duration)
        return {"title": title, "duration_seconds": duration}
