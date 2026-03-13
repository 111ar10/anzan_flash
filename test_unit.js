#!/usr/bin/env node
/**
 * test_unit.js — Anzan Flash unit tests
 * Pure logic only — no browser, no DOM, no Playwright.
 *
 * Usage:
 *   node test_unit.js
 *   node test_unit.js --verbose
 */

"use strict";

const VERBOSE = process.argv.includes("--verbose");
const fs = require("fs");

// ── Minimal stubs so the game script can be eval'd without a browser ─────────
const localStorage = { _s: {}, getItem: k => localStorage._s[k] ?? null, setItem: (k, v) => { localStorage._s[k] = v } };
const document = {
    getElementById:     () => ({ textContent: "", style: {}, classList: { add(){}, remove(){}, toggle(){}, contains:()=>false }, innerHTML: "" }),
    querySelectorAll:   () => ({ forEach: () => {} }),
    querySelector:      () => null,
    addEventListener:   () => {},
    readyState:         "complete",
};
const window = { AudioContext: null, webkitAudioContext: null };
// Silence init side-effects
const _noop = () => {};
global.localStorage = localStorage;
global.document = document;
global.window = window;
global.btoa  = s => Buffer.from(s, "binary").toString("base64");
global.atob  = s => Buffer.from(s, "base64").toString("binary");
// encodeURIComponent / decodeURIComponent are already globals in Node
global.unescape  = s => decodeURIComponent(s.replace(/%(?![\da-fA-F]{2})/g, '%25'));
global.escape    = s => encodeURIComponent(s).replace(/%20/g, '+');

// Patch init-time DOM calls so they don't throw
const html = fs.readFileSync(require("path").join(__dirname, "anzan_flash.html"), "utf8");
// Extract only the <script> block (everything between <script> and </script>)
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>\s*<\/body>/);
if (!scriptMatch) { console.error("Could not extract <script> block"); process.exit(1); }

// Wrap in a function so top-level returns don't break and suppress init call
let src = scriptMatch[1];
// Suppress the auto-init at the bottom so we control state
src = src.replace(/document\.addEventListener\('DOMContentLoaded',safeInit\);[\s\S]*$/, "");
src = src.replace(/^function safeInit[\s\S]*?^}/m, "function safeInit(){}");

// Inject saveD/loadD/renderAll/updUI/renderLevels/renderWorlds/renderBadges/renderTip/celebrate/toast/setupKB/initAudio stubs
src += `
// ── stubs injected by test harness ──
function saveD(){}
function renderAll(){}
function updUI(){}
function renderLevels(){}
function renderWorlds(){}
function renderBadges(){}
function renderTip(){}
function renderRankCard(){}
function celebrate(){}
function toast(){}
function setupKB(){}
function initAudio(){}
function initSheetSwipe(){}
function showBadgesM(){}
function openSheet(){}
function closeSheet(){}
function playS(){}
function updChart(){}
function updDaily(){}
function drawDots(){}
function enterGameScreen(){}
function exitGameScreen(){}
function showAnswerArea(){}
function hideAnswerArea(){}
function showContinueBar(){}
function showComplete(){}
function showLvlUps(){}
function showBadgesModal(){}
function showNameEntry(){}
function showTutorial(){}
function setTheme(){}
function setDifficulty(k){ D.difficulty = DIFFICULTIES[k] ? k : 'normal'; }
`;

// Expose all game globals to the outer scope after eval
src += `
// ── expose to Node global scope ──
Object.assign(global, {
    levels, RANKS, BADGES, DIFFICULTIES, DIFF_DESC, ANZAN_TYPES,
    TR, NEG_TYPES, CH, G, D,
    getXP, getRank, getRankTitle, isRankUp,
    getMastery, masteryIcon, masteryName,
    applyDifficulty, setDifficulty,
    genAddSub, genMult, genDiv,
    encExp, decImp, cksum,
    fmtN, fmtTime, rnd, todayStr,
    npDigit, npBack, npNeg, clearNP,
    challConfigHash,
    checkBadges, addXP,
    npCurrent: undefined,  // special — we reference this by name
});
// npCurrent is a simple let; we need to proxy it
Object.defineProperty(global, 'npCurrent', {
    get(){ return npCurrent; },
    set(v){ npCurrent = v; },
    configurable: true,
});
`;


try {
    eval(src);
} catch (e) {
    console.error("Failed to eval game source:", e.message);
    process.exit(1);
}
let passed = 0, failed = 0, skipped = 0;
const results = [];

function test(name, fn) {
    try {
        fn();
        passed++;
        results.push({ ok: true, name });
        if (VERBOSE) console.log(`  ✓  ${name}`);
    } catch (e) {
        failed++;
        results.push({ ok: false, name, err: e.message });
        console.log(`  ✗  ${name}\n     ${e.message}`);
    }
}

function assert(cond, msg = "assertion failed") {
    if (!cond) throw new Error(msg);
}

function assertEqual(a, b, msg) {
    if (a !== b) throw new Error(msg ?? `expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`);
}

function assertApprox(a, b, eps = 1e-9, msg) {
    if (Math.abs(a - b) > eps) throw new Error(msg ?? `expected ~${b}, got ${a}`);
}

function assertInRange(v, lo, hi, msg) {
    if (v < lo || v > hi) throw new Error(msg ?? `${v} not in [${lo}, ${hi}]`);
}

// Reset D to a clean state before tests that mutate it.
// IMPORTANT: must mutate in-place — applyDifficulty closes over the original D object.
function freshD() {
    const clean = {
        name: "Test", nameSet: true, tutorialDone: true, avatar: "🧒",
        level: 1, xp: 0, stars: 0, dailyStreak: 0, lastPlay: null,
        difficulty: "normal",
        totalRounds: 0, correctAnswers: 0, bestStreak: 0, perfectLevels: 0,
        levelsCompleted: 0, totalTime: 0, avgTime: 0,
        history: [], roundTimes: [],
        badges: [], badgeCounts: {},
        levelProgress: {},
        daily: { date: null, goal: 3, progress: 0, done: false },
        dailyGames: {},
        challengeRuns: 0, challengePBs: {},
        adaptiveLevel: { numbers: 3, speed: 1000, maxResult: 20, minNum: 1, maxNum: 9 },
    };
    Object.keys(D).forEach(k => delete D[k]);
    Object.assign(D, clean);
}


// ═══════════════════════════════════════════════════════════════════════════════
// 1. XP FORMULA
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── XP Formula ───────────────────────────────────────────────────");

test("level 1 XP = 200", () => assertEqual(getXP(1), 200));
test("level 2 XP = floor(200 * 1.18^1) = 236", () => assertEqual(getXP(2), 236));
test("level 10 XP = floor(200 * 1.18^9)", () => {
    assertEqual(getXP(10), Math.floor(200 * Math.pow(1.18, 9)));
});
test("XP strictly increases with level", () => {
    for (let l = 1; l < 100; l++) assert(getXP(l + 1) > getXP(l), `XP[${l+1}] <= XP[${l}]`);
});
test("level 100 XP is very large (>1 million)", () => assert(getXP(100) > 1_000_000));


// ═══════════════════════════════════════════════════════════════════════════════
// 2. RANK SYSTEM
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── Rank System ──────────────────────────────────────────────────");

test("level 1 = 🐣 Beginner", () => assertEqual(getRank(1).icon, "🐣"));
test("level 2 = 🐣 Beginner", () => assertEqual(getRank(2).icon, "🐣"));
test("level 3 = 🌱 Learner",  () => assertEqual(getRank(3).icon, "🌱"));
test("level 5 = 📖 Apprentice",() => assertEqual(getRank(5).icon, "📖"));
test("level 50 = 💎 Diamond",  () => assertEqual(getRank(50).icon, "💎"));
test("level 100 = 🧙 Anzan Sage",() => assertEqual(getRank(100).icon, "🧙"));
test("level 999 = 🧙 Anzan Sage",() => assertEqual(getRank(999).icon, "🧙"));
test("every level 1-120 has a rank", () => {
    for (let l = 1; l <= 120; l++) assert(getRank(l), `no rank for level ${l}`);
});
test("isRankUp detects level 2→3", () => assert(isRankUp(2, 3)));
test("isRankUp no change within same rank (1→2)", () => assert(!isRankUp(1, 2)));
test("isRankUp detects 49→50 (Rocketeer→Diamond)", () => assert(isRankUp(49, 50)));


// ═══════════════════════════════════════════════════════════════════════════════
// 3. MASTERY CALCULATION
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── Mastery ──────────────────────────────────────────────────────");

test("100% + avg<3s → diamond", () => assertEqual(getMastery(100, 2.9), "diamond"));
test("100% + avg==3s → gold (not diamond)", () => assertEqual(getMastery(100, 3.0), "gold"));
test("100% + avg>3s → gold",   () => assertEqual(getMastery(100, 5), "gold"));
test("80% → silver",           () => assertEqual(getMastery(80, 5), "silver"));
test("85% → silver",           () => assertEqual(getMastery(85, 5), "silver"));
test("99% → silver",           () => assertEqual(getMastery(99, 5), "silver"));
test("60% → bronze",           () => assertEqual(getMastery(60, 5), "bronze"));
test("75% → bronze",           () => assertEqual(getMastery(75, 5), "bronze"));
test("59% → null",             () => assertEqual(getMastery(59, 5), null));
test("0% → null",              () => assertEqual(getMastery(0, 5), null));


// ═══════════════════════════════════════════════════════════════════════════════
// 4. LEVEL GENERATION
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── Level Generation ─────────────────────────────────────────────");

test("exactly 150 levels generated", () => assertEqual(levels.length, 150));
test("levels are numbered 1–150", () => {
    for (let i = 0; i < 150; i++) assertEqual(levels[i].level, i + 1, `level[${i}].level`);
});
test("15 worlds, each containing 10 levels", () => {
    for (let w = 1; w <= 15; w++) {
        const wl = levels.filter(l => l.world === w);
        assertEqual(wl.length, 10, `world ${w} has ${wl.length} levels`);
    }
});
test("no level has speed below 280ms (normal floor)", () => {
    levels.forEach(l => assert(l.speed >= 280, `level ${l.level} speed=${l.speed}`));
});
test("all levels have at least 1 round", () => {
    levels.forEach(l => assert(l.rounds >= 1, `level ${l.level}`));
});
test("all levels have minNum < maxNum", () => {
    levels.forEach(l => assert(l.minNum < l.maxNum, `level ${l.level}: min=${l.minNum} max=${l.maxNum}`));
});
test("world 11 (multiplication) uses mult type", () => {
    const w11 = levels.filter(l => l.world === 11);
    w11.forEach(l => assertEqual(l.anzanType, "multiplication", `level ${l.level}`));
});
test("world 12 (division) uses division type", () => {
    const w12 = levels.filter(l => l.world === 12);
    w12.forEach(l => assertEqual(l.anzanType, "division", `level ${l.level}`));
});
test("early levels (1-4 per world) have no mix pool", () => {
    levels.filter(l => l.level % 10 <= 4 && l.level % 10 > 0).forEach(l => {
        assert(!l.effectiveType || !l.effectiveType.startsWith("mix:"),
            `level ${l.level} should not be mixed`);
    });
});
test("later levels (5-10 per world) have mix pool (except world 1)", () => {
    levels.filter(l => l.world > 1 && l.level % 10 >= 5).forEach(l => {
        assert(l.poolTypes && l.poolTypes.length > 0, `level ${l.level} has no pool`);
    });
});


// ═══════════════════════════════════════════════════════════════════════════════
// 5. DIFFICULTY PRESETS
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── Difficulty Presets ───────────────────────────────────────────");

// Level 1: base speed=1750, numbers=2, maxNum=5
const BASE = levels[0];

test("normal: speed unchanged, numbers unchanged", () => {
    freshD(); D.difficulty = "normal";
    const r = applyDifficulty({...BASE});
    assertEqual(r.speed,   Math.max(Math.round(BASE.speed * 1.0), 280));
    assertEqual(r.numbers, Math.min(Math.max(1, BASE.numbers + 0), 15));
});
test("beginner: speed is SLOWER (larger ms value)", () => {
    freshD(); D.difficulty = "beginner";
    const r = applyDifficulty({...BASE});
    // speedMult=1.6 → 1750*1.6=2800 > 1750
    assert(r.speed > BASE.speed, `beginner speed ${r.speed} should be > base ${BASE.speed}`);
});
test("elite: speed is FASTER (smaller ms value)", () => {
    freshD(); D.difficulty = "elite";
    const r = applyDifficulty({...BASE});
    // speedMult=0.25 → 1750*0.25=438 < 1750
    assert(r.speed < BASE.speed, `elite speed ${r.speed} should be < base ${BASE.speed}`);
});
test("elite: more numbers than base", () => {
    freshD(); D.difficulty = "elite";
    const r = applyDifficulty({...BASE});
    // extraNums=+4 → 2+4=6 > 2
    assert(r.numbers > BASE.numbers, `elite numbers ${r.numbers} should be > base ${BASE.numbers}`);
});
test("beginner: fewer numbers (clamped to ≥1)", () => {
    freshD(); D.difficulty = "beginner";
    const r = applyDifficulty({...BASE});
    assert(r.numbers >= 1);
});
test("numbers always clamped to [1, 15]", () => {
    Object.keys(DIFFICULTIES).forEach(d => {
        freshD(); D.difficulty = d;
        levels.forEach(l => {
            const r = applyDifficulty({...l});
            assertInRange(r.numbers, 1, 15, `${d} level ${l.level} numbers=${r.numbers}`);
        });
    });
});
test("speed always ≥ minSpeed for each tier", () => {
    Object.entries(DIFFICULTIES).forEach(([key, diff]) => {
        freshD(); D.difficulty = key;
        levels.forEach(l => {
            const r = applyDifficulty({...l});
            assert(r.speed >= diff.minSpeed,
                `${key} level ${l.level} speed=${r.speed} < minSpeed=${diff.minSpeed}`);
        });
    });
});
test("elite xpMult (2.5) > competition (1.5) > normal (1.0) > beginner (0.6)", () => {
    assert(DIFFICULTIES.elite.xpMult > DIFFICULTIES.competition.xpMult);
    assert(DIFFICULTIES.competition.xpMult > DIFFICULTIES.normal.xpMult);
    assert(DIFFICULTIES.normal.xpMult > DIFFICULTIES.beginner.xpMult);
});


// ═══════════════════════════════════════════════════════════════════════════════
// 6. NUMBER GENERATION
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── Number Generation ────────────────────────────────────────────");

test("genAddSub answer = sum of signed nums", () => {
    for (let i = 0; i < 50; i++) {
        const r = genAddSub(4, 1, 9, 50, false);
        const sum = r.dispNums.reduce((acc, n, idx) => acc + (r.isNeg[idx] ? -n : n), 0);
        assertEqual(r.answer, sum, `answer mismatch: got ${r.answer}, expected ${sum}`);
    }
});
test("genAddSub: first number is never negative", () => {
    for (let i = 0; i < 50; i++) {
        const r = genAddSub(5, 1, 9, 100, true);
        assert(!r.isNeg[0], "first number should not be negative");
    }
});
test("genAddSub answer ≥ 0 when allowNeg=false", () => {
    for (let i = 0; i < 100; i++) {
        const r = genAddSub(5, 1, 9, 50, false);
        assert(r.answer >= 0, `negative answer ${r.answer} with allowNeg=false`);
    }
});
test("genAddSub answer within [0, maxResult] (no neg)", () => {
    for (let i = 0; i < 100; i++) {
        const r = genAddSub(4, 1, 9, 30, false);
        assertInRange(r.answer, 0, 30, `answer ${r.answer} out of [0,30]`);
    }
});
test("genAddSub returns correct count of numbers", () => {
    for (const count of [2, 3, 5, 8]) {
        const r = genAddSub(count, 1, 9, 999, false);
        assertEqual(r.dispNums.length, count);
        assertEqual(r.isNeg.length, count);
    }
});
test("genAddSub opType is 'add'", () => {
    assertEqual(genAddSub(3, 1, 9, 50, false).opType, "add");
});
test("genMult: answer = a × b", () => {
    for (let i = 0; i < 30; i++) {
        const r = genMult(1, 9);
        assertEqual(r.answer, r.dispNums[0] * r.dispNums[1]);
    }
});
test("genMult: opType is 'mult'", () => {
    assertEqual(genMult(2, 9).opType, "mult");
});
test("genMult: always exactly 2 numbers", () => {
    assertEqual(genMult(1, 12).dispNums.length, 2);
});
test("genDiv: answer × divisor = dividend", () => {
    for (let i = 0; i < 30; i++) {
        const r = genDiv(2, 12);
        assertEqual(r.dispNums[0], r.answer * r.dispNums[1]);
    }
});
test("genDiv: divisor ≥ 2", () => {
    for (let i = 0; i < 30; i++) {
        const r = genDiv(2, 12);
        assert(r.dispNums[1] >= 2, `divisor ${r.dispNums[1]} < 2`);
    }
});
test("genDiv: opType is 'div'", () => {
    assertEqual(genDiv(2, 9).opType, "div");
});


// ═══════════════════════════════════════════════════════════════════════════════
// 7. STARS CALCULATION
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── Stars / Accuracy ─────────────────────────────────────────────");

function calcStars(correct, rounds) {
    const acc = Math.round(correct / rounds * 100);
    let stars = 0;
    if (acc >= 60) stars = 1;
    if (acc >= 80) stars = 2;
    if (acc === 100) stars = 3;
    return { acc, stars };
}

test("0/10 → 0 stars",    () => assertEqual(calcStars(0, 10).stars,  0));
test("5/10 (50%) → 0 stars", () => assertEqual(calcStars(5, 10).stars, 0));
test("6/10 (60%) → 1 star",  () => assertEqual(calcStars(6, 10).stars, 1));
test("8/10 (80%) → 2 stars",  () => assertEqual(calcStars(8, 10).stars, 2));
test("10/10 (100%) → 3 stars",() => assertEqual(calcStars(10, 10).stars,3));
test("acc rounds correctly: 7/11 = 63% → 1 star", () => {
    assertEqual(calcStars(7, 11).stars, 1);
    assertEqual(calcStars(7, 11).acc,  64); // Math.round(63.6) = 64
});


// ═══════════════════════════════════════════════════════════════════════════════
// 8. EXPORT / IMPORT
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── Export / Import ──────────────────────────────────────────────");

test("encExp produces a non-empty string", () => {
    const blob = encExp({ name: "Test", level: 5 });
    assert(typeof blob === "string" && blob.length > 10);
});
test("decImp round-trips the data exactly", () => {
    const orig = { name: "Mario", level: 42, stars: 1337, badges: ["s3","l5"] };
    const blob = encExp(orig);
    const back = decImp(blob);
    assertEqual(back.name,  orig.name);
    assertEqual(back.level, orig.level);
    assertEqual(back.stars, orig.stars);
    assertEqual(JSON.stringify(back.badges), JSON.stringify(orig.badges));
});
test("decImp throws on corrupted data", () => {
    let threw = false;
    try { decImp("not-valid-base64!!!"); } catch { threw = true; }
    assert(threw, "should throw on bad input");
});
test("decImp throws when checksum tampered", () => {
    const blob = encExp({ name: "Test" });
    // Flip a character in the middle
    const tampered = blob.slice(0, 10) + (blob[10] === "A" ? "B" : "A") + blob.slice(11);
    let threw = false;
    try { decImp(tampered); } catch { threw = true; }
    assert(threw, "should throw on tampered checksum");
});
test("cksum is deterministic", () => {
    const d = { a: 1, b: [2, 3] };
    assertEqual(cksum(d), cksum(d));
});
test("cksum differs for different data", () => {
    assert(cksum({ a: 1 }) !== cksum({ a: 2 }));
});


// ═══════════════════════════════════════════════════════════════════════════════
// 9. NUMPAD LOGIC
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── Numpad Logic ─────────────────────────────────────────────────");

// npCurrent is a module-level var in the game; we test via the exposed functions
function resetNP() { npCurrent = ""; }

test("npDigit builds number left-to-right", () => {
    resetNP(); G.waiting = false;
    npDigit(3); npDigit(7);
    assertEqual(npCurrent, "37");
});
test("npDigit 0 then digit appends (produces '05')", () => {
    resetNP(); G.waiting = false;
    npDigit(0); npDigit(5);
    assertEqual(npCurrent, "05"); // 0 is NOT replaced — only -0 gets replaced
});
test("npDigit '-0' then digit replaces the zero (produces '-5')", () => {
    // npNeg on '' → '-'; npDigit(0) appends → '-0'; npDigit(5) on '-0' replaces → '-5'
    resetNP(); G.waiting = false;
    npNeg(); npDigit(0);
    assertEqual(npCurrent, "-0");
    npDigit(5);
    assertEqual(npCurrent, "-5");
});
test("npBack removes last digit", () => {
    resetNP(); G.waiting = false;
    npDigit(4); npDigit(2); npBack();
    assertEqual(npCurrent, "4");
});
test("npBack on empty stays empty", () => {
    resetNP(); G.waiting = false;
    npBack();
    assertEqual(npCurrent, "");
});
test("npNeg toggles negative sign", () => {
    resetNP(); G.waiting = false;
    npDigit(5); npNeg();
    assertEqual(npCurrent, "-5");
});
test("npNeg on already-negative removes sign", () => {
    resetNP(); G.waiting = false;
    npDigit(5); npNeg(); npNeg();
    assertEqual(npCurrent, "5");
});
test("npNeg on empty string produces '-'", () => {
    resetNP(); G.waiting = false;
    npNeg();
    assertEqual(npCurrent, "-");
});
test("npDigit capped at 6 digits", () => {
    resetNP(); G.waiting = false;
    [1,2,3,4,5,6,7].forEach(d => npDigit(d));
    assertEqual(npCurrent, "123456");
});
test("npDigit blocked when G.waiting=true", () => {
    resetNP(); G.waiting = true;
    npDigit(9);
    assertEqual(npCurrent, "");
    G.waiting = false;
});


// ═══════════════════════════════════════════════════════════════════════════════
// 10. BADGE CONDITIONS
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── Badge Conditions ─────────────────────────────────────────────");

function badgeCk(id, data) {
    const b = BADGES.find(b => b.id === id);
    if (!b || !b.ck) throw new Error(`badge ${id} not found or has no ck`);
    return b.ck(data);
}

test("baby_steps: triggers at totalRounds=1", () =>
    assert(badgeCk("baby_steps", { totalRounds: 1 })));
test("baby_steps: does not trigger at 0", () =>
    assert(!badgeCk("baby_steps", { totalRounds: 0 })));
test("first_win: triggers at levelsCompleted=1", () =>
    assert(badgeCk("first_win", { levelsCompleted: 1 })));
test("s3: triggers at bestStreak=3", () =>
    assert(badgeCk("s3", { bestStreak: 3 })));
test("s3: does not trigger at bestStreak=2", () =>
    assert(!badgeCk("s3", { bestStreak: 2 })));
test("s50: triggers at bestStreak=50", () =>
    assert(badgeCk("s50", { bestStreak: 50 })));
test("a70: triggers at 70%+ over 30+ rounds", () =>
    assert(badgeCk("a70", { totalRounds: 30, correctAnswers: 21 })));
test("a70: does not trigger under 30 rounds", () =>
    assert(!badgeCk("a70", { totalRounds: 29, correctAnswers: 21 })));
test("a85: triggers at 85% over 50 rounds", () =>
    assert(badgeCk("a85", { totalRounds: 50, correctAnswers: 43 })));
test("a95: triggers at 95% over 100 rounds", () =>
    assert(badgeCk("a95", { totalRounds: 100, correctAnswers: 95 })));
test("r_thinker: triggers at level 15", () =>
    assert(badgeCk("r_thinker", { level: 15 })));
test("r_sage: does not trigger at level 99", () =>
    assert(!badgeCk("r_sage", { level: 99 })));
test("r_sage: triggers at level 100", () =>
    assert(badgeCk("r_sage", { level: 100 })));
test("w3: triggers when levels 1-30 all completed", () => {
    const lp = {};
    for (let i = 1; i <= 30; i++) lp[i] = { completed: true };
    assert(badgeCk("w3", { levelProgress: lp }));
});
test("w3: does not trigger when level 15 missing", () => {
    const lp = {};
    for (let i = 1; i <= 30; i++) lp[i] = { completed: true };
    delete lp[15];
    assert(!badgeCk("w3", { levelProgress: lp }));
});
test("m_diamond: triggers when any level has diamond mastery", () =>
    assert(badgeCk("m_diamond", { levelProgress: { 1: { mastery: "diamond" } } })));
test("m_gold: does not trigger when only bronze exists", () =>
    assert(!badgeCk("m_gold", { levelProgress: { 1: { mastery: "bronze" } } })));


// ═══════════════════════════════════════════════════════════════════════════════
// 11. CHALLENGE CONFIG HASH
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── Challenge Config Hash ────────────────────────────────────────");

test("same config → same hash", () => {
    CH.rounds=10; CH.numbers=5; CH.speed=1000; CH.maxNum=9; CH.ops=["add"];
    const h1 = challConfigHash();
    assertEqual(challConfigHash(), h1);
});
test("different rounds → different hash", () => {
    CH.rounds=10; CH.numbers=5; CH.speed=1000; CH.maxNum=9; CH.ops=["add"];
    const h1 = challConfigHash();
    CH.rounds = 20;
    assert(challConfigHash() !== h1);
});
test("ops order doesn't affect hash (sorted)", () => {
    CH.rounds=5; CH.numbers=3; CH.speed=800; CH.maxNum=9;
    CH.ops = ["sub", "add"];
    const h1 = challConfigHash();
    CH.ops = ["add", "sub"];
    assertEqual(challConfigHash(), h1);
});


// ═══════════════════════════════════════════════════════════════════════════════
// 12. UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════════
console.log("\n── Utility Functions ────────────────────────────────────────────");

test("fmtN: < 1000 shows plain number", () => assertEqual(fmtN(999), 999));
test("fmtN: 1000 → '1.0k'",  () => assertEqual(fmtN(1000), "1.0k"));
test("fmtN: 1500 → '1.5k'",  () => assertEqual(fmtN(1500), "1.5k"));
test("fmtN: 10000 → '10.0k'",() => assertEqual(fmtN(10000),"10.0k"));
test("fmtTime: 0s → '0s'",   () => assertEqual(fmtTime(0),  "0s"));
test("fmtTime: 59s → '59s'", () => assertEqual(fmtTime(59), "59s"));
test("fmtTime: 60s → '1:00'",() => assertEqual(fmtTime(60), "1:00"));
test("fmtTime: 90s → '1:30'",() => assertEqual(fmtTime(90), "1:30"));
test("fmtTime: 125s → '2:05'",()=> assertEqual(fmtTime(125),"2:05"));
test("rnd: always in [a, b]", () => {
    for (let i = 0; i < 500; i++) assertInRange(rnd(3, 7), 3, 7);
});
test("rnd(n, n) always returns n", () => {
    for (let i = 0; i < 20; i++) assertEqual(rnd(5, 5), 5);
});
test("todayStr returns ISO date format", () => {
    assert(/^\d{4}-\d{2}-\d{2}$/.test(todayStr()), `got: ${todayStr()}`);
});


// ═══════════════════════════════════════════════════════════════════════════════
// Summary
// ═══════════════════════════════════════════════════════════════════════════════
const total = passed + failed;
console.log(`\n${"─".repeat(60)}`);
console.log(`  ${passed}/${total} passed${failed > 0 ? `   ✗ ${failed} failed` : "   ✓ all good"}`);
console.log(`${"─".repeat(60)}\n`);

if (failed > 0) {
    console.log("Failed tests:");
    results.filter(r => !r.ok).forEach(r => console.log(`  ✗  ${r.name}\n     ${r.err}`));
    process.exit(1);
}
