#!/usr/bin/env python3
"""
generate_media.py — Anzan Flash screenshot & GIF generator
Produces ready-to-use GitHub repo media assets.

Usage:
    python3 generate_media.py [path/to/anzan_flash.html]

Output (./media/):
    screenshots/  — static PNG screenshots
    gifs/         — animated GIF walkthroughs
"""

import sys, os, time, shutil, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────
HTML_FILE  = sys.argv[1] if len(sys.argv) > 1 else "anzan_flash.html"
OUT_DIR    = Path("media")
SS_DIR     = OUT_DIR / "screenshots"
GIF_DIR    = OUT_DIR / "gifs"
VIEWPORT   = {"width": 390, "height": 844}   # iPhone 14 Pro viewport
GIF_FPS    = 8                                 # frames per second for GIFs

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_dirs():
    for d in [SS_DIR, GIF_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def file_url(path: str) -> str:
    return "file://" + os.path.abspath(path)


def snap(page, name: str, description: str = "") -> Path:
    """Take a screenshot and save it."""
    dest = SS_DIR / f"{name}.png"
    page.screenshot(path=str(dest))
    label = f"  📸  {name}.png" + (f"  ({description})" if description else "")
    print(label)
    return dest


def frames_to_gif(frames: list[Path], dest: Path, fps: int = GIF_FPS,
                  loop: int = 0, scale: float = 1.0):
    """Convert a list of PNG paths to an animated GIF."""
    imgs = []
    for f in frames:
        img = Image.open(f).convert("RGBA")
        if scale != 1.0:
            w, h = img.size
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        # GIF needs palette mode
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        imgs.append(bg.convert("P", palette=Image.ADAPTIVE, colors=256))
    duration_ms = int(1000 / fps)
    imgs[0].save(
        dest,
        save_all=True,
        append_images=imgs[1:],
        duration=duration_ms,
        loop=loop,
        optimize=False,
    )
    kb = dest.stat().st_size // 1024
    print(f"  🎞   {dest.name}  ({len(frames)} frames, {kb} KB)")


def stub_external_libs(page):
    """Inject stubs for CDN-loaded libs (Chart.js) that won't load in file:// context."""
    page.evaluate("""
        if (typeof Chart === 'undefined') {
            window.Chart = function(el, cfg) {
                this.data = cfg.data;
                this.update = function(){};
            };
        }
    """)


def init_game(page, name="Demo", avatar="🧒"):
    """Bypass the name-entry screen by injecting saved data into localStorage."""
    data = {
        "name": name,
        "nameSet": True,
        "tutorialDone": True,
        "avatar": avatar,
        "level": 5,
        "xp": 120,
        "stars": 250,
        "dailyStreak": 3,
        "difficulty": "normal",
        "levelsCompleted": 12,
        "totalRounds": 85,
        "correctAnswers": 72,
        "bestStreak": 7,
        "daily": {"date": "2099-01-01", "goal": 3, "progress": 1, "done": False},
        "badges": [],
        "badgeCounts": {},
        "roundTimes": [],
        "avgTime": 0,
        "adaptiveLevel": {"numbers": 3, "speed": 1000, "maxResult": 20,
                          "minNum": 1, "maxNum": 9},
    }
    import json
    page.evaluate(f"""
        localStorage.setItem('az2', JSON.stringify({json.dumps(data)}));
        localStorage.setItem('az_lang', 'en');
        localStorage.setItem('az_t', 'default');
        localStorage.setItem('az_v', '0.0');
    """)
    page.reload()
    page.wait_for_timeout(800)


def select_level(page, level_number: int):
    """Click on a world card, then a level button in the list."""
    # Find and click the level button in the level grid
    page.evaluate(f"""
        const lev = levels.find(l => l.level === {level_number});
        if (lev) {{
            curWorld = lev.world;
            G.level = lev;
            renderLevels();
            renderWorlds();
        }}
    """)
    page.wait_for_timeout(300)
    # Click the matching level card
    page.evaluate(f"""
        const btn = document.querySelector('.lvb[data-lv="{level_number}"]');
        if (btn) btn.click();
    """)
    page.wait_for_timeout(400)


# ── Screenshots ───────────────────────────────────────────────────────────────

def screenshot_home(page):
    print("\n── Home Screen ──────────────────────────────────────────────────")
    snap(page, "01_home", "main menu / world carousel")


def screenshot_themes(page):
    print("\n── Themes ───────────────────────────────────────────────────────")
    themes = ["ocean", "forest", "sunset", "candy", "space", "dark"]
    for th in themes:
        page.evaluate(f"setTheme('{th}')")
        page.wait_for_timeout(250)
        snap(page, f"theme_{th}", f"{th} theme")
    page.evaluate("setTheme('default')")
    page.wait_for_timeout(250)


def screenshot_stats_tab(page):
    print("\n── Stats Tab ────────────────────────────────────────────────────")
    page.evaluate("tab('stats')")
    page.wait_for_timeout(300)
    snap(page, "05_stats", "statistics tab")
    page.evaluate("tab('play')")
    page.wait_for_timeout(200)


def screenshot_badges_tab(page):
    print("\n── Badges Tab ───────────────────────────────────────────────────")
    page.evaluate("tab('badges')")
    page.wait_for_timeout(300)
    snap(page, "06_badges", "badges / trophies tab")
    page.evaluate("tab('play')")
    page.wait_for_timeout(200)


def screenshot_settings(page):
    print("\n── Settings ─────────────────────────────────────────────────────")
    page.evaluate("tab('set')")
    page.wait_for_timeout(300)
    snap(page, "07_settings", "settings panel")
    page.evaluate("tab('play')")
    page.wait_for_timeout(200)


def screenshot_level_sheet(page, level_number=3):
    print("\n── Level Detail Sheet ───────────────────────────────────────────")
    page.evaluate(f"selLv({level_number}); openSheet()")
    page.wait_for_timeout(500)
    snap(page, "04_level_sheet", "level detail / start sheet")
    page.evaluate("closeSheet()")
    page.wait_for_timeout(300)


def screenshot_game_sequence(page, level_number=3):
    """Start a game and capture: countdown → flash → answer → result."""
    print("\n── In-Game Sequence ─────────────────────────────────────────────")

    page.evaluate(f"""
        const lev = levels.find(l => l.level === {level_number});
        if (lev) {{ G.level = lev; startGame(false); }}
    """)
    page.wait_for_timeout(200)
    snap(page, "08_countdown", "3-2-1 countdown")

    # Wait for "GO!" flash start
    page.wait_for_timeout(500)
    snap(page, "09_flashing", "number flashing")

    # Wait for the numbers to finish and answer area to appear
    page.wait_for_function("document.getElementById('aa').classList.contains('on')",
                           timeout=8000)
    snap(page, "10_answer_prompt", "answer input with numpad")

    # Type correct answer via numpad
    answer = page.evaluate("G.answer")
    print(f"     answer = {answer}")
    answer_str = str(abs(int(answer)))
    if int(answer) < 0:
        page.evaluate("npNeg()")
        page.wait_for_timeout(80)
    for digit in answer_str:
        page.evaluate(f"npDigit({digit})")
        page.wait_for_timeout(80)

    # Submit
    page.evaluate("check()")
    page.wait_for_timeout(600)
    snap(page, "11_result", "correct/wrong result feedback")


# ── GIFs ──────────────────────────────────────────────────────────────────────

def gif_gameplay(page, level_number=3, scale=0.7):
    """Record a full round: countdown → flashes → answer → result."""
    print("\n── GIF: gameplay round ──────────────────────────────────────────")

    tmp = Path(tempfile.mkdtemp(prefix="gif_gameplay_"))

    page.evaluate(f"""
        const lev = levels.find(l => l.level === {level_number});
        if (lev) {{ G.level = lev; startGame(false); }}
    """)

    frames: list[Path] = []

    def capture(tag=""):
        p = tmp / f"f{len(frames):04d}_{tag}.png"
        page.screenshot(path=str(p))
        frames.append(p)

    # Countdown (grab every ~120 ms for ~1.5 s)
    for _ in range(12):
        capture("cd")
        page.wait_for_timeout(120)

    # Flashing numbers
    page.wait_for_function(
        "document.getElementById('nd').textContent !== '' && "
        "!document.getElementById('nd').querySelector('.cd')",
        timeout=3000,
    )
    for _ in range(20):
        capture("fl")
        page.wait_for_timeout(100)

    # Wait for answer area
    page.wait_for_function("document.getElementById('aa').classList.contains('on')",
                           timeout=8000)
    for _ in range(4):
        capture("aa")
        page.wait_for_timeout(80)

    # Type answer
    answer = page.evaluate("G.answer")
    if int(answer) < 0:
        page.evaluate("npNeg()")
        page.wait_for_timeout(120)
        capture("ty")
    for digit in str(abs(int(answer))):
        page.evaluate(f"npDigit({digit})")
        page.wait_for_timeout(120)
        capture("ty")

    # Submit
    page.evaluate("check()")
    for _ in range(10):
        capture("res")
        page.wait_for_timeout(100)

    dest = GIF_DIR / "gameplay_round.gif"
    frames_to_gif(frames, dest, fps=GIF_FPS, scale=scale)
    shutil.rmtree(tmp)


def gif_theme_switcher(page, scale=0.6):
    """Cycle through colour themes on the home screen."""
    print("\n── GIF: theme switcher ──────────────────────────────────────────")

    tmp = Path(tempfile.mkdtemp(prefix="gif_themes_"))
    frames: list[Path] = []

    def capture():
        p = tmp / f"f{len(frames):04d}.png"
        page.screenshot(path=str(p))
        frames.append(p)

    # Navigate to settings for the theme buttons
    page.evaluate("tab('set')")
    page.wait_for_timeout(400)

    themes = ["default", "ocean", "forest", "sunset", "candy", "space", "dark", "default"]
    for th in themes:
        page.evaluate(f"setTheme('{th}')")
        for _ in range(6):        # hold each theme ~6 frames
            capture()
            page.wait_for_timeout(80)

    page.evaluate("setTheme('default'); tab('play')")
    page.wait_for_timeout(200)

    dest = GIF_DIR / "themes.gif"
    frames_to_gif(frames, dest, fps=6, scale=scale)
    shutil.rmtree(tmp)


def gif_number_flash(page, level_number=5, scale=0.75):
    """Tight GIF showing just the number-flashing phase."""
    print("\n── GIF: number flash close-up ───────────────────────────────────")

    tmp = Path(tempfile.mkdtemp(prefix="gif_flash_"))
    frames: list[Path] = []

    def capture():
        p = tmp / f"f{len(frames):04d}.png"
        page.screenshot(path=str(p))
        frames.append(p)

    page.evaluate(f"""
        const lev = levels.find(l => l.level === {level_number});
        if (lev) {{ G.level = lev; startGame(false); }}
    """)

    # Skip past countdown
    page.wait_for_function(
        "document.getElementById('nd').textContent !== '' && "
        "!document.getElementById('nd').querySelector('.cd')",
        timeout=5000,
    )

    # Record until answer area appears
    deadline = time.time() + 6
    while time.time() < deadline:
        if page.evaluate("document.getElementById('aa').classList.contains('on')"):
            break
        capture()
        page.wait_for_timeout(60)

    # Capture 8 more frames of the answer screen
    for _ in range(8):
        capture()
        page.wait_for_timeout(80)

    if len(frames) < 4:
        print("  ⚠  too few frames captured — skipping flash GIF")
        shutil.rmtree(tmp)
        return

    dest = GIF_DIR / "number_flash.gif"
    frames_to_gif(frames, dest, fps=10, scale=scale)
    shutil.rmtree(tmp)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(HTML_FILE):
        print(f"❌  File not found: {HTML_FILE}")
        sys.exit(1)

    make_dirs()
    url = file_url(HTML_FILE)
    print(f"🎮  Anzan Flash — media generator")
    print(f"    source : {HTML_FILE}")
    print(f"    output : {OUT_DIR}/")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=2,    # retina-quality PNGs
        )
        # Stub Chart.js before any page script runs (CDN unavailable in file:// context)
        ctx.add_init_script("""
            window.Chart = function(el, cfg) {
                this.data = (cfg || {}).data || {labels:[], datasets:[{data:[]}]};
                this.update = function(){};
                this.destroy = function(){};
            };
            window.Chart.register = function(){};
        """)
        page = ctx.new_page()

        # ── Load and init ──────────────────────────────────────────────────
        page.goto(url)
        page.wait_for_timeout(600)
        init_game(page)

        # ── Static screenshots ─────────────────────────────────────────────
        screenshot_home(page)
        screenshot_level_sheet(page, level_number=3)
        screenshot_stats_tab(page)
        screenshot_badges_tab(page)
        screenshot_settings(page)
        screenshot_themes(page)
        screenshot_game_sequence(page, level_number=3)

        # ── Reload for clean GIF state ─────────────────────────────────────
        page.goto(url)
        page.wait_for_timeout(600)
        init_game(page)

        # ── Animated GIFs ──────────────────────────────────────────────────
        gif_theme_switcher(page, scale=0.6)

        page.goto(url)
        page.wait_for_timeout(600)
        init_game(page)
        gif_gameplay(page, level_number=4, scale=0.65)

        page.goto(url)
        page.wait_for_timeout(600)
        init_game(page)
        gif_number_flash(page, level_number=6, scale=0.75)

        browser.close()

    # ── Summary ────────────────────────────────────────────────────────────
    pngs = list(SS_DIR.glob("*.png"))
    gifs = list(GIF_DIR.glob("*.gif"))
    print(f"\n✅  Done!  {len(pngs)} screenshots  +  {len(gifs)} GIFs")
    print(f"   {SS_DIR}/")
    for f in sorted(pngs):
        print(f"     {f.name}")
    print(f"   {GIF_DIR}/")
    for f in sorted(gifs):
        kb = f.stat().st_size // 1024
        print(f"     {f.name}  ({kb} KB)")

    print("""
── Suggested README usage ──────────────────────────────────────────────────
  ![Home](media/screenshots/01_home.png)
  ![Gameplay](media/gifs/gameplay_round.gif)
  ![Themes](media/gifs/themes.gif)
  ![Flash](media/gifs/number_flash.gif)
────────────────────────────────────────────────────────────────────────────
""")


if __name__ == "__main__":
    main()
