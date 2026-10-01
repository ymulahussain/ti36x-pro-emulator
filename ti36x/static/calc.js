// Keep local actions in order, and let one EventSource handle reconnects.
let pendingAction = Promise.resolve();
let eventStream;
let topButtonsWired = false;
let currentPanel = null;

// Only these fixed, locally authored legends contain markup. API text is
// always inserted with textContent, including entries, results, and menus.
const box = '<span class="box-mark"></span>';
const fraction = `<span class="fraction-mark"><span>${box}</span><span>${box}</span></span>`;
const keyLegends = {
  exp10: `<span><i>e</i><sup>${box}</sup> 10<sup>${box}</sup></span>`,
  prb: '<span>!</span><span class="stack"><span>nCr</span><span>nPr</span></span>',
  pi: '<i>π</i><span class="stack"><i>e</i><i>i</i></span>',
  sin: '<span class="stack trig"><span>sin</span><span>sin<sup>−1</sup></span></span>',
  cos: '<span class="stack trig"><span>cos</span><span>cos<sup>−1</sup></span></span>',
  tan: '<span class="stack trig"><span>tan</span><span>tan<sup>−1</sup></span></span>',
  power: `<span><i>x</i><sup>${box}</sup></span>`,
  frac: fraction,
  sq: "<span><i>x</i><sup>2</sup></span>",
  var: '<span class="variable-x">x</span><span class="stack variables"><span>yzt</span><span>abcd</span></span>',
  sto: "sto<span>→</span>",
  fd: '<svg viewBox="0 0 24 18" aria-hidden="true"><path d="M1 9 9 3v12ZM23 9 15 3v12Z" fill="currentColor"/></svg><span>≈</span>',
};
const shiftLegends = {
  lnlog: `<i>d/dx</i>&nbsp;${box}`,
  exp10: `<i>∫</i><sup>${box}</sup>${box}<i>dx</i>`,
  power: `${box}<i>√</i><span style="border-top: .2cqw solid currentColor">${box}</span>`,
  frac: `<span class="fraction-mark"><span>1</span><span>${box}</span></span>`,
  sq: `<i>√</i>${box}`,
  7: `<span class="box-mark whole-mark"></span>${fraction}`,
  sub: '<svg viewBox="0 0 26 14" aria-hidden="true"><path d="M1 7 7 3v8Z" fill="currentColor"/><circle cx="16" cy="7" r="5" fill="none" stroke="currentColor"/><path d="M16 2a5 5 0 0 1 0 10Z" fill="currentColor"/></svg>',
  add: '<svg viewBox="0 0 26 14" aria-hidden="true"><path d="m25 7-6-4v8Z" fill="currentColor"/><circle cx="10" cy="7" r="5" fill="none" stroke="currentColor"/><path d="M10 2a5 5 0 0 1 0 10Z" fill="currentColor"/></svg>',
};

function showError(error) {
  document.getElementById("error-line").textContent =
    error.message || String(error);
}

async function fetchJSON(url, opts) {
  const response = await fetch(url, opts);
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join("; ")
      : data.detail;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return data;
}

function enqueueAction(operation) {
  pendingAction = pendingAction.then(operation).catch(showError);
  return pendingAction;
}

function press(name, el) {
  return enqueueAction(async () => {
    if (el) {
      el.classList.add("pressed");
      setTimeout(() => el.classList.remove("pressed"), 140);
    }
    const state = await fetchJSON("/press", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: name }),
    });
    renderState(state);
  });
}

function makeKeyButton(name, meta, physical = true) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `key ${meta.group || "fn"}`;
  button.dataset.name = name;
  button.disabled = meta.enabled === false;
  button.title = button.disabled
    ? "Planned feature — not available yet"
    : `${meta.label}${meta.shift ? ` (2nd: ${meta.shift})` : ""}`;
  button.setAttribute("aria-label", button.title);
  const label = document.createElement("span");
  label.className = "label";
  if (physical && keyLegends[name]) label.innerHTML = keyLegends[name];
  else label.textContent = meta.label;
  label.setAttribute("aria-hidden", "true");
  button.appendChild(label);
  button.addEventListener("click", () => press(name, button));
  if (!physical) return button;
  const slot = document.createElement("div");
  slot.className = "key-slot";
  const shift = document.createElement("span");
  shift.className = "shift";
  shift.setAttribute("aria-hidden", "true");
  if (shiftLegends[name]) shift.innerHTML = shiftLegends[name];
  else shift.textContent = meta.shift || "";
  slot.append(shift, button);
  return slot;
}

async function buildKeypad() {
  const data = await fetchJSON("/keys");
  const menu = document.getElementById("menu-row");
  menu.replaceChildren(
    ...data.menu.map((name) => makeKeyButton(name, data.keys[name])),
  );

  const keys = document.getElementById("keys");
  keys.style.gridTemplateColumns = `repeat(${data.grid[0].length}, minmax(0, 1fr))`;
  keys.replaceChildren();
  for (const row of data.grid) {
    for (const name of row) {
      if (name) keys.appendChild(makeKeyButton(name, data.keys[name]));
    }
  }

  const utilities = document.getElementById("utility-keys");
  const labels = { reciprocal: "1/x", sqrt: "√", ans: "ans" };
  utilities.replaceChildren(
    ...Object.entries(labels).map(([name, label]) =>
      makeKeyButton(name, { label }, false),
    ),
  );

  // Only the static controls need listeners here. Generated buttons already
  // have their own listener, including those in the menu row.
  if (!topButtonsWired) {
    document.querySelectorAll(".control-strip [data-name]").forEach((el) => {
      el.addEventListener("click", () => press(el.dataset.name, el));
    });
    topButtonsWired = true;
  }
}

function renderState(state) {
  const entry = document.getElementById("entry-line");
  if (state.entry) {
    const caret = document.createElement("span");
    caret.className = "cursor";
    caret.textContent = "│";
    entry.replaceChildren(
      state.entry.slice(0, state.cursor),
      caret,
      state.entry.slice(state.cursor),
    );
  } else {
    const caret = document.createElement("span");
    caret.className = "cursor";
    caret.textContent = "│";
    entry.replaceChildren(caret);
  }
  document.getElementById("result-line").textContent = state.result;
  const previous = state.history
    .filter(([expression]) => expression !== state.entry)
    .at(-1);
  document.getElementById("lcd-history-entry").textContent =
    previous?.[0] || "";
  document.getElementById("lcd-history-result").textContent =
    previous?.[1] || "";
  // A completed calculation sits above the new cursor. Do not repeat the
  // cached answer beneath it when the input line is empty.
  document.querySelector(".screen").dataset.answerInHistory = String(
    !state.entry && !!previous && previous[1] === state.result,
  );
  document.getElementById("error-line").textContent = state.error || "";
  document
    .getElementById("status-2nd")
    .classList.toggle("active", !!state.is_2nd);
  const angle = document.getElementById("status-angle");
  angle.textContent = state.angle;
  angle.classList.add("active");
  const mode = document.getElementById("status-mode");
  mode.textContent = state.mode;
  mode.classList.toggle("active", state.mode !== "NORMAL");
  document.getElementById("status-fmt").textContent = state.float_format;
  document
    .getElementById("status-fmt")
    .classList.toggle("active", state.float_format !== "FLOAT");
  renderMenu(state);
  renderPanel(state);
  document.querySelector(".screen").dataset.powered = String(state.powered_on);
  document.querySelector(".screen").style.filter =
    `contrast(${0.6 + state.contrast * 0.08})`;
  document.getElementById("prompt-line").textContent = state.memory_action
    ? `Store in ${state.feature_result?.store_in || "x"}: press the variable key to cycle, then Enter`
    : state.menu === "math"
      ? "Choose a function. Use 2nd + . for a comma."
      : "";

  const history = document.getElementById("history");
  history.replaceChildren();
  for (const [expression, result] of state.history.slice().reverse()) {
    const item = document.createElement("li");
    const left = document.createElement("span");
    left.textContent = expression;
    const right = document.createElement("span");
    right.className = "res";
    right.textContent = result;
    item.append(left, right);
    history.appendChild(item);
  }
  const second = document.querySelector('[data-name="2nd"]');
  if (second) second.classList.toggle("active", !!state.is_2nd);
}

function renderMenu(state) {
  const menu = document.getElementById("calculator-menu");
  const view = state.menu_view;
  menu.hidden = !state.menu || !view?.tabs;
  document.querySelector(".screen").dataset.menu = String(!menu.hidden);
  menu.replaceChildren();
  if (menu.hidden) return;
  const tabs = document.createElement("div");
  tabs.className = "menu-tabs";
  view.tabs.forEach((name, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = name;
    button.classList.toggle("selected", index === view.tab);
    button.addEventListener("click", () => press(`tab_${index}`));
    tabs.appendChild(button);
  });
  const items = document.createElement("div");
  items.className = "menu-items";
  view.items.forEach((label, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${index + 1}: ${label}${view.current === label ? " ✓" : ""}`;
    button.classList.toggle("selected", index === view.selected);
    button.addEventListener("click", () => press(`select_${index}`));
    items.appendChild(button);
  });
  menu.append(tabs, items);
  const selected = items.querySelector(".selected");
  if (selected) items.scrollTop = selected.offsetTop - items.offsetTop;
}

function renderPanel(state) {
  const output = document.getElementById("feature-result");
  output.hidden = state.feature_result == null;
  output.textContent = output.hidden
    ? ""
    : JSON.stringify(state.feature_result, null, 2);
  if (state.panel === currentPanel) return;
  currentPanel = state.panel;
  const requestedPanel = currentPanel;
  const section = document.getElementById("feature-panel");
  section.hidden = !requestedPanel;
  if (requestedPanel) document.getElementById("workspace-tools").open = true;
  const form = document.getElementById("feature-form");
  form.replaceChildren();
  if (!requestedPanel) return;
  fetchJSON("/panel")
    .then((schema) => {
      if (currentPanel !== requestedPanel) return;
      section.hidden = !schema;
      if (!schema) return;
      document.getElementById("feature-title").textContent = schema.title;
      for (const field of schema.fields) {
        const label = document.createElement("label");
        label.textContent = field.label;
        const input = document.createElement(
          field.type === "json" ? "textarea" : "input",
        );
        input.name = field.name;
        input.value =
          field.type === "json" ? JSON.stringify(field.default) : field.default;
        label.appendChild(input);
        form.appendChild(label);
      }
      const submit = document.createElement("button");
      submit.type = "submit";
      submit.textContent = "Calculate";
      form.appendChild(submit);
      form.onsubmit = (event) => {
        event.preventDefault();
        enqueueAction(async () => {
          const parameters = {};
          for (const field of schema.fields) {
            const text = form.elements.namedItem(field.name).value;
            parameters[field.name] =
              field.type === "json" ? JSON.parse(text) : text;
          }
          renderState(
            await fetchJSON("/feature", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ operation: schema.operation, parameters }),
            }),
          );
        });
      };
    })
    .catch(showError);
}

function flashKey(name) {
  const el = [...document.querySelectorAll("[data-name]")].find(
    (key) => key.dataset.name === name,
  );
  if (!el) return;
  el.classList.remove("flash");
  // Restart the animation when the same key is pressed twice.
  void el.offsetWidth;
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 350);
}

function connectEvents() {
  if (eventStream) eventStream.close();
  eventStream = new EventSource("/events");
  const status = document.getElementById("connection-status");
  eventStream.onopen = () => {
    status.textContent = "Connected";
  };
  eventStream.onmessage = (event) => {
    try {
      const state = JSON.parse(event.data);
      renderState(state);
      if (state.last_key) flashKey(state.last_key);
    } catch (error) {
      showError(error);
    }
  };
  // EventSource reconnects automatically. Creating another source here would
  // leave the original alive and multiply subscriptions on every outage.
  eventStream.onerror = () => {
    status.textContent = "Disconnected — reconnecting…";
  };
}

async function initialize() {
  try {
    await buildKeypad();
    renderState(await fetchJSON("/state"));
    connectEvents();
  } catch (error) {
    document.getElementById("connection-status").textContent =
      "Connection failed — press Retry";
    showError(error);
  }
}

document
  .getElementById("reconnect-btn")
  .addEventListener("click", () => enqueueAction(initialize));
document.getElementById("reset-btn").addEventListener("click", () =>
  enqueueAction(async () => {
    renderState(await fetchJSON("/reset", { method: "POST" }));
  }),
);

document.addEventListener("keydown", (event) => {
  if (
    event.ctrlKey ||
    event.metaKey ||
    event.altKey ||
    event.isComposing ||
    event.target.closest("input, textarea, select, [contenteditable='true']")
  )
    return;
  const map = {
    0: "0",
    1: "1",
    2: "2",
    3: "3",
    4: "4",
    5: "5",
    6: "6",
    7: "7",
    8: "8",
    9: "9",
    ".": "dot",
    ",": "comma",
    "+": "add",
    "-": "sub",
    "*": "mul",
    "/": "div",
    "(": "lparen",
    ")": "rparen",
    "^": "power",
    "=": "enter",
    Enter: "enter",
    Backspace: "backspace",
    Delete: "delete",
    Escape: "clear",
    ArrowLeft: "left",
    ArrowRight: "right",
    ArrowUp: "up",
    ArrowDown: "down",
  };
  const name = map[event.key];
  if (name) {
    event.preventDefault();
    flashKey(name);
    press(name);
  }
});

window.addEventListener("offline", () => {
  document.getElementById("connection-status").textContent =
    "Disconnected — reconnecting…";
});
window.addEventListener("online", () => {
  document.getElementById("connection-status").textContent =
    eventStream?.readyState === EventSource.OPEN
      ? "Connected"
      : "Reconnecting…";
});
window.addEventListener("beforeunload", () => eventStream?.close());
initialize();
