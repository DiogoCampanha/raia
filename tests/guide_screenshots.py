#!/usr/bin/env python3
"""
Screenshots for the tester guide, taken from the app itself.

    pip install playwright && playwright install chromium   # once
    python tests/guide_screenshots.py                       # writes docs/images/guide/*.png

The Guide page and docs/TESTERS.md show one screenshot per step
(``raia.ui.guide.IMAGES``). This script starts the app in mock mode on a free
port, walks the resume-screening demo through the screens those steps describe,
and saves each one. Re-run it whenever one of those screens changes.

Mock mode calls no model, so its records carry placeholder wording ("[MOCK
MODE] Placeholder headline ..."). Before each picture the placeholders are
replaced on screen with example wording for the resume-screening case, and the
mock-mode banner is hidden, so the images read like a real run. Nothing else on
the screen is altered. To photograph a real deployment instead, pass its address
(``--base https://...``) after signing in there; no wording is replaced then.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from raia.ui.guide import IMAGE_DIR, IMAGES  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional tool
    print("Playwright is not installed: pip install playwright && playwright install chromium")
    sys.exit(0)

#: Mock placeholders -> example wording for the resume-screening demo.
EXAMPLE_WORDING = {
    "[MOCK MODE] Placeholder headline: no model was called.":
        "High risk under both laws: applicants are rejected automatically, with no case-level human review.",
    "[MOCK MODE] No model was called; this record conforms to the contract but is not an analysis.":
        "TalentFlow ranks and filters job applications; the lowest-scored never reach a recruiter.",
    "Placeholder finding from mock mode": "Historical hiring data may encode bias against protected groups",
    "Second placeholder finding from mock mode": "Applicants are not told that a model screened them out",
    "Third placeholder finding from mock mode": "Resumes hold more personal data than screening needs",
    "Placeholder action from mock mode.": "Measure selection rates by group before each release.",
    "Second placeholder action from mock mode.": "Tell applicants that a model ranks their application.",
    "Third placeholder action from mock mode.": "Drop resume fields the ranking does not need.",
}

SHOTS = {title: name for title, name in IMAGES.items()}
WIDTH, HEIGHT = 1280, 800


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(port: int, tmp: str) -> subprocess.Popen:
    env = {**os.environ, "RAIA_LLM_PROVIDER": "mock", "RAIA_FAKE_EMBED": "1", "RAIA_AUTH": "dev",
           "RAIA_DEV_USER_NAME": os.environ.get("RAIA_DEV_USER_NAME", "Ana Souza"),
           "RAIA_DEV_USER_EMAIL": os.environ.get("RAIA_DEV_USER_EMAIL", "ana.souza@example.org"),
           "RAIA_WORKSPACE_DIR": str(Path(tmp) / "workspace"), "RAIA_CHROMA_DIR": str(Path(tmp) / "chroma")}
    return subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
                             "--server.port", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _idle(page, extra: int = 1500) -> None:
    page.wait_for_timeout(400)
    for _ in range(200):
        if page.locator('[data-testid="stStatusWidget"]').count() == 0:
            break
        page.wait_for_timeout(250)
    page.wait_for_timeout(extra)


_TIDY = """(map) => {
  document.querySelectorAll('[data-testid="stAlert"]').forEach((a) => {
    if (a.innerText.includes('Mock mode is on')) a.closest('[data-testid="stElementContainer"]').style.display = 'none';
  });
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n; while ((n = walk.nextNode())) {
    for (const [from, to] of Object.entries(map)) if (n.nodeValue.includes(from)) n.nodeValue = n.nodeValue.split(from).join(to);
  }
}"""


def shoot(page, title: str, wording: bool, at: str | None = None, block: str = "start") -> None:
    if wording:
        page.evaluate(_TIDY, EXAMPLE_WORDING)
    if at:
        page.locator(at).first.evaluate(f"(e) => e.scrollIntoView({{block: '{block}'}})")
        if block == "start":  # clear the menu bar, which stays on top of the page
            page.evaluate("document.querySelector('[data-testid=stMain]').scrollBy(0, -96)")
    else:
        page.evaluate("document.querySelector('[data-testid=stMain]').scrollTo(0, 0)")
    page.wait_for_timeout(500)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(IMAGE_DIR / SHOTS[title]))
    print("  wrote", (IMAGE_DIR / SHOTS[title]).relative_to(ROOT))


def walk(base: str, wording: bool) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.goto(base)
        consent = page.get_by_text("I have read the Privacy Policy")
        try:
            consent.wait_for(timeout=90000)
            consent.click()
            _idle(page, 500)
            page.locator("button", has_text="Continue").first.click()
        except Exception:  # noqa: BLE001 - already accepted on this deployment
            pass
        page.wait_for_selector("text=All projects", timeout=90000)
        _idle(page)
        shoot(page, "Create a project", wording, at='[class*="st-key-card-demo-"]', block="center")

        # The example wording below is the resume-screening case's, so that is the demo walked.
        page.locator('[class*="st-key-demo_project_resume_screening"] button').first.click()
        page.wait_for_url(re.compile("id="), timeout=60000)
        pid = re.search(r"id=([0-9a-f]+)", page.url).group(1)

        page.goto(f"{base}/stage?project={pid}&agent=risk_classifier")
        page.wait_for_selector("text=Run Risk Classifier", timeout=60000)
        _idle(page)
        shoot(page, "Answer the Risk Classifier's questions", wording)

        page.locator("button", has_text="Run Risk Classifier").first.click()
        page.wait_for_selector("text=Human review required", timeout=180000)
        _idle(page, 3000)
        shoot(page, "Run the agent and read the draft", wording, at='[class*="gate_head"]')
        shoot(page, "Review each card, and take the decisions", wording, at="#card-RC-F1", block="center")
        shoot(page, "Approve it, or reject it with a reason", wording, at='[class*="approve_box"]', block="center")

        page.locator("button", has_text="Approve and commit").first.click()
        page.wait_for_selector("text=Approved and committed", timeout=120000)
        _idle(page, 2500)
        shoot(page, "Continue through the stages", wording, at='[class*="-done"]', block="center")

        page.goto(f"{base}/stage?project={pid}&agent=requirements_reviewer")
        page.wait_for_selector("text=Run Requirements Reviewer", timeout=60000)
        _idle(page, 2000)
        page.locator("button", has_text="Run Requirements Reviewer").first.click()
        page.wait_for_selector("text=Human review required", timeout=180000)
        _idle(page, 2500)
        page.locator("button", has_text="Approve and commit").first.click()
        page.wait_for_selector("text=Approved and committed", timeout=120000)
        _idle(page)

        page.goto(f"{base}/project?id={pid}")
        page.wait_for_selector("text=Plan Sprint 1", timeout=60000)
        _idle(page, 4000)
        shoot(page, "Run sprints on the Board", wording, at='[data-testid="stTabs"]', block="start")

        page.goto(f"{base}/assessment")
        page.wait_for_selector("text=Evaluation of RAIA", timeout=60000)
        _idle(page, 2000)
        page.locator('[class*="st-key-a_dim_utility"] [data-testid="stRadioOption"]').nth(3).click()
        _idle(page, 1000)
        shoot(page, "Complete the assessment", wording, at='[class*="st-key-a_dim_utility"]', block="center")
        browser.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", help="address of a running RAIA to photograph instead of a local mock app")
    args = ap.parse_args()
    if args.base:
        walk(args.base.rstrip("/"), wording=False)
        return
    port, tmp = _free_port(), tempfile.mkdtemp(prefix="raia_guide_")
    server = _start(port, tmp)
    try:
        time.sleep(4)
        walk(f"http://127.0.0.1:{port}", wording=True)
    finally:
        server.terminate()


if __name__ == "__main__":
    main()
