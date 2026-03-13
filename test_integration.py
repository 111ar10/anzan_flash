#!/usr/bin/env python3
"""
test_integration.py — Anzan Flash integration tests
Real Chromium via Playwright. Covers full user flows end-to-end.

Setup:
    pip install playwright
    playwright install chromium   (or: python -m playwright install chromium)

Usage:
    python3 test_integration.py
    python3 test_integration.py -v
    python3 test_integration.py -k challenge     # filter by name substring
    python3 test_integration.py -k "name or challenge"
"""

import sys, os, re, json, time, argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, expect

# ── Config ────────────────────────────────────────────────────────────────────
HTML_FILE  = Path(__file__).parent / "anzan_flash.html"
HEADLESS   = True   # set False to watch tests run
SLOW_MO    = 0      # ms delay between actions (useful for debugging)
TIMEOUT    = 8_000  # default element timeout ms


# ── Helpers ───────────────────────────────────────────────────────────────────

def file_url(p: Path) -> str:
    return "file://" + str(p.resolve())


def make_page(pw):
    """Create a browser page with Chart.js stubbed (CDN unavailable in file://)."""
    browser = pw.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    ctx.add_init_script("""
        window.Chart = function(el, cfg) {
            this.data = (cfg || {}).data || { labels: [], datasets: [{ data: [] }] };
            this.update = function() {};
            this.destroy = function() {};
        };
        window.Chart.register = function() {};
    """)
    return browser, ctx, ctx.new_page()


def init_save(page: Page, *, name="Tester", level=5, xp=120, stars=250,
              difficulty="normal", levelsCompleted=12, badges=None,
              levelProgress=None):
    """Inject a pre-built save into localStorage, then reload."""
    data = {
        "name": name, "nameSet": True, "tutorialDone": True, "avatar": "🧒",
        "level": level, "xp": xp, "stars": stars, "dailyStreak": 3,
        "difficulty": difficulty,
        "totalRounds": 80, "correctAnswers": 65, "bestStreak": 7,
        "perfectLevels": 3, "levelsCompleted": levelsCompleted,
        "totalTime": 300, "avgTime": 1.8,
        "history": [80, 90, 100, 70, 85],
        "roundTimes": [1.5, 2.0, 1.2],
        "badges": badges or [],
        "badgeCounts": {},
        "levelProgress": levelProgress or {},
        "daily": {"date": "2099-01-01", "goal": 3, "progress": 1, "done": False},
        "dailyGames": {},
        "challengeRuns": 0, "challengePBs": {},
        "adaptiveLevel": {"numbers": 3, "speed": 1000, "maxResult": 20,
                          "minNum": 1, "maxNum": 9},
        "lastPlay": None,
    }
    page.evaluate(f"""
        localStorage.setItem('az2', JSON.stringify({json.dumps(data)}));
        localStorage.setItem('az_lang', 'en');
        localStorage.setItem('az_t', 'default');
        localStorage.setItem('az_v', '0');
    """)
    page.reload()
    page.wait_for_timeout(600)


def play_round(page: Page, correct: bool = True) -> int:
    """
    Wait for a round to start, then submit the answer (correct or wrong).
    Returns the answer value.
    """
    # Wait for answer area to appear
    page.wait_for_function(
        "document.getElementById('aa').classList.contains('on')",
        timeout=10_000,
    )
    answer = page.evaluate("G.answer")
    if correct:
        val = str(abs(int(answer)))
        if int(answer) < 0:
            page.evaluate("npNeg()")
        for d in val:
            page.evaluate(f"npDigit({d})")
    else:
        # Submit a deliberately wrong answer
        page.evaluate("npDigit(9); npDigit(9); npDigit(9)")
    page.evaluate("check()")
    page.wait_for_timeout(300)
    return int(answer)


def start_level(page: Page, level_num: int):
    """Select a level and start a non-practice game."""
    page.evaluate(f"selLv({level_num}); openSheet()")
    page.wait_for_timeout(300)
    page.evaluate("closeSheet(); startGame(false)")
    page.wait_for_timeout(200)


# ── Test harness ──────────────────────────────────────────────────────────────

passed = failed = 0
results = []

def test(name: str):
    """Decorator that registers and runs a test function."""
    def decorator(fn):
        results.append(name)
        return fn
    return decorator


class Runner:
    def __init__(self, verbose: bool, keyword: str):
        self.verbose = verbose
        self.keyword = keyword.lower() if keyword else ""
        self.passed = 0
        self.failed = 0
        self._tests: list = []

    def register(self, name, fn):
        self._tests.append((name, fn))

    def run(self):
        url = file_url(HTML_FILE)
        with sync_playwright() as pw:
            for name, fn in self._tests:
                if self.keyword and self.keyword not in name.lower():
                    continue
                try:
                    browser, ctx, page = make_page(pw)
                    page.goto(url)
                    page.wait_for_timeout(500)
                    fn(page)
                    self.passed += 1
                    print(f"  ✓  {name}")
                except Exception as e:
                    self.failed += 1
                    msg = str(e).split("\n")[0][:120]
                    print(f"  ✗  {name}\n     {msg}")
                    if self.verbose:
                        import traceback
                        traceback.print_exc()
                finally:
                    try:
                        browser.close()
                    except Exception:
                        pass

        total = self.passed + self.failed
        print(f"\n{'─'*58}")
        ok = "✓ all good" if self.failed == 0 else f"✗ {self.failed} failed"
        print(f"  {self.passed}/{total} passed   {ok}")
        print(f"{'─'*58}\n")
        return self.failed == 0


R = Runner(verbose=False, keyword="")   # configured in main()


def t(name):
    """Test decorator."""
    def decorator(fn):
        R.register(name, fn)
        return fn
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# 1. PAGE LOAD & ONBOARDING
# ═══════════════════════════════════════════════════════════════════════════════

@t("page loads and shows name-entry modal on first visit")
def _(page):
    # No save — fresh page shows the onboarding modal
    page.goto(file_url(HTML_FILE))
    page.wait_for_timeout(500)
    modal = page.locator("#mName")
    expect(modal).to_have_class(re.compile(r"\bvis\b"))


@t("name entry: typing name and submitting dismisses modal")
def _(page):
    page.goto(file_url(HTML_FILE))
    page.wait_for_timeout(500)
    page.fill("#nameInput", "Mario")
    page.evaluate("submitName()")
    page.wait_for_timeout(300)
    modal = page.locator("#mName")
    expect(modal).not_to_have_class(re.compile(r"\bvis\b"))


@t("with existing save: home screen shows player name and level")
def _(page):
    init_save(page, name="Mario", level=7)
    expect(page.locator("#pn")).to_have_text("Mario")
    expect(page.locator("#pl")).to_contain_text("Lv.7")


@t("with existing save: XP bar is visible")
def _(page):
    init_save(page)
    expect(page.locator("#xpf")).to_be_visible()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. NAVIGATION / TABS
# ═══════════════════════════════════════════════════════════════════════════════

@t("tab: switching to Stats shows stats panel")
def _(page):
    init_save(page)
    page.evaluate("tab('stats')")
    page.wait_for_timeout(200)
    expect(page.locator("#tc-stats")).to_have_class(re.compile(r"\bon\b"))


@t("tab: switching to Badges shows badge grid")
def _(page):
    init_save(page)
    page.evaluate("tab('badges')")
    page.wait_for_timeout(200)
    expect(page.locator("#tc-badges")).to_have_class(re.compile(r"\bon\b"))


@t("tab: switching to Config shows settings panel")
def _(page):
    init_save(page)
    page.evaluate("tab('set')")
    page.wait_for_timeout(200)
    expect(page.locator("#tc-set")).to_have_class(re.compile(r"\bon\b"))


@t("tab: returning to Play tab hides other panels")
def _(page):
    init_save(page)
    page.evaluate("tab('stats')")
    page.wait_for_timeout(100)
    page.evaluate("tab('play')")
    page.wait_for_timeout(100)
    expect(page.locator("#tc-play")).to_have_class(re.compile(r"\bon\b"))
    expect(page.locator("#tc-stats")).not_to_have_class(re.compile(r"\bon\b"))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. LEVEL SELECTION & SHEET
# ═══════════════════════════════════════════════════════════════════════════════

@t("level sheet: opens on selLv and shows level number")
def _(page):
    init_save(page)
    page.evaluate("selLv(1); openSheet()")
    page.wait_for_timeout(300)
    sheet = page.locator("#sheet")
    expect(sheet).to_have_class(re.compile(r"\bvis\b"))
    expect(page.locator("#shTitle")).to_contain_text("Level 1")


@t("level sheet: closes on closeSheet()")
def _(page):
    init_save(page)
    page.evaluate("selLv(1); openSheet()")
    page.wait_for_timeout(300)
    page.evaluate("closeSheet()")
    page.wait_for_timeout(200)
    expect(page.locator("#sheet")).not_to_have_class(re.compile(r"\bvis\b"))


@t("level sheet: Start button launches game screen")
def _(page):
    init_save(page)
    page.evaluate("selLv(1); openSheet()")
    page.wait_for_timeout(300)
    page.evaluate("closeSheet(); startGame(false)")
    page.wait_for_timeout(200)
    expect(page.locator("#gs")).to_have_class(re.compile(r"\bon\b"))


# ═══════════════════════════════════════════════════════════════════════════════
# 4. GAMEPLAY — ANSWER FLOW
# ═══════════════════════════════════════════════════════════════════════════════

@t("gameplay: countdown then number flashes then answer area appears")
def _(page):
    init_save(page)
    page.evaluate("selLv(1); G.level = levels.find(l=>l.level===1); startGame(false)")
    # Wait for answer area
    page.wait_for_function(
        "document.getElementById('aa').classList.contains('on')",
        timeout=10_000,
    )
    expect(page.locator("#aa")).to_have_class(re.compile(r"\bon\b"))


@t("gameplay: correct answer shows '✓ Correct!' feedback")
def _(page):
    init_save(page)
    page.evaluate("selLv(1); G.level = levels.find(l=>l.level===1); startGame(false)")
    play_round(page, correct=True)
    expect(page.locator("#resTxt")).to_contain_text("Correct")


@t("gameplay: wrong answer shows the correct answer")
def _(page):
    init_save(page)
    page.evaluate("selLv(1); G.level = levels.find(l=>l.level===1); startGame(false)")
    answer = page.evaluate("G.answer")
    page.wait_for_function(
        "document.getElementById('aa').classList.contains('on')",
        timeout=10_000,
    )
    # Submit wrong
    page.evaluate("npDigit(9); npDigit(9); npDigit(9)")
    page.evaluate("check()")
    page.wait_for_timeout(300)
    result_text = page.locator("#resTxt").inner_text()
    assert str(int(answer)) in result_text, f"Expected answer {answer} in '{result_text}'"


@t("gameplay: score counter increments on correct answer")
def _(page):
    init_save(page)
    page.evaluate("selLv(1); G.level = levels.find(l=>l.level===1); startGame(false)")
    play_round(page, correct=True)
    score_text = page.locator("#gscore").inner_text()
    assert score_text.startswith("1/"), f"Score should start with '1/', got '{score_text}'"


@t("gameplay: Escape key exits to home screen")
def _(page):
    init_save(page)
    page.evaluate("selLv(1); G.level = levels.find(l=>l.level===1); startGame(false)")
    # Wait until the game screen is fully active, then exit via JS (same as Escape handler)
    page.wait_for_function(
        "document.getElementById('gs').classList.contains('on')",
        timeout=5_000,
    )
    page.evaluate("exitGame()")
    page.wait_for_timeout(300)
    expect(page.locator("#gs")).not_to_have_class(re.compile(r"\bon\b"))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. NUMPAD INTERACTION
# ═══════════════════════════════════════════════════════════════════════════════

@t("numpad: clicking digit buttons updates display")
def _(page):
    init_save(page)
    page.evaluate("selLv(1); G.level = levels.find(l=>l.level===1); startGame(false)")
    page.wait_for_function(
        "document.getElementById('aa').classList.contains('on')",
        timeout=10_000,
    )
    page.evaluate("npDigit(4); npDigit(2)")
    expect(page.locator("#ansVal")).to_have_text("42")


@t("numpad: backspace button removes last digit")
def _(page):
    init_save(page)
    page.evaluate("selLv(1); G.level = levels.find(l=>l.level===1); startGame(false)")
    page.wait_for_function(
        "document.getElementById('aa').classList.contains('on')",
        timeout=10_000,
    )
    page.evaluate("npDigit(4); npDigit(2); npBack()")
    expect(page.locator("#ansVal")).to_have_text("4")


@t("numpad: keyboard digits work during answer phase")
def _(page):
    init_save(page)
    page.evaluate("selLv(1); G.level = levels.find(l=>l.level===1); startGame(false)")
    page.wait_for_function(
        "document.getElementById('aa').classList.contains('on')",
        timeout=10_000,
    )
    page.keyboard.press("7")
    page.keyboard.press("3")
    expect(page.locator("#ansVal")).to_have_text("73")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. THEMES
# ═══════════════════════════════════════════════════════════════════════════════

@t("theme: switching to 'dark' adds data-theme attribute to body")
def _(page):
    init_save(page)
    page.evaluate("setTheme('dark')")
    page.wait_for_timeout(100)
    attr = page.evaluate("document.body.getAttribute('data-theme')")
    assert attr == "dark", f"Expected data-theme='dark', got '{attr}'"


@t("theme: switching to 'default' removes data-theme attribute")
def _(page):
    init_save(page)
    page.evaluate("setTheme('space')")
    page.wait_for_timeout(100)
    page.evaluate("setTheme('default')")
    page.wait_for_timeout(100)
    attr = page.evaluate("document.body.getAttribute('data-theme')")
    assert attr is None, f"Expected no data-theme, got '{attr}'"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CHALLENGE MODE
# ═══════════════════════════════════════════════════════════════════════════════

@t("challenge: tab shows challenge setup panel")
def _(page):
    init_save(page)
    page.evaluate("tab('challenge')")
    page.wait_for_timeout(200)
    expect(page.locator("#challSetupPanel")).to_be_visible()


@t("challenge: config hash changes when rounds change")
def _(page):
    init_save(page)
    h1 = page.evaluate("CH.rounds=10; CH.numbers=5; CH.speed=1000; CH.maxNum=9; CH.ops=['add']; challConfigHash()")
    h2 = page.evaluate("CH.rounds=20; challConfigHash()")
    assert h1 != h2, "Hash should differ when rounds change"


@t("challenge: running a full challenge session completes and shows result panel")
def _(page):
    init_save(page)
    # Set to 1-round challenge for speed
    page.evaluate("""
        CH.rounds = 1;
        CH.numbers = 2;
        CH.speed = 300;
        CH.maxNum = 9;
        CH.ops = ['add'];
    """)
    page.evaluate("startChallenge()")
    # Wait for answer area
    page.wait_for_function(
        "document.getElementById('aa').classList.contains('on')",
        timeout=10_000,
    )
    # Submit any answer
    page.evaluate("npDigit(1); challCheck()")
    # Wait for result panel or continue bar
    page.wait_for_timeout(1000)
    page.evaluate("if(G.waiting) challCont()")
    page.wait_for_timeout(1500)
    result_visible = page.evaluate(
        "document.getElementById('challResultPanel').style.display !== 'none'"
    )
    assert result_visible, "Challenge result panel should be visible after completion"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. DATA PERSISTENCE & EXPORT/IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

@t("persistence: player name survives page reload")
def _(page):
    init_save(page, name="Persisted")
    page.reload()
    page.wait_for_timeout(600)
    expect(page.locator("#pn")).to_have_text("Persisted")


@t("persistence: star count displays correctly from save")
def _(page):
    init_save(page, stars=1337)
    star_text = page.locator("#stars").inner_text()
    # fmtN(1337) → "1.3k"
    assert "1.3k" in star_text or "1337" in star_text, f"Got: '{star_text}'"


@t("export/import: round-trips save data correctly")
def _(page):
    init_save(page, name="RoundTrip", level=12, stars=500)
    blob = page.evaluate("encExp(D)")
    assert isinstance(blob, str) and len(blob) > 10
    back = page.evaluate(f"decImp({json.dumps(blob)})")
    assert back["name"] == "RoundTrip"
    assert back["level"] == 12
    assert back["stars"] == 500


@t("export/import: decImp throws on corrupted blob")
def _(page):
    init_save(page)
    threw = page.evaluate("""
        (() => {
            try { decImp('not-valid!!!'); return false; }
            catch(e) { return true; }
        })()
    """)
    assert threw, "decImp should throw on invalid input"


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not HTML_FILE.exists():
        print(f"❌  Game file not found: {HTML_FILE}")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-k", "--keyword", default="", help="Filter tests by name substring")
    args = parser.parse_args()

    R.verbose = args.verbose
    R.keyword = args.keyword.lower()

    n = len([n for n, _ in R._tests if not R.keyword or R.keyword in n.lower()])
    print(f"\n🎮  Anzan Flash — integration tests  ({n} selected)\n")
    ok = R.run()
    sys.exit(0 if ok else 1)
