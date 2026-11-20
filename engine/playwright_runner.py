"""Bounded Playwright scenario runner. Failures are explicit evidence, not successes."""

import json
import os
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .desktop import SECRET, redact

ALLOWED_ACTIONS = {"click", "fill", "select", "check", "uncheck", "press"}


def validate_scenarios(scenarios):
    if not isinstance(scenarios, list) or not scenarios or len(scenarios) > 500:
        raise ValueError("expected 1..500 browser scenarios")
    seen = set()
    for scenario in scenarios:
        sid = scenario.get("id")
        if not isinstance(sid, str) or not sid or sid in seen:
            raise ValueError("scenario ids must be unique and nonempty")
        seen.add(sid)
        path = scenario.get("path", "/")
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or "\\" in path:
            raise ValueError("scenario path must be a relative root path")
        if len(scenario.get("steps", [])) > 100:
            raise ValueError("too many browser steps")
        for step in scenario.get("steps", []):
            if (
                step.get("action") not in ALLOWED_ACTIONS
                or not isinstance(step.get("selector"), str)
                or not step["selector"]
                or SECRET.search(step["selector"])
            ):
                raise ValueError("invalid browser step")
            if step["action"] in ("fill", "select", "press") and not isinstance(step.get("value"), str):
                raise ValueError("browser step requires string value")
        for selector in scenario.get("observe", {}).values():
            if not isinstance(selector, str) or not selector or SECRET.search(selector):
                raise ValueError("observation selector required")
    return True


def loopback_origin(base_url):
    parsed = urlparse(base_url)
    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
        or parsed.username
        or parsed.password
    ):
        raise ValueError("browser replay requires a loopback origin without credentials")
    return f"{parsed.scheme}://{parsed.netloc}"


def observation(element):
    if element.evaluate("(node) => node.type === 'password'"):
        return "[redacted]"
    if element.evaluate(
        "(node) => 'value' in node && node.matches('input:not([type=checkbox]), textarea, select')"
    ):
        return redact(element.input_value())
    if element.evaluate("(node) => node.type === 'checkbox'"):
        return str(element.is_checked()).lower()
    return redact(element.inner_text())


def run_scenarios(scenario_file, base_url, output_file, *, timeout_ms=10000, screenshots=False):
    from playwright.sync_api import Error, sync_playwright

    scenarios = json.loads(Path(scenario_file).read_text(encoding="utf-8"))
    validate_scenarios(scenarios)
    origin = loopback_origin(base_url)
    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    results = {}
    with sync_playwright() as p:
        channel = os.environ.get("TWIN_BROWSER_CHANNEL")
        browser = p.chromium.launch(headless=True, **({"channel": channel} if channel else {}))
        try:
            for index, scenario in enumerate(scenarios):
                page = browser.new_page(service_workers="block")
                page.context.route(
                    "**/*",
                    lambda route: (
                        route.continue_() if route.request.url.startswith(origin + "/") else route.abort()
                    ),
                )
                page.context.route_web_socket("**/*", lambda socket: socket.close())
                try:
                    target = urljoin(base_url.rstrip("/") + "/", scenario["path"].lstrip("/"))
                    if loopback_origin(target) != origin:
                        raise ValueError("cross-origin navigation blocked")
                    page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
                    page.set_default_timeout(timeout_ms)
                    for step in scenario.get("steps", []):
                        loc = page.locator(step["selector"])
                        action = step["action"]
                        if action == "click":
                            loc.click()
                        elif action == "fill":
                            loc.fill(step["value"])
                        elif action == "select":
                            loc.select_option(step["value"])
                        elif action == "check":
                            loc.check()
                        elif action == "uncheck":
                            loc.uncheck()
                        elif action == "press":
                            loc.press(step["value"])
                        if step.get("wait_for"):
                            page.wait_for_function(
                                """selector => { const node = document.querySelector(selector);
                                return node?.textContent?.trim() && node.textContent.trim() !== 'Loading…'; }""",
                                arg=step["wait_for"],
                                timeout=timeout_ms,
                            )
                    results[scenario["id"]] = {
                        name: observation(page.locator(selector))
                        for name, selector in scenario.get("observe", {}).items()
                    }
                except (Error, ValueError) as exc:
                    results[scenario["id"]] = {"__error__": type(exc).__name__}
                finally:
                    if screenshots:
                        try:
                            page.screenshot(path=out.with_name(f"{out.stem}-{index:03}.png"))
                        except Error:
                            results[scenario["id"]]["__error__"] = "ScreenshotUnavailable"
                    page.close()
        finally:
            browser.close()
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results
