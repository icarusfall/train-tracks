/* Train Tracks — player.
 *
 * Marks: 0 = blank, 1 = cross (no track), 2 = circle (track).
 * Given cells show their piece and can't be marked.
 *
 * Mouse:  left = cross, right = circle, double-click = clear, drag to paint.
 * Touch:  tap cycles blank → cross → circle → blank; drag paints the same mark.
 * Keys:   arrows move, X = cross, O = circle, Delete/Backspace = clear.
 */
(function () {
  "use strict";

  const PUZZLES = window.PUZZLES || [];
  const BLANK = 0, CROSS = 1, CIRCLE = 2;

  const $ = (id) => document.getElementById(id);
  const board = $("board");
  const statusEl = $("status");

  let P = null;            // current puzzle
  let givens = new Map();  // index -> piece
  let marks = [];          // per cell
  let undoStack = [];
  let rowStatus = [], colStatus = [];
  let revealed = false;
  let cellEls = [], rowTotalEls = [], colTotalEls = [];
  let painting = null;     // { state, pointerId }
  let lastPointerType = "mouse";
  let solved = false;       // board filled in and matches the solution
  let layOrder = new Map(); // cell index -> position along the line (for the laying animation)
  let layAnimate = false;
  let trainTimer = 0, trainFrame = 0;
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- storage (per-viewer convenience only) -----------------------------
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } },
  };

  // ---- track drawing -----------------------------------------------------
  const ROT = { NS: 0, EW: 90, NE: 0, SE: 90, SW: 180, NW: 270 };

  function pieceSVG(piece) {
    let body = "";
    if (piece === "NS" || piece === "EW") {
      for (const y of [10, 30, 50, 70, 90]) {
        body += `<line class="sleeper" x1="20" y1="${y}" x2="80" y2="${y}"/>`;
      }
      body += `<line class="rail" x1="36" y1="-1" x2="36" y2="101"/>` +
              `<line class="rail" x1="64" y1="-1" x2="64" y2="101"/>`;
    } else {
      // Quarter circle around the top-right corner (joins N and E); rotate for others.
      for (const deg of [9, 27, 45, 63, 81]) {
        const t = deg * Math.PI / 180, c = Math.cos(t), s = Math.sin(t);
        body += `<line class="sleeper" x1="${100 - 20 * c}" y1="${20 * s}" ` +
                `x2="${100 - 80 * c}" y2="${80 * s}"/>`;
      }
      for (const r of [36, 64]) {
        body += `<path class="rail" d="M ${100 - r} -1 L ${100 - r} 0 A ${r} ${r} 0 0 0 100 ${r} L 101 ${r}"/>`;
      }
    }
    return `<svg viewBox="0 0 100 100" aria-hidden="true"><g transform="rotate(${ROT[piece]} 50 50)">${body}</g></svg>`;
  }

  const CROSS_SVG = `<svg viewBox="0 0 100 100" aria-hidden="true"><line class="mark-x" x1="33" y1="33" x2="67" y2="67"/><line class="mark-x" x1="67" y1="33" x2="33" y2="67"/></svg>`;
  const CIRCLE_SVG = `<svg viewBox="0 0 100 100" aria-hidden="true"><circle class="mark-o" cx="50" cy="50" r="19"/></svg>`;

  // ---- puzzle lifecycle --------------------------------------------------
  function idx(r, c) { return r * P.cols + c; }

  function loadPuzzle(p) {
    P = p;
    givens = new Map(p.givens.map((g) => [idx(g.row, g.col), g.piece]));
    marks = new Array(p.rows * p.cols).fill(BLANK);
    const saved = store.get("tt:" + p.id);
    if (saved && saved.length === marks.length) {
      marks = Array.from(saved, (ch) => +ch || 0);
    }
    undoStack = [];
    revealed = false;
    solved = false;
    stopTrain();
    rowStatus = new Array(p.rows).fill(null);
    colStatus = new Array(p.cols).fill(null);
    store.set("tt:last", p.id);
    if (location.hash.slice(1) !== p.id) history.replaceState(null, "", "#" + p.id);

    $("puzzle-name").textContent = p.name || p.id;
    $("puzzle-difficulty").textContent = p.difficulty && p.difficulty !== "unrated" ? p.difficulty : "";
    buildBoard();
    setStatus("");
    updateButtons();
    if (boardSolved()) celebrate(false);
  }

  function buildBoard() {
    const R = P.rows, C = P.cols;
    board.innerHTML = "";
    board.style.gridTemplateColumns = `0.55fr repeat(${C}, 1fr) 0.55fr 0.9fr`;
    board.style.gridTemplateRows = `auto 1.1em repeat(${R}, auto) 1.4em`;
    cellEls = []; rowTotalEls = []; colTotalEls = [];

    const place = (el, row, col) => {
      el.style.gridRow = String(row + 1);
      el.style.gridColumn = String(col + 1);
      board.appendChild(el);
      return el;
    };
    const slot = (cls, text) => {
      const el = document.createElement("div");
      el.className = "slot " + cls;
      el.textContent = text;
      return el;
    };

    for (let c = 0; c < C; c++) {
      colTotalEls.push(place(slot("total", P.col_totals[c]), 0, c + 1));
    }
    for (let r = 0; r < R; r++) {
      rowTotalEls.push(place(slot("total", P.row_totals[r]), r + 2, C + 2));
      for (let c = 0; c < C; c++) {
        const el = document.createElement("div");
        const i = idx(r, c);
        el.className = "cell" + (c === C - 1 ? " last-col" : "") + (r === R - 1 ? " last-row" : "");
        el.dataset.i = i;
        if (givens.has(i)) {
          el.classList.add("given");
          el.setAttribute("aria-label", `Row ${r + 1}, column ${c + 1}: given track`);
        }
        cellEls.push(place(el, r + 2, c + 1));
      }
    }
    // Make sure exactly one non-given cell is tabbable.
    let first = true;
    for (const el of cellEls) {
      if (el.classList.contains("given")) continue;
      el.tabIndex = first ? 0 : -1;
      first = false;
    }

    for (const [t, name] of [[P.start, "A"], [P.end, "B"]]) {
      const pos = {
        N: [1, t.col + 1], S: [R + 2, t.col + 1], W: [t.row + 2, 0], E: [t.row + 2, C + 1],
      }[t.side];
      place(slot("terminal", name), pos[0], pos[1]).setAttribute("aria-label", `Village ${name}`);
    }

    const frame = document.createElement("div");
    frame.className = "frame";
    frame.style.gridRow = `3 / span ${R}`;
    frame.style.gridColumn = `2 / span ${C}`;
    board.appendChild(frame);

    const layer = document.createElement("div");
    layer.className = "train-layer";
    layer.style.gridRow = frame.style.gridRow;
    layer.style.gridColumn = frame.style.gridColumn;
    layer.innerHTML = `<svg viewBox="0 0 ${C * 100} ${R * 100}" preserveAspectRatio="none" aria-hidden="true">` +
      `<path class="route" d="${routePath(route())}"/>${TRAIN_CARS}</svg>`;
    board.appendChild(layer);

    renderAll();
  }

  // ---- rendering ---------------------------------------------------------
  function renderCell(i) {
    const el = cellEls[i];
    const r = Math.floor(i / P.cols) + 1, c = (i % P.cols) + 1;
    if (givens.has(i)) {
      el.innerHTML = pieceSVG(givens.get(i));
      return;
    }
    if (revealed) {
      const p = P.solution[r - 1][c - 1];
      el.innerHTML = p ? pieceSVG(p) : "";
      el.classList.add("reveal");
      return;
    }
    el.classList.remove("reveal");
    const m = marks[i];
    if (solved && m === CIRCLE) {
      // Finished: the circles become real track, laid in order from A to B.
      el.innerHTML = pieceSVG(P.solution[r - 1][c - 1]);
      el.classList.toggle("laid", layAnimate);
      el.style.setProperty("--d", (layOrder.get(i) || 0) * LAY_MS + "ms");
      el.setAttribute("aria-label", `Row ${r}, column ${c}: track`);
      return;
    }
    el.classList.remove("laid");
    el.classList.toggle("dim", solved);
    el.innerHTML = m === CROSS ? CROSS_SVG : m === CIRCLE ? CIRCLE_SVG : "";
    el.setAttribute("aria-label",
      `Row ${r}, column ${c}: ${m === CROSS ? "no track" : m === CIRCLE ? "track" : "blank"}`);
  }

  function renderTotals() {
    rowTotalEls.forEach((el, r) => { el.className = "slot total" + (rowStatus[r] ? " " + rowStatus[r] : ""); });
    colTotalEls.forEach((el, c) => { el.className = "slot total" + (colStatus[c] ? " " + colStatus[c] : ""); });
  }

  function renderAll() {
    for (let i = 0; i < cellEls.length; i++) renderCell(i);
    renderTotals();
  }

  function setStatus(text, kind) {
    statusEl.textContent = text;
    statusEl.className = "status" + (kind ? " " + kind : "");
  }

  function updateButtons() {
    $("btn-undo").disabled = undoStack.length === 0 || revealed;
    $("btn-check").disabled = revealed;
    $("btn-reset").disabled = revealed;
    $("btn-reveal").textContent = revealed ? "Hide solution" : "Show solution";
  }

  // ---- editing -----------------------------------------------------------
  function save() { store.set("tt:" + P.id, marks.join("")); }

  function pushUndo() {
    undoStack.push(marks.slice());
    if (undoStack.length > 500) undoStack.shift();
    updateButtons();
  }

  function setMark(i, state) {
    if (givens.has(i) || marks[i] === state) return;
    marks[i] = state;
    // Old check colours no longer apply to this row and column.
    const r = Math.floor(i / P.cols), c = i % P.cols;
    if (rowStatus[r] || colStatus[c]) {
      rowStatus[r] = null;
      colStatus[c] = null;
      renderTotals();
    }
    renderCell(i);
    save();
    if (statusEl.textContent) setStatus("");
  }

  function cellFromEvent(e) {
    const el = e.target.closest ? e.target.closest(".cell") : null;
    return el && board.contains(el) ? +el.dataset.i : -1;
  }

  board.addEventListener("contextmenu", (e) => e.preventDefault());

  board.addEventListener("pointerdown", (e) => {
    lastPointerType = e.pointerType;
    const i = cellFromEvent(e);
    if (i < 0 || givens.has(i) || revealed) return;
    e.preventDefault();
    let state;
    if (e.pointerType === "mouse") {
      if (e.button === 0) state = CROSS;
      else if (e.button === 2) state = CIRCLE;
      else return;
    } else {
      state = (marks[i] + 1) % 3;
    }
    pushUndo();
    setMark(i, state);
    painting = { state, pointerId: e.pointerId };
    cellEls[i].focus({ preventScroll: true });
    // Touch pointers are implicitly captured by the first element; release so
    // elementFromPoint works and we can paint across cells.
    if (board.hasPointerCapture && board.hasPointerCapture(e.pointerId)) {
      board.releasePointerCapture(e.pointerId);
    }
  });

  board.addEventListener("pointermove", (e) => {
    if (!painting || e.pointerId !== painting.pointerId) return;
    const el = document.elementFromPoint(e.clientX, e.clientY);
    const cell = el && el.closest ? el.closest(".cell") : null;
    if (cell && board.contains(cell)) setMark(+cell.dataset.i, painting.state);
  });

  const endPaint = (e) => {
    if (painting && e.pointerId === painting.pointerId) {
      painting = null;
      afterEdit();
    }
  };
  window.addEventListener("pointerup", endPaint);
  window.addEventListener("pointercancel", endPaint);

  board.addEventListener("dblclick", (e) => {
    if (lastPointerType !== "mouse" || revealed) return;
    const i = cellFromEvent(e);
    if (i < 0 || givens.has(i)) return;
    setMark(i, BLANK);
    afterEdit();
  });

  board.addEventListener("keydown", (e) => {
    const i = cellFromEvent(e);
    if (i < 0) return;
    const r = Math.floor(i / P.cols), c = i % P.cols;
    const moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
    if (moves[e.key]) {
      e.preventDefault();
      let [rr, cc] = [r, c];
      do {
        rr += moves[e.key][0];
        cc += moves[e.key][1];
      } while (rr >= 0 && rr < P.rows && cc >= 0 && cc < P.cols && givens.has(idx(rr, cc)));
      if (rr >= 0 && rr < P.rows && cc >= 0 && cc < P.cols) {
        cellEls[i].tabIndex = -1;
        const next = cellEls[idx(rr, cc)];
        next.tabIndex = 0;
        next.focus();
      }
      return;
    }
    if (givens.has(i) || revealed) return;
    const key = e.key.toLowerCase();
    const state = key === "x" || key === "1" ? CROSS
      : key === "o" || key === "2" ? CIRCLE
      : key === "delete" || key === "backspace" || key === "0" || key === " " ? BLANK
      : null;
    if (state === null) return;
    e.preventDefault();
    if (marks[i] !== state) { pushUndo(); setMark(i, state); afterEdit(); }
  });

  // ---- completion: lay the track and run the train -------------------------
  const LAY_MS = 45;          // delay between laying successive pieces
  const TRAIN_SPEED = 0.5;    // grid units (1 cell = 100) per millisecond
  const CAR_GAPS = [0, 66, 128];
  const STEP = { N: [0, -1], S: [0, 1], E: [1, 0], W: [-1, 0] };   // [dx, dy]
  const OPP = { N: "S", S: "N", E: "W", W: "E" };

  // Seen from above, facing +x, centred on the origin.
  const TRAIN_CARS =
    `<g class="car engine"><rect class="body" x="-30" y="-16" width="60" height="32" rx="8"/>` +
    `<rect class="cab" x="-30" y="-16" width="20" height="32" rx="5"/>` +
    `<circle class="chimney" cx="17" cy="0" r="7"/><line class="buffer" x1="31" y1="-11" x2="31" y2="11"/></g>` +
    `<g class="car carriage"><rect class="body" x="-26" y="-14" width="52" height="28" rx="6"/>` +
    `<line class="roof" x1="-18" y1="0" x2="18" y2="0"/></g>` +
    `<g class="car carriage"><rect class="body" x="-26" y="-14" width="52" height="28" rx="6"/>` +
    `<line class="roof" x1="-18" y1="0" x2="18" y2="0"/></g>`;

  function boardSolved() {
    if (revealed) return false;
    for (let i = 0; i < marks.length; i++) {
      if (givens.has(i)) continue;
      if (marks[i] === BLANK) return false;
      const r = Math.floor(i / P.cols), c = i % P.cols;
      if ((marks[i] === CIRCLE) !== Boolean(P.solution[r][c])) return false;
    }
    return true;
  }

  /** The solution as a walk from A to B: [{i, r, c, entry, exit}]. */
  function route() {
    const steps = [];
    let r = P.start.row, c = P.start.col, entry = P.start.side;
    for (let n = 0; n < P.rows * P.cols; n++) {
      const exit = P.solution[r][c].replace(entry, "");
      steps.push({ i: idx(r, c), r, c, entry, exit });
      if (r === P.end.row && c === P.end.col && exit === P.end.side) break;
      c += STEP[exit][0];
      r += STEP[exit][1];
      entry = OPP[exit];
    }
    return steps;
  }

  /** SVG path along the middle of the track, starting and ending just outside the grid. */
  function routePath(steps) {
    const mid = (s, side) => [s.c * 100 + 50 + STEP[side][0] * 50, s.r * 100 + 50 + STEP[side][1] * 50];
    const first = steps[0], last = steps[steps.length - 1];
    const [sx, sy] = mid(first, first.entry);
    let d = `M ${sx + STEP[first.entry][0] * 70} ${sy + STEP[first.entry][1] * 70} L ${sx} ${sy}`;
    for (const s of steps) {
      const [x, y] = mid(s, s.exit);
      if (s.entry === OPP[s.exit]) {
        d += ` L ${x} ${y}`;
      } else {
        const din = STEP[OPP[s.entry]], dout = STEP[s.exit];
        const sweep = din[0] * dout[1] - din[1] * dout[0] > 0 ? 1 : 0;
        d += ` A 50 50 0 0 ${sweep} ${x} ${y}`;
      }
    }
    const [ex, ey] = mid(last, last.exit);
    return d + ` L ${ex + STEP[last.exit][0] * 70} ${ey + STEP[last.exit][1] * 70}`;
  }

  /** Called after each finished edit: start or undo the celebration. */
  function afterEdit() {
    const now = boardSolved();
    if (now && !solved) {
      celebrate(true);
    } else if (!now && solved) {
      solved = false;
      stopTrain();
      rowStatus.fill(null);
      colStatus.fill(null);
      renderAll();
      setStatus("");
    }
  }

  function celebrate(animate) {
    solved = true;
    stopTrain();
    const steps = route();
    layOrder = new Map(steps.map((s, k) => [s.i, k]));
    layAnimate = animate && !reduceMotion;
    rowStatus.fill("ok");
    colStatus.fill("ok");
    renderAll();
    statusEl.className = "status ok";
    statusEl.textContent = "Solved! All aboard from A to B. ";
    const again = document.createElement("button");
    again.type = "button";
    again.className = "linkish";
    again.textContent = "Run the train again";
    again.addEventListener("click", runTrain);
    statusEl.appendChild(again);
    if (animate && !reduceMotion) {
      trainTimer = setTimeout(runTrain, steps.length * LAY_MS + 350);
    }
  }

  function stopTrain() {
    clearTimeout(trainTimer);
    cancelAnimationFrame(trainFrame);
    board.querySelectorAll(".train-layer .car").forEach((car) => { car.style.opacity = "0"; });
  }

  function runTrain() {
    stopTrain();
    const path = board.querySelector(".train-layer .route");
    if (!path) return;
    const cars = [...board.querySelectorAll(".train-layer .car")];
    const L = path.getTotalLength();
    const travel = L + CAR_GAPS[CAR_GAPS.length - 1];
    const duration = travel / TRAIN_SPEED;
    const ease = (t) => (1 - Math.cos(Math.PI * t)) / 2;
    let t0 = null;

    const frame = (now) => {
      if (t0 === null) t0 = now;
      const t = Math.min(1, (now - t0) / duration);
      const s = ease(t) * travel;
      cars.forEach((car, k) => {
        const at = s - CAR_GAPS[k];
        if (at < 0 || at > L) { car.style.opacity = "0"; return; }
        const p = path.getPointAtLength(at);
        const a = path.getPointAtLength(Math.max(0, at - 2));
        const b = path.getPointAtLength(Math.min(L, at + 2));
        const deg = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
        car.setAttribute("transform", `translate(${p.x} ${p.y}) rotate(${deg})`);
        car.style.opacity = "1";
      });
      if (t < 1) trainFrame = requestAnimationFrame(frame);
    };
    trainFrame = requestAnimationFrame(frame);
  }

  // ---- check -------------------------------------------------------------
  function check() {
    const R = P.rows, C = P.cols;
    const isTrack = (i) => givens.has(i) || marks[i] === CIRCLE;
    const isDone = (i) => givens.has(i) || marks[i] !== BLANK;
    let complete = 0, right = 0;
    const judge = (cells, total) => {
      if (!cells.every(isDone)) return null;
      complete++;
      const ok = cells.filter(isTrack).length === total;
      if (ok) right++;
      return ok ? "ok" : "bad";
    };
    for (let r = 0; r < R; r++) {
      rowStatus[r] = judge(Array.from({ length: C }, (_, c) => idx(r, c)), P.row_totals[r]);
    }
    for (let c = 0; c < C; c++) {
      colStatus[c] = judge(Array.from({ length: R }, (_, r) => idx(r, c)), P.col_totals[c]);
    }
    renderTotals();

    if (boardSolved()) {
      celebrate(!solved);
      return;
    }
    if (complete === 0) {
      setStatus("Nothing to check yet: fill in a whole row or column first.");
    } else if (complete === R + C && right === complete) {
      let solved = true;
      for (let r = 0; r < R && solved; r++) {
        for (let c = 0; c < C; c++) {
          if (isTrack(idx(r, c)) !== Boolean(P.solution[r][c])) { solved = false; break; }
        }
      }
      if (solved) setStatus("Solved! The train can get from A to B.", "ok");
      else setStatus("All the totals match, but that isn’t one unbroken line from A to B.", "bad");
    } else if (right === complete) {
      setStatus(`All ${complete} completed line${complete === 1 ? "" : "s"} add up.`, "ok");
    } else {
      const wrong = complete - right;
      setStatus(`${wrong} of ${complete} completed line${complete === 1 ? "" : "s"} ${wrong === 1 ? "doesn’t" : "don’t"} add up.`, "bad");
    }
  }

  // ---- buttons -----------------------------------------------------------
  $("btn-check").addEventListener("click", check);

  $("btn-undo").addEventListener("click", () => {
    if (!undoStack.length) return;
    marks = undoStack.pop();
    rowStatus.fill(null);
    colStatus.fill(null);
    renderAll();
    save();
    setStatus("");
    updateButtons();
    afterEdit();
  });

  $("btn-reset").addEventListener("click", () => {
    if (marks.every((m) => m === BLANK)) return;
    pushUndo();
    marks.fill(BLANK);
    solved = false;
    stopTrain();
    rowStatus.fill(null);
    colStatus.fill(null);
    renderAll();
    save();
    setStatus("Board cleared. Press Undo to get your marks back.");
  });

  $("btn-reveal").addEventListener("click", () => {
    revealed = !revealed;
    stopTrain();
    renderAll();
    updateButtons();
    setStatus(revealed ? "Showing the solution. Your marks are kept for when you hide it." : "");
  });

  const diffSel = $("sel-difficulty");
  diffSel.value = store.get("tt:difficulty") || "any";
  diffSel.addEventListener("change", () => store.set("tt:difficulty", diffSel.value));

  $("btn-new").addEventListener("click", () => {
    const want = diffSel.value;
    let pool = PUZZLES.filter((p) => p.id !== P.id && (want === "any" || p.difficulty === want));
    // Prefer puzzles not started yet.
    const fresh = pool.filter((p) => !store.get("tt:" + p.id));
    if (fresh.length) pool = fresh;
    if (!pool.length) { setStatus("No other puzzles at that difficulty."); return; }
    loadPuzzle(pool[Math.floor(Math.random() * pool.length)]);
  });

  window.addEventListener("hashchange", () => {
    const p = PUZZLES.find((q) => q.id === location.hash.slice(1));
    if (p && p !== P) loadPuzzle(p);
  });

  // ---- start -------------------------------------------------------------
  const coarse = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
  $("help-input").innerHTML = coarse
    ? "<b>Tap</b> a square once for ✕ (no track), twice for ○ (track), three times to clear. Drag to mark several squares the same way. <b>Check</b> colours each completed row and column green or red."
    : "<b>Left-click</b> for ✕ (no track), <b>right-click</b> for ○ (track), <b>double-click</b> to clear. Drag to mark several squares. Keyboard: arrows, X, O, Delete. <b>Check</b> colours each completed row and column green or red.";

  if (!PUZZLES.length) {
    setStatus("No puzzles found (puzzles.js is missing).", "bad");
    return;
  }
  const want = location.hash.slice(1) || store.get("tt:last");
  loadPuzzle(PUZZLES.find((p) => p.id === want) || PUZZLES[0]);
})();
