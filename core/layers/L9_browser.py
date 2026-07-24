"""Layer 9: Browser Automation — Chrome, Firefox, Edge via Playwright.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 11:

Library: Playwright (async API, connects to existing browser via CDP)
Setup: chrome.exe --remote-debugging-port=9222

Actions:
  navigate, reload, go_back, go_forward, new_tab, close_tab, switch_tab
  get_page_info, get_current_url, get_page_title, get_page_content, get_page_html
  click_element, hover_element, type_into_element, fill_form, submit_form
  find_element, get_element_text, get_element_attribute
  scroll_page, scroll_to_element
  take_screenshot, run_javascript
  wait_for_element, wait_for_url, wait_for_network_idle
  manage_cookies, manage_local_storage
  download_file, intercept_request
"""

from __future__ import annotations

from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.layers._utils import run_cmd, run_ps, create_escalation_fn, create_preflight_fn

import logging
logger = logging.getLogger("may.core.layers.L9_browser")

# Lazy-loaded playwright instance
_playwright = None
_browser = None


async def _get_browser():
    """Get or create a Playwright browser connection."""
    global _playwright, _browser
    if _browser and _browser.is_connected():
        return _browser
    from playwright.async_api import async_playwright
    _playwright = await async_playwright().start()
    try:
        _browser = await _playwright.chromium.connect_over_cdp("http://localhost:9222")
        return _browser
    except Exception as e:
        logger.warning("Could not connect to browser via CDP: %s", e)
        raise


async def _get_page(params: dict = None):
    """Get the active page, or a specific tab by index/URL."""
    browser = await _get_browser()
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    
    # Select specific tab if requested
    tab_index = params.get("tab_index") if params else None
    tab_url = params.get("tab_url") if params else None
    
    if tab_index is not None and tab_index < len(context.pages):
        return context.pages[tab_index]
    if tab_url:
        for page in context.pages:
            if tab_url in page.url:
                return page
    if context.pages:
        return context.pages[0]
    return await context.new_page()


# ══════════════════════════════════════════════════════════════════════════════
# NAVIGATION
# ══════════════════════════════════════════════════════════════════════════════

async def _navigate(params: dict) -> Any:
    """Navigate to a URL."""
    url = params["url"]
    page = await _get_page(params)
    await page.goto(url, timeout=30000)
    return {"url": url, "title": await page.title()}


async def _reload(params: dict) -> Any:
    """Reload the current page."""
    page = await _get_page(params)
    await page.reload(timeout=30000)
    return {"url": page.url, "title": await page.title()}


async def _go_back(params: dict) -> Any:
    """Go back in browser history."""
    page = await _get_page(params)
    await page.go_back()
    return {"url": page.url}


async def _go_forward(params: dict) -> Any:
    """Go forward in browser history."""
    page = await _get_page(params)
    await page.go_forward()
    return {"url": page.url}


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════

async def _new_tab(params: dict) -> Any:
    """Open a new tab."""
    url = params.get("url", "about:blank")
    browser = await _get_browser()
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = await context.new_page()
    if url != "about:blank":
        await page.goto(url, timeout=30000)
    return {"url": url, "tab_count": len(context.pages)}


async def _close_tab(params: dict) -> Any:
    """Close a tab by index or URL."""
    browser = await _get_browser()
    context = browser.contexts[0] if browser.contexts else None
    if not context:
        return {"error": "No browser context"}
    
    tab_index = params.get("tab_index", -1)
    tab_url = params.get("tab_url", "")
    
    if tab_url:
        for page in context.pages:
            if tab_url in page.url:
                await page.close()
                return {"closed_tab": tab_url}
    elif 0 <= tab_index < len(context.pages):
        page = context.pages[tab_index]
        url = page.url
        await page.close()
        return {"closed_tab": url}
    elif len(context.pages) > 1:
        # Close current/last tab
        page = context.pages[-1]
        url = page.url
        await page.close()
        return {"closed_tab": url}
    
    return {"error": "No tab to close"}


async def _switch_tab(params: dict) -> Any:
    """Switch to a tab by index or URL."""
    page = await _get_page(params)
    await page.bring_to_front()
    return {"url": page.url, "title": await page.title()}


# ══════════════════════════════════════════════════════════════════════════════
# PAGE INFO
# ══════════════════════════════════════════════════════════════════════════════

async def _get_page_info(params: dict) -> Any:
    """Get current page title and URL."""
    page = await _get_page(params)
    return {"title": await page.title(), "url": page.url}


async def _get_current_url(params: dict) -> Any:
    """Get the current page URL."""
    page = await _get_page(params)
    return {"url": page.url}


async def _get_page_content(params: dict) -> Any:
    """Get page HTML content."""
    page = await _get_page(params)
    content = await page.content()
    max_chars = params.get("max_chars", 10000)
    return {"html": content[:max_chars], "length": len(content)}


async def _get_page_html(params: dict) -> Any:
    """Get full page HTML (alias for get_page_content with no truncation)."""
    page = await _get_page(params)
    content = await page.content()
    return {"html": content[:50000]}


# ══════════════════════════════════════════════════════════════════════════════
# ELEMENT INTERACTION
# ══════════════════════════════════════════════════════════════════════════════

async def _click_element(params: dict) -> Any:
    """Click an element by selector."""
    selector = params["selector"]
    page = await _get_page(params)
    timeout = params.get("timeout", 10000)
    await page.click(selector, timeout=timeout)
    return {"clicked": selector}


async def _hover_element(params: dict) -> Any:
    """Hover over an element by selector."""
    selector = params["selector"]
    page = await _get_page(params)
    await page.hover(selector, timeout=10000)
    return {"hovered": selector}


async def _type_into_element(params: dict) -> Any:
    """Type text into an element (clears first)."""
    selector = params["selector"]
    text = params["text"]
    page = await _get_page(params)
    await page.fill(selector, text, timeout=10000)
    return {"typed": text, "selector": selector}


async def _fill_form(params: dict) -> Any:
    """Fill multiple form fields at once.
    
    params:
      fields: list of {selector, value} dicts
    """
    fields = params.get("fields", [])
    page = await _get_page(params)
    filled = []
    for field in fields:
        selector = field.get("selector", "")
        value = field.get("value", "")
        if selector:
            await page.fill(selector, value, timeout=10000)
            filled.append(selector)
    return {"filled": filled, "count": len(filled)}


async def _submit_form(params: dict) -> Any:
    """Submit a form by pressing Enter on a field or clicking submit button."""
    selector = params.get("selector", "")
    page = await _get_page(params)
    if selector:
        await page.press(selector, "Enter")
    else:
        await page.keyboard.press("Enter")
    return {"submitted": True}


async def _find_element(params: dict) -> Any:
    """Check if an element exists on the page."""
    selector = params["selector"]
    page = await _get_page(params)
    element = await page.query_selector(selector)
    if element:
        text = await element.inner_text() if await element.is_visible() else ""
        return {"found": True, "selector": selector, "text": text[:500], "visible": await element.is_visible()}
    return {"found": False, "selector": selector}


async def _get_element_text(params: dict) -> Any:
    """Get text content of an element."""
    selector = params["selector"]
    page = await _get_page(params)
    element = await page.query_selector(selector)
    if not element:
        return {"error": f"Element not found: {selector}"}
    text = await element.inner_text()
    return {"text": text, "selector": selector}


async def _get_element_attribute(params: dict) -> Any:
    """Get an attribute value from an element."""
    selector = params["selector"]
    attribute = params["attribute"]
    page = await _get_page(params)
    value = await page.get_attribute(selector, attribute)
    return {"attribute": attribute, "value": value, "selector": selector}


# ══════════════════════════════════════════════════════════════════════════════
# SCROLLING
# ══════════════════════════════════════════════════════════════════════════════

async def _scroll_page(params: dict) -> Any:
    """Scroll the page up or down."""
    direction = params.get("direction", "down")
    amount = params.get("amount", 500)
    page = await _get_page(params)
    delta = amount if direction == "down" else -amount
    await page.mouse.wheel(0, delta)
    return {"scrolled": direction, "amount": amount}


async def _scroll_to_element(params: dict) -> Any:
    """Scroll an element into view."""
    selector = params["selector"]
    page = await _get_page(params)
    await page.locator(selector).scroll_into_view_if_needed()
    return {"scrolled_to": selector}


# ══════════════════════════════════════════════════════════════════════════════
# SCREENSHOTS & JS
# ══════════════════════════════════════════════════════════════════════════════

async def _take_screenshot(params: dict) -> Any:
    """Take a screenshot."""
    import tempfile
    page = await _get_page(params)
    path = params.get("path", "")
    if not path:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        path = tmp.name
    full_page = params.get("full_page", False)
    await page.screenshot(path=path, full_page=full_page)
    return {"path": path}


async def _run_javascript(params: dict) -> Any:
    """Run JavaScript on the page."""
    script = params["script"]
    page = await _get_page(params)
    result = await page.evaluate(script)
    return {"result": result}


# ══════════════════════════════════════════════════════════════════════════════
# WAIT FOR
# ══════════════════════════════════════════════════════════════════════════════

async def _wait_for_element(params: dict) -> Any:
    """Wait for an element to appear."""
    selector = params["selector"]
    timeout = params.get("timeout", 10000)
    page = await _get_page(params)
    await page.wait_for_selector(selector, timeout=timeout)
    return {"found": selector}


async def _wait_for_url(params: dict) -> Any:
    """Wait for the URL to contain a pattern."""
    pattern = params["pattern"]
    timeout = params.get("timeout", 10000)
    page = await _get_page(params)
    await page.wait_for_url(f"*{pattern}*", timeout=timeout)
    return {"url": page.url}


async def _wait_for_network_idle(params: dict) -> Any:
    """Wait for network to be idle (no pending requests)."""
    timeout = params.get("timeout", 10000)
    page = await _get_page(params)
    await page.wait_for_load_state("networkidle", timeout=timeout)
    return {"url": page.url, "state": "networkidle"}


# ══════════════════════════════════════════════════════════════════════════════
# COOKIES & STORAGE
# ══════════════════════════════════════════════════════════════════════════════

async def _manage_cookies(params: dict) -> Any:
    """Get, set, or delete cookies.
    
    action: get, set, delete, clear
    For set: name, value, domain, path
    For delete: name
    """
    action = params.get("action", "get")
    page = await _get_page(params)
    context = page.context
    
    if action == "get":
        cookies = await context.cookies()
        return {"cookies": cookies[:50], "count": len(cookies)}
    elif action == "set":
        cookie = {
            "name": params.get("name", ""),
            "value": params.get("value", ""),
            "domain": params.get("domain", ""),
            "path": params.get("path", "/"),
        }
        await context.add_cookies([cookie])
        return {"set": cookie["name"]}
    elif action == "delete":
        name = params.get("name", "")
        domain = params.get("domain", "")
        cookies = await context.cookies()
        to_delete = [c for c in cookies if c["name"] == name]
        for c in to_delete:
            await context.delete_cookies([{"name": c["name"], "domain": c["domain"], "path": c.get("path", "/")}])
        return {"deleted": name, "count": len(to_delete)}
    elif action == "clear":
        await context.clear_cookies()
        return {"cleared": True}
    
    return {"error": f"Unknown cookie action: {action}"}


async def _manage_local_storage(params: dict) -> Any:
    """Get, set, or clear localStorage.
    
    action: get, set, clear, keys
    For set: key, value
    """
    action = params.get("action", "get")
    page = await _get_page(params)
    
    if action == "get":
        key = params.get("key", "")
        if key:
            value = await page.evaluate(f"localStorage.getItem('{key}')")
            return {"key": key, "value": value}
        else:
            length = await page.evaluate("localStorage.length")
            items = {}
            for i in range(min(length, 50)):
                item = await page.evaluate(f"localStorage.key({i})")
                val = await page.evaluate(f"localStorage.getItem('{item}')")
                items[item] = val
            return {"items": items, "count": length}
    elif action == "set":
        key = params.get("key", "")
        value = params.get("value", "")
        await page.evaluate("localStorage.setItem(arguments[0], arguments[1])", key, value)
        return {"set": key}
    elif action == "clear":
        await page.evaluate("localStorage.clear()")
        return {"cleared": True}
    elif action == "keys":
        keys = await page.evaluate("Object.keys(localStorage)")
        return {"keys": keys}
    
    return {"error": f"Unknown localStorage action: {action}"}


# ══════════════════════════════════════════════════════════════════════════════
# DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

async def _download_file(params: dict) -> Any:
    """Download a file from a URL."""
    import tempfile
    import os
    
    url = params["url"]
    save_path = params.get("path", "")
    
    if not save_path:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".download")
        save_path = tmp.name
    
    page = await _get_page(params)
    
    # Trigger download via page
    async with page.expect_download(timeout=30000) as download_info:
        await page.evaluate(f"window.location.href = '{url}'")
    download = await download_info.value
    await download.path_as_needed(save_path)
    
    return {"path": save_path, "suggested_name": download.suggested_filename}


# ══════════════════════════════════════════════════════════════════════════════
# INTERCEPT REQUEST
# ══════════════════════════════════════════════════════════════════════════════

async def _cleanup_browser() -> None:
    """Safely close existing browser and stop playwright to avoid resource leaks."""
    global _playwright, _browser
    if _browser:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright:
        try:
            await _playwright.stop()
        except Exception:
            pass
        _playwright = None


async def _open_browser_action(params: dict) -> Any:
    """Launch a new browser instance via Playwright."""
    await _cleanup_browser()
    from playwright.async_api import async_playwright
    headless = params.get("headless", False)
    browser_type = params.get("browser", "chromium")
    _playwright = await async_playwright().start()
    launcher = getattr(_playwright, browser_type, _playwright.chromium)
    _browser = await launcher.launch(headless=headless)
    url = params.get("url", "about:blank")
    if url and url != "about:blank":
        page = await _browser.new_page()
        await page.goto(url, timeout=30000)
    return {"browser": browser_type, "url": url}


async def _close_browser_action(params: dict) -> Any:
    """Close the browser instance."""
    global _browser
    if _browser:
        await _browser.close()
        _browser = None
    return {"closed": True}


_dialog_results = {}  # tab_id -> action

async def _handle_dialog_action(params: dict) -> Any:
    """Accept or dismiss a JS dialog (alert, confirm, prompt)."""
    action = params.get("action", "accept")  # accept, dismiss
    text = params.get("text", "")  # for prompt
    page = await _get_page(params)
    # Set up handler for next dialog
    async def on_dialog(dialog):
        if action == "accept":
            if text and dialog.type == "prompt":
                await dialog.accept(text)
            else:
                await dialog.accept()
        else:
            await dialog.dismiss()
    page.once("dialog", on_dialog)
    return {"handler_set": action}


async def _intercept_request(params: dict) -> Any:
    """Block or modify network requests matching a pattern.
    
    action: block, allow_all
    pattern: URL pattern to match (substring)
    """
    action = params.get("action", "allow_all")
    pattern = params.get("pattern", "")
    page = await _get_page(params)
    
    if action == "block" and pattern:
        await page.route(f"**/*{pattern}*", lambda route: route.abort())
        return {"blocked": pattern}
    elif action == "allow_all":
        await page.unroute("**/*")
        return {"unblocked": True}
    
    return {"error": f"Unknown intercept action: {action}"}


# ══════════════════════════════════════════════════════════════════════════════
# CONNECT TO EXISTING BROWSER (via CDP)
# ══════════════════════════════════════════════════════════════════════════════

async def _connect_to_browser_action(params: dict) -> Any:
    """Connect to an existing browser instance via Chrome DevTools Protocol.

    params:
      cdp_url: CDP endpoint URL (default: http://localhost:9222)
    """
    cdp_url = params.get("cdp_url", "http://localhost:9222")
    await _cleanup_browser()
    from playwright.async_api import async_playwright
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.connect_over_cdp(cdp_url)
    contexts = _browser.contexts
    page_count = sum(len(c.pages) for c in contexts)
    return {
        "connected": True,
        "cdp_url": cdp_url,
        "contexts": len(contexts),
        "pages": page_count,
    }


# ══════════════════════════════════════════════════════════════════════════════
# JAVASCRIPT / CDP FALLBACK METHODS
# ══════════════════════════════════════════════════════════════════════════════

async def _navigate_js(params: dict) -> Any:
    """Method 2: Navigate via JavaScript window.location."""
    url = params["url"]
    page = await _get_page(params)
    await page.evaluate(f"window.location.href = '{url}'")
    await page.wait_for_load_state("domcontentloaded", timeout=30000)
    return {"url": url, "title": await page.title()}


async def _reload_js(params: dict) -> Any:
    """Method 2: Reload via JavaScript location.reload()."""
    page = await _get_page(params)
    await page.evaluate("location.reload()")
    await page.wait_for_load_state("domcontentloaded", timeout=30000)
    return {"url": page.url, "title": await page.title()}


async def _go_back_js(params: dict) -> Any:
    """Method 2: Go back via JavaScript history.back()."""
    page = await _get_page(params)
    await page.evaluate("history.back()")
    await page.wait_for_timeout(1000)
    return {"url": page.url}


async def _go_forward_js(params: dict) -> Any:
    """Method 2: Go forward via JavaScript history.forward()."""
    page = await _get_page(params)
    await page.evaluate("history.forward()")
    await page.wait_for_timeout(1000)
    return {"url": page.url}


async def _click_element_js(params: dict) -> Any:
    """Method 2: Click element via JavaScript."""
    selector = params["selector"]
    page = await _get_page(params)
    # Try multiple JS click strategies
    try:
        await page.evaluate(f"document.querySelector('{selector}').click()")
        return {"clicked": selector}
    except Exception:
        # Try XPath-like CSS selector conversion
        css = selector.replace("//", " > ").replace("[@class='", "[class='")
        await page.evaluate(f"document.querySelector('{css}').click()")
        return {"clicked": selector}


async def _type_into_element_js(params: dict) -> Any:
    """Method 2: Type into element via JavaScript value setting + input event."""
    selector = params["selector"]
    text = params["text"]
    page = await _get_page(params)
    await page.evaluate(
        f"const el = document.querySelector('{selector}'); "
        f"el.value = '{text}'; "
        f"el.dispatchEvent(new Event('input', {{bubbles: true}})); "
        f"el.dispatchEvent(new Event('change', {{bubbles: true}}));"
    )
    return {"typed": text, "selector": selector}


async def _get_element_text_js(params: dict) -> Any:
    """Method 2: Get element text via JavaScript."""
    selector = params["selector"]
    page = await _get_page(params)
    text = await page.evaluate(f"document.querySelector('{selector}')?.innerText || ''")
    return {"text": text, "selector": selector}


async def _get_element_attribute_js(params: dict) -> Any:
    """Method 2: Get element attribute via JavaScript."""
    selector = params["selector"]
    attribute = params["attribute"]
    page = await _get_page(params)
    value = await page.evaluate(f"document.querySelector('{selector}')?.getAttribute('{attribute}') || null")
    return {"attribute": attribute, "value": value, "selector": selector}


async def _scroll_page_js(params: dict) -> Any:
    """Method 2: Scroll via JavaScript."""
    direction = params.get("direction", "down")
    amount = params.get("amount", 500)
    page = await _get_page(params)
    dy = amount if direction == "down" else -amount
    await page.evaluate(f"window.scrollBy(0, {dy})")
    return {"scrolled": direction, "amount": amount}


async def _scroll_to_element_js(params: dict) -> Any:
    """Method 2: Scroll element into view via JavaScript."""
    selector = params["selector"]
    page = await _get_page(params)
    await page.evaluate(f"document.querySelector('{selector}')?.scrollIntoView({{behavior: 'smooth'}})")
    return {"scrolled_to": selector}


async def _take_screenshot_js(params: dict) -> Any:
    """Method 2: Screenshot via Playwright CDP."""
    import base64
    page = await _get_page(params)
    path = params.get("path", "screenshot.png")
    cdp = await page.context.new_cdp_session(page)
    result = await cdp.send("Page.captureScreenshot", {"format": "png"})
    data = base64.b64decode(result["data"])
    with open(path, "wb") as f:
        f.write(data)
    return {"path": path}


async def _wait_for_element_js(params: dict) -> Any:
    """Method 2: Wait for element via JavaScript polling."""
    selector = params["selector"]
    timeout = params.get("timeout", 10000)
    page = await _get_page(params)
    # Poll with JS instead of Playwright wait
    result = await page.evaluate(
        f"new Promise((resolve, reject) => {{ "
        f"  const start = Date.now(); "
        f"  const check = () => {{ "
        f"    const el = document.querySelector('{selector}'); "
        f"    if (el) resolve(true); "
        f"    else if (Date.now() - start > {timeout}) reject(new Error('timeout')); "
        f"    else setTimeout(check, 100); "
        f"  }}; check(); }})"
    )
    return {"found": selector}


async def _get_page_content_js(params: dict) -> Any:
    """Method 2: Get page content via JavaScript."""
    page = await _get_page(params)
    content = await page.evaluate("document.documentElement.outerHTML")
    max_chars = params.get("max_chars", 10000)
    return {"html": content[:max_chars], "length": len(content)}


async def _find_element_js(params: dict) -> Any:
    """Method 2: Find element via JavaScript."""
    selector = params["selector"]
    page = await _get_page(params)
    result = await page.evaluate(
        f"(() => {{ const el = document.querySelector('{selector}'); "
        f"if (!el) return {{found: false, selector: '{selector}'}}; "
        f"return {{found: true, selector: '{selector}', text: (el.innerText || '').substring(0, 500), visible: el.offsetParent !== null}}; }})()"
    )
    return result


async def _submit_form_js(params: dict) -> Any:
    """Method 2: Submit form via JavaScript."""
    selector = params.get("selector", "form")
    page = await _get_page(params)
    try:
        await page.evaluate(f"document.querySelector('{selector}').submit()")
    except Exception:
        await page.evaluate("document.forms[0]?.submit()")
    return {"submitted": True}


async def _fill_form_js(params: dict) -> Any:
    """Method 2: Fill form via JavaScript."""
    fields = params.get("fields", [])
    page = await _get_page(params)
    filled = []
    for field in fields:
        selector = field.get("selector", "")
        value = field.get("value", "")
        if selector:
            await page.evaluate(
                f"(() => {{ const el = document.querySelector('{selector}'); "
                f"if (el) {{ el.value = '{value}'; el.dispatchEvent(new Event('input', {{bubbles: true}})); }} }})()"
            )
            filled.append(selector)
    return {"filled": filled, "count": len(filled)}


async def _new_tab_js(params: dict) -> Any:
    """Method 2: Open new tab via JavaScript."""
    url = params.get("url", "about:blank")
    page = await _get_page(params)
    await page.evaluate(f"window.open('{url}', '_blank')")
    await page.wait_for_timeout(1000)
    browser = await _get_browser()
    context = browser.contexts[0] if browser.contexts else None
    tab_count = len(context.pages) if context else 1
    return {"url": url, "tab_count": tab_count}


# ══════════════════════════════════════════════════════════════════════════════
# WEB SEARCH (open Google in browser)
# ══════════════════════════════════════════════════════════════════════════════

async def _web_search_browser(params: dict) -> Any:
    """Method 1: Open Google search via Playwright browser."""
    import urllib.parse
    query = params.get("query", "")
    q = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={q}"
    try:
        browser = await _get_browser()
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        await page.goto(url, timeout=30000)
        return {"query": query, "url": url, "title": await page.title()}
    except Exception:
        # If browser not available, fall back to cmd /c start (no shell=True)
        import subprocess as _subprocess
        _subprocess.Popen(["cmd", "/c", "start", "", url],
                          stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL)
        return {"query": query, "url": url}


async def _web_search_powershell(params: dict) -> Any:
    """Method 2: Open Google search via PowerShell Start-Process."""
    import urllib.parse
    query = params.get("query", "")
    q = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={q}"
    success, output = await run_ps(f"Start-Process '{url}'")
    return {"query": query, "url": url}


# ══════════════════════════════════════════════════════════════════════════════
# OPEN URL (in default browser)
# ══════════════════════════════════════════════════════════════════════════════

async def _open_url_startfile(params: dict) -> Any:
    """Method 1: Open URL via cmd /c start (safe, no shell=True)."""
    import subprocess as _subprocess
    url = params.get("url", "")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    _subprocess.Popen(["cmd", "/c", "start", "", url],
                      stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL)
    return {"opened": url}


async def _open_url_powershell(params: dict) -> Any:
    """Method 2: Open URL via PowerShell Start-Process."""
    url = params.get("url", "")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    success, output = await run_ps(f"Start-Process '{url}'")
    if not success:
        raise RuntimeError(output)
    return {"opened": url}


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACT WEB CONTENT (fetch URL, strip HTML, return text)
# ══════════════════════════════════════════════════════════════════════════════

async def _extract_web_content_httpx(params: dict) -> Any:
    """Method 1: Extract content via httpx."""
    import httpx as _httpx
    import re as _re
    url = params.get("url", "")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    async with _httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        html = resp.text
        # Strip scripts and styles
        html = _re.sub(r'<script[^>]*>.*?</script>', '', html, flags=_re.DOTALL | _re.IGNORECASE)
        html = _re.sub(r'<style[^>]*>.*?</style>', '', html, flags=_re.DOTALL | _re.IGNORECASE)
        # Extract text
        text = _re.sub(r'<[^>]+>', ' ', html)
        text = _re.sub(r'\s+', ' ', text).strip()[:5000]
        return {"url": url, "content": text, "length": len(text)} if text else {"url": url, "content": "", "error": "No content"}


async def _extract_web_content_powershell(params: dict) -> Any:
    """Method 2: Extract content via PowerShell Invoke-WebRequest."""
    url = params.get("url", "")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    success, output = await run_ps(
        f"(Invoke-WebRequest -Uri '{url}' -UseBasicParsing -TimeoutSec 15).Content"
    )
    if success and output:
        import re as _re
        html = output
        html = _re.sub(r'<script[^>]*>.*?</script>', '', html, flags=_re.DOTALL | _re.IGNORECASE)
        html = _re.sub(r'<style[^>]*>.*?</style>', '', html, flags=_re.DOTALL | _re.IGNORECASE)
        text = _re.sub(r'<[^>]+>', ' ', html)
        text = _re.sub(r'\s+', ' ', text).strip()[:5000]
        return {"url": url, "content": text, "length": len(text)}
    return {"url": url, "content": "", "error": output or "Failed"}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION HANDLER
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    # Navigation
    "navigate":           ([_navigate, _navigate_js], None),
    "reload":             ([_reload, _reload_js], None),
    "go_back":            ([_go_back, _go_back_js], None),
    "go_forward":         ([_go_forward, _go_forward_js], None),
    
    # Tabs
    "new_tab":            ([_new_tab, _new_tab_js], None),
    "close_tab":          ([_close_tab], None),
    "switch_tab":         ([_switch_tab], None),
    
    # Page info
    "get_page_info":      ([_get_page_info], None),
    "get_current_url":    ([_get_current_url], None),
    "get_page_content":   ([_get_page_content, _get_page_content_js], None),
    "get_page_html":      ([_get_page_html, _get_page_content_js], None),
    
    # Element interaction
    "click_element":      ([_click_element, _click_element_js], None),
    "hover_element":      ([_hover_element], None),
    "type_into_element":  ([_type_into_element, _type_into_element_js], None),
    "fill_form":          ([_fill_form, _fill_form_js], None),
    "submit_form":        ([_submit_form, _submit_form_js], None),
    "find_element":       ([_find_element, _find_element_js], None),
    "get_element_text":   ([_get_element_text, _get_element_text_js], None),
    "get_element_attribute": ([_get_element_attribute, _get_element_attribute_js], None),
    
    # Scrolling
    "scroll_page":        ([_scroll_page, _scroll_page_js], None),
    "scroll_to_element":  ([_scroll_to_element, _scroll_to_element_js], None),
    
    # Screenshots & JS
    "take_screenshot":    ([_take_screenshot, _take_screenshot_js], None),
    "run_javascript":     ([_run_javascript], None),
    
    # Wait for
    "wait_for_element":   ([_wait_for_element, _wait_for_element_js], None),
    "wait_for_url":       ([_wait_for_url], None),
    "wait_for_network_idle": ([_wait_for_network_idle], None),
    
    # Cookies & Storage
    "manage_cookies":     ([_manage_cookies], None),
    "manage_local_storage": ([_manage_local_storage], None),
    
    # Download & Intercept
    "download_file":      ([_download_file], None),
    "intercept_request":  ([_intercept_request], None),
    # --- Phase 7 additions ---
    "open_browser":    ([_open_browser_action], None),
    "close_browser":   ([_close_browser_action], None),
    "handle_dialog":   ([_handle_dialog_action], None),
    "connect_to_browser": ([_connect_to_browser_action], None),
    # --- web_search (open Google search in browser) ---
    "web_search":  ([_web_search_browser, _web_search_powershell], None),
    # --- open_url (open URL in default browser) ---
    "open_url":    ([_open_url_startfile, _open_url_powershell], None),
    # --- extract_web_content (fetch URL and extract text) ---
    "extract_web_content": ([_extract_web_content_httpx, _extract_web_content_powershell], None),
}


async def handler(action: str, params: dict[str, Any]) -> Result:
    """L9 Browser layer handler."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown browser action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"browser.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("browser", action),
        escalation_fn=create_escalation_fn("browser", action),
    )

    suggested = None
    if not success and error:
        suggested = f"Try running as Administrator. Error: {error[:120]}"

    return Result(
        command_id=params.get("id", ""),
        success=success,
        data=data,
        error=error if not success else None,
        verified=verifier is not None and success,
        method_used=method_used,
        suggested_action=suggested,
    )
