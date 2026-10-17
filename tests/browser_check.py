#!/usr/bin/env python3
"""
The page stays where the person is — checked in a real browser.

    pip install playwright && playwright install chromium   # once
    python tests/browser_check.py

Streamlit's app-test harness (tests/test_ui.py) sees which elements a page
draws, not where the browser leaves the person. Two failures only a browser
shows have reached testers: an element drawn on one redraw and not the next
shifted everything after it, so Streamlit rebuilt the draft and the person
landed at the end of the page with any popover closed; and a decision's
button stayed greyed out because the reason typed into it had not reached the
app yet. This script starts the app in mock mode on a free port, walks the
first stages in headless Chromium and checks, at each click, that the page did
not move and that a popover stayed open.

It needs Playwright and a Chromium build, so it is not part of the smoke test.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional tool
    print("Playwright is not installed: pip install playwright && playwright install chromium")
    sys.exit(0)

FAILURES = []


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILURES.append(label)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(port: int, tmp: str) -> subprocess.Popen:
    env = {**os.environ, "RAIA_LLM_PROVIDER": "mock", "RAIA_FAKE_EMBED": "1", "RAIA_AUTH": "dev",
           "RAIA_WORKSPACE_DIR": str(Path(tmp) / "workspace"), "RAIA_CHROMA_DIR": str(Path(tmp) / "chroma")}
    return subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
                             "--server.port", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _scroll(page) -> int:
    return page.evaluate("Math.round(document.querySelector('[data-testid=stMain]').scrollTop)")


def _idle(page, extra: int = 1500) -> None:
    page.wait_for_timeout(400)
    for _ in range(160):
        if page.locator('[data-testid="stStatusWidget"]').count() == 0:
            break
        page.wait_for_timeout(250)
    page.wait_for_timeout(extra)


def _main(page) -> str:
    return page.inner_text("[data-testid=stMain]")


def walk(base: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(base)
        page.wait_for_selector("text=I have read the Privacy Policy", timeout=90000)
        page.get_by_text("I have read the Privacy Policy").click()
        _idle(page, 500)
        page.locator("button", has_text="Continue").first.click()
        page.wait_for_selector("text=Create this demo project", timeout=60000)
        _idle(page, 500)
        page.locator("button", has_text="Create this demo project").first.click()
        page.wait_for_url(re.compile("id="), timeout=60000)
        pid = re.search(r"id=([0-9a-f]+)", page.url).group(1)

        print("== Risk Classifier: the first click on a new draft leaves the page where it is ==")
        page.goto(f"{base}/stage?project={pid}&agent=risk_classifier")
        page.wait_for_selector("text=Run Risk Classifier", timeout=60000)
        _idle(page)
        page.locator("button", has_text="Run Risk Classifier").first.click()
        page.wait_for_selector("text=Human review required", timeout=120000)
        _idle(page, 3000)
        group = page.locator('[data-testid="stButtonGroup"]').first
        group.scroll_into_view_if_needed()
        _idle(page, 600)
        top = "Math.round(document.getElementById('card-RC-F1').getBoundingClientRect().top)"
        before, at = _scroll(page), page.evaluate(top)
        group.locator("button", has_text="Accept").click()
        _idle(page)
        check(_scroll(page) == before and abs(page.evaluate(top) - at) <= 2,
              "accepting the first card does not move the page")
        form = page.locator('[data-testid="stForm"]').first
        form.scroll_into_view_if_needed()
        _idle(page, 600)
        form.locator('[role="radiogroup"] label').first.click()
        page.wait_for_timeout(1000)
        check(page.locator('[data-testid="stStatusWidget"]').count() == 0,
              "choosing a decision's option does not redraw the page")
        form.locator("input[type=text]").nth(1).fill("Oversight is being designed")
        form.locator("button", has_text="Record decision").click()
        _idle(page)
        check("Oversight is being designed" in _main(page), "…and Record decision records it, with the reason")
        page.locator("button", has_text="Approve and commit").first.click()
        page.wait_for_selector("text=Approved and committed", timeout=120000)
        _idle(page)

        print("== Requirements Reviewer: a decision in a popover keeps it open ==")
        page.goto(f"{base}/stage?project={pid}&agent=requirements_reviewer")
        page.wait_for_selector("text=Run Requirements Reviewer", timeout=60000)
        _idle(page, 2000)
        page.locator("button", has_text="Run Requirements Reviewer").first.click()
        page.wait_for_selector("text=Human review required", timeout=120000)
        _idle(page, 3000)
        take = page.locator("button", has_text="Take this decision")
        if take.count():
            take.first.scroll_into_view_if_needed()
            _idle(page, 500)
            take.first.click()
            page.wait_for_timeout(1200)
            before = _scroll(page)
            page.locator('[data-testid="stPopoverBody"] [role="radiogroup"] label').first.click()
            page.wait_for_timeout(1500)
            check(page.locator('[data-testid="stPopoverBody"]').count() > 0 and _scroll(page) == before,
                  "choosing an option leaves the popover open and the page where it is")
            page.keyboard.press("Escape")
        page.locator("button", has_text="Approve and commit").first.click()
        page.wait_for_selector("text=Approved and committed", timeout=120000)
        _idle(page)

        print("== What this stage receives: a decision is recorded on the first click ==")
        page.goto(f"{base}/stage?project={pid}&agent=story_refiner")
        page.wait_for_selector("text=What this stage receives", timeout=60000)
        _idle(page, 2000)
        row = page.locator('[class*="st-key-ho-dec-"]').first
        check(row.count() > 0, "the decisions still open upstream are listed")
        row.scroll_into_view_if_needed()
        _idle(page, 500)
        row.locator("button", has_text="Decide").click()
        page.wait_for_timeout(1200)
        pop = page.locator('[data-testid="stPopoverBody"]')
        pop.locator('[role="radiogroup"] label').first.click()
        field = pop.locator("input[type=text]").first
        field.click()
        field.type("Recorded from the hand-off", delay=5)
        button = pop.locator("button", has_text="Record decision")
        check(not button.is_disabled(), "the Record button is available while the reason is being typed")
        button.click()
        _idle(page)
        check("decided, recorded as" in _main(page), "…and one click records the decision")

        print("== Generate mode: the run button says what it does ==")
        page.goto(f"{base}/stage?project={pid}&agent=story_generate")
        page.wait_for_selector("text=Generate from requirements", timeout=60000)
        _idle(page, 2000)
        gen = page.locator("button", has_text="Generate stories")
        check(gen.count() == 1 and gen.first.is_visible() and not gen.first.is_disabled(),
              "a Generate stories button is there, and enabled")
        browser.close()


def main() -> None:
    port, tmp = _free_port(), tempfile.mkdtemp(prefix="raia_browser_")
    server = _start(port, tmp)
    try:
        time.sleep(4)
        walk(f"http://127.0.0.1:{port}")
    finally:
        server.terminate()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} browser check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("All browser checks passed.")


if __name__ == "__main__":
    main()
