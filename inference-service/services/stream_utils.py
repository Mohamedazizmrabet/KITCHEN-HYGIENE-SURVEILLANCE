"""
services/stream_utils.py — Playwright-based stream capture utilities.

Provides two capture strategies:
  1. get_ivideon_stream_url() — sniff the HLS .m3u8 URL from network traffic.
  2. capture_embedded_player() — screenshot video element at configured FPS.

The stream_manager uses these as an automatic fallback when OpenCV cannot
open a URL (e.g. Ivideon embed pages, web-player URLs without raw streams).
"""

from __future__ import annotations

import logging
import time
import urllib.parse
from dataclasses import dataclass
from typing import Generator, Iterable

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class StreamResolutionError(RuntimeError):
    """Raised when the embed does not expose a direct playable stream."""


IVIDEON_EMBED_URL = (
    "https://open.ivideon.com/embed/v2/"
    "?server={server_id}&camera={camera_id}&lang=en"
)


def _candidate_urls(server_id: str, camera_id: int | str) -> Iterable[str]:
    embed = IVIDEON_EMBED_URL.format(server_id=server_id, camera_id=camera_id)
    yield embed


def get_ivideon_stream_url(
    server_id: str, camera_id: int | str = 0, timeout_ms: int = 15000
) -> str:
    """Try to discover an HLS URL from Ivideon embed network traffic."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    found: list[str] = []
    embed_url = next(_candidate_urls(server_id, camera_id))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        def on_response(response) -> None:
            url = response.url
            parsed = urllib.parse.urlparse(url)
            if ".m3u8" in parsed.path or ".m3u8" in parsed.query:
                found.append(url)

        page.on("response", on_response)
        page.goto(embed_url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.locator("video").first.wait_for(timeout=timeout_ms)
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(5000)
        browser.close()

    if found:
        return found[0]

    raise StreamResolutionError(
        "No direct HLS .m3u8 URL was observed. Use capture_embedded_player() instead."
    )


@dataclass
class EmbeddedCaptureConfig:
    url: str
    width: int = 1280
    height: int = 720
    fps: float = 5.0
    selector: str = "video"
    timeout_ms: int = 30000
    startup_wait_ms: int = 5000
    click_to_play: bool = True
    headless: bool = True


def _force_play_all_videos(page) -> None:
    """Force-play every <video> element found across ALL frames on the page.

    Ivideon embeds the player inside nested iframes. This function iterates
    every frame context and calls .play() + mutes each video it finds via JS,
    plus dispatches synthetic click/touch events on any visible play button.
    """
    # JS snippet: mute + play all videos, remove poster/overlay if any
    PLAY_JS = """
    () => {
        const videos = document.querySelectorAll('video');
        videos.forEach(v => {
            v.muted = true;
            v.volume = 0;
            v.autoplay = true;
            v.removeAttribute('autoplay');
            v.setAttribute('autoplay', '');
            const p = v.play();
            if (p && p.catch) p.catch(() => {});
        });

        // Click any element that looks like a play button
        const playSelectors = [
            '[class*="play"]',
            '[aria-label*="play" i]',
            'button',
            '[class*="btn"]',
            '[class*="control"]',
        ];
        playSelectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(el => {
                try { el.click(); } catch(e) {}
            });
        });
    }
    """

    # Run in the main page
    try:
        page.evaluate(PLAY_JS)
    except Exception:
        pass

    # Run in every iframe frame context
    for frame in page.frames:
        try:
            frame.evaluate(PLAY_JS)
        except Exception:
            pass

    # Also try clicking the center of the page (catches overlay play buttons)
    try:
        page.mouse.click(page.viewport_size["width"] // 2, page.viewport_size["height"] // 2)
    except Exception:
        pass


def _get_best_screenshot_target(page):
    """Return the element (or None for full page) to screenshot.

    Priority:
    1. <video> element directly in the main page
    2. <video> inside an iframe
    3. The whole iframe element
    4. None → fall back to full-page screenshot
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    # Try direct video
    try:
        v = page.locator("video").first
        v.wait_for(timeout=4000)
        return v
    except PlaywrightTimeoutError:
        pass

    # Try video inside each iframe
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            v = frame.locator("video").first
            v.wait_for(timeout=3000)
            # Get the iframe element handle in the parent page
            for iframe_el in page.locator("iframe").all():
                try:
                    cf = iframe_el.content_frame()
                    if cf and cf == frame:
                        return iframe_el  # screenshot the iframe element
                except Exception:
                    pass
            return v
        except PlaywrightTimeoutError:
            continue

    return None  # Will use full-page screenshot


def capture_embedded_player(
    config: EmbeddedCaptureConfig | str,
) -> Generator[np.ndarray, None, None]:
    """Yield BGR frames by screenshotting the embedded video player.

    Works with Ivideon embed URLs by:
    1. Launching headless Chromium with autoplay enabled
    2. Loading the embed page and waiting for the player to appear
    3. Force-playing every <video> across all iframes via JavaScript
    4. Repeatedly screenshotting the video/iframe element at `fps`

    Yields numpy BGR frames suitable for OpenCV / YOLO inference.
    """
    from playwright.sync_api import sync_playwright

    if isinstance(config, str):
        config = EmbeddedCaptureConfig(url=config)

    delay = 1.0 / max(config.fps, 0.1)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=config.headless,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--mute-audio",
            ],
        )
        context = browser.new_context(
            viewport={"width": config.width, "height": config.height},
            # Pretend to be a real browser to avoid bot detection
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        logger.info(f"[stream_utils] Loading URL: {config.url}")
        page.goto(config.url, wait_until="domcontentloaded", timeout=config.timeout_ms)

        # Give the page time to initialise its JS player
        page.wait_for_timeout(3000)

        # Aggressively force-play everything
        for attempt in range(5):
            _force_play_all_videos(page)
            page.wait_for_timeout(1000)

        # Wait for configured startup time
        page.wait_for_timeout(config.startup_wait_ms)

        # Determine what to screenshot
        target = _get_best_screenshot_target(page)
        logger.info(f"[stream_utils] Screenshot target: {type(target).__name__ if target else 'full-page'}")

        consecutive_errors = 0
        while True:
            try:
                if target is not None:
                    try:
                        png = target.screenshot(type="png")
                    except Exception:
                        # Target may have detached — fall back to full page
                        png = page.screenshot(type="png")
                else:
                    png = page.screenshot(type="png")

                frame = cv2.imdecode(
                    np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR
                )
                if frame is not None:
                    consecutive_errors = 0
                    yield frame
                else:
                    consecutive_errors += 1

            except Exception as exc:
                logger.warning(f"[stream_utils] Screenshot error: {exc}")
                consecutive_errors += 1
                # Retry force-play periodically
                if consecutive_errors % 5 == 0:
                    _force_play_all_videos(page)

            if consecutive_errors > 30:
                logger.error("[stream_utils] Too many consecutive errors, stopping capture.")
                break

            time.sleep(delay)

        browser.close()


def is_browser_url(source: str) -> bool:
    """Return True if the source is a browser-embed URL that OpenCV cannot open."""
    BROWSER_INDICATORS = [
        "open.ivideon.com/embed",
        "public.ivideon.com",
        "embed/v2",
        "embed/v3",
    ]
    return any(indicator in source for indicator in BROWSER_INDICATORS)
