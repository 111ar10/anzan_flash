# Testing Manual — Anzan Flash

Two test suites: **unit tests** (pure logic, Node.js) and **integration tests** (full browser, Playwright + Python). They are independent and can be run in any order.

---

## Quick Start

```bash
# Unit tests — no setup needed
node test_unit.js

# Integration tests — one-time setup
pip install playwright pillow
python -m playwright install chromium

python3 test_integration.py
```

---

## Unit Tests (`test_unit.js`)

### Requirements

- Node.js 16+ (no npm packages needed)

### Running

```bash
# Normal run — shows summary only
node test_unit.js

# Verbose — prints every test name as it passes
node test_unit.js --verbose
```

### What is tested

| Section | Tests | Description |
|---|---|---|
| XP Formula | 5 | Level-to-XP curve, monotonic growth |
| Rank System | 11 | All 18 rank boundaries, rank-up detection |
| Mastery | 10 | Diamond/Gold/Silver/Bronze thresholds and edge cases |
| Level Generation | 10 | All 150 levels: count, world assignment, speed floors, mix pools |
| Difficulty Presets | 8 | Speed direction, number count, clamping, minSpeed, XP multipliers |
| Number Generation | 12 | `genAddSub`, `genMult`, `genDiv` — answer correctness, sign rules |
| Stars / Accuracy | 6 | 0/1/2/3-star boundaries, rounding |
| Export / Import | 6 | Round-trip, tampered checksum, `cksum` determinism |
| Numpad Logic | 9 | Digit entry, zero handling, backspace, negative toggle, 6-digit cap |
| Badge Conditions | 20 | 20 badge predicates tested at boundary values |
| Challenge Hash | 3 | Same config = same hash, mutation changes it, ops order-insensitive |
| Utility Functions | 8 | `fmtN`, `fmtTime`, `rnd`, `todayStr` |

### How it works

The harness extracts the `<script>` block from `anzan_flash.html` and evals it inside Node with minimal stubs (a fake `document`, `localStorage`, etc.) so that the game's logic functions are available without a browser. DOM-touching functions (`renderAll`, `saveD`, `playS`, …) are replaced with no-ops. Tests then call game functions directly and assert on their return values.

**Key detail:** `applyDifficulty` reads `D` by closure — the harness mutates `D` in-place rather than reassigning it, so the game's internal reference stays valid.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | All tests passed |
| `1` | One or more tests failed |

---

## Integration Tests (`test_integration.py`)

### Requirements

- Python 3.9+
- Playwright for Python + Chromium browser

```bash
pip install playwright
python -m playwright install chromium
```

### Running

```bash
# Run all 28 tests
python3 test_integration.py

# Verbose — full traceback on failure
python3 test_integration.py -v

# Filter by name substring (case-insensitive)
python3 test_integration.py -k challenge
python3 test_integration.py -k "numpad or theme"
python3 test_integration.py -k persistence
```

### What is tested

| Section | Tests | Description |
|---|---|---|
| Page Load & Onboarding | 4 | Fresh load shows name modal; submitting it dismisses the modal; save restores name + level |
| Navigation / Tabs | 4 | All 4 tabs switch correctly; returning to Play cleans up others |
| Level Sheet | 3 | Opens with correct level info, closes, triggers game start |
| Gameplay Flow | 5 | Countdown → flash → answer area; correct/wrong feedback; score counter; exit |
| Numpad | 3 | Click digits, backspace, keyboard input during answer phase |
| Themes | 2 | `data-theme` attribute set on body / removed for default |
| Challenge Mode | 3 | Setup panel visible, hash changes with config, full session completes |
| Data Persistence | 2 | Name and stars survive reload |
| Export / Import | 2 | Round-trip via `encExp`/`decImp`; corrupted blob throws |

### How it works

Each test gets a **fresh browser page**. `init_save()` injects a pre-built JSON save into `localStorage` and reloads, so every test starts from a known state without navigating through onboarding. Chart.js is stubbed via `add_init_script` (the CDN is unavailable in `file://` context). Game functions are called directly via `page.evaluate()` where waiting for animations would be slow; Playwright `expect()` assertions are used for DOM state checks.

### Adjusting timeouts and headless mode

At the top of `test_integration.py`:

```python
HEADLESS = True    # set False to watch tests run in a visible browser window
SLOW_MO  = 0      # ms delay between Playwright actions — increase for debugging
TIMEOUT  = 8_000  # default element timeout in ms
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | All (selected) tests passed |
| `1` | One or more tests failed |

---

## Generating Repo Screenshots & GIFs

The media generator is a separate script — not a test, but uses the same Playwright setup:

```bash
python3 generate_media.py anzan_flash.html
```

Output goes to `media/screenshots/` (15 PNG files) and `media/gifs/` (3 animated GIFs). Re-run it any time the game UI changes.

---

## Troubleshooting

**`playwright` command not found (Windows)**
Use `python -m playwright install chromium` instead of `playwright install chromium`. See the PATH note in the project root.

**`Chart is not defined` error in integration tests**
The tests stub Chart.js automatically. If you see this error, make sure you are running the tests from the project directory so `anzan_flash.html` is found at the expected path.

**Unit tests: `Could not extract <script> block`**
The harness looks for the `<script>` tag immediately before `</body>`. If you have added additional inline scripts, update the regex in `test_unit.js` accordingly.

**Integration tests timing out**
Slow machines may need a larger `TIMEOUT` value in `test_integration.py`, or you can set `SLOW_MO = 50` to help Playwright keep up with the page.

**A test that should pass is failing after a code change**
Run the unit tests first — they're faster and cover the same logic functions. If the logic is correct but the integration test still fails, set `HEADLESS = False` and add `page.pause()` inside the failing test to inspect the browser state interactively.

---

## Adding New Tests

### Unit test

Add a `test(...)` call anywhere in `test_unit.js` after the eval block:

```js
test("my new test", () => {
    assertEqual(someGameFunction(input), expectedOutput);
});
```

Use the existing helpers: `assert`, `assertEqual`, `assertApprox`, `assertInRange`.

### Integration test

Add a function decorated with `@t(...)` anywhere in `test_integration.py`:

```python
@t("my new integration test")
def _(page):
    init_save(page)
    page.evaluate("someGameFunction()")
    expect(page.locator("#someElement")).to_have_text("expected text")
```

The test runner picks up all registered functions in declaration order. No imports or registration calls needed beyond the decorator.
