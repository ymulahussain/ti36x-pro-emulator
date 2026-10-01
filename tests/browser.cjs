// Optional end-to-end checks: requires Playwright and a Chromium installation.
const assert = require("node:assert/strict");
const { chromium } = require("playwright");
const base = process.env.CALCULATOR_URL || "http://127.0.0.1:8765";

(async () => {
  const browser = await chromium.launch({
    executablePath:
      process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || "/usr/bin/chromium",
    headless: true,
  });
  try {
    const context = await browser.newContext();
    await context.addInitScript(() => {
      const Original = window.EventSource;
      window.eventSourcesCreated = 0;
      window.EventSource = class extends Original {
        constructor(...args) {
          super(...args);
          window.eventSourcesCreated++;
        }
      };
    });
    const page = await context.newPage();
    const errors = [];
    const presses = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => {
      if (
        new URL(request.url()).pathname === "/press" &&
        request.method() === "POST"
      ) {
        presses.push(request.postDataJSON().key);
      }
    });
    await page.request.post(base + "/reset");
    await page.goto(base);
    await page.waitForFunction(
      () =>
        document.getElementById("connection-status").textContent ===
        "Connected",
    );
    assert.equal(await page.locator("#keys button").count(), 35);
    assert.equal(await page.locator('[data-name="data"]').isDisabled(), false);
    assert.equal(await page.locator('[data-name="table"]').isDisabled(), false);
    console.log("PASS: keypad loads with honest feature availability");
    await page.evaluate(() => document.fonts.ready);
    assert.equal(await page.locator(".calc button").count(), 45);
    assert.equal(await page.locator(".calc #utility-keys").count(), 0);
    assert.equal(
      await page.locator("#workspace-tools").evaluate((el) => el.open),
      false,
    );
    assert.equal(
      await page.evaluate(() =>
        [...document.fonts].some(
          (font) =>
            font.family === "Calculator LCD" && font.status === "loaded",
        ),
      ),
      true,
    );
    const face = await page.locator(".calc").boundingBox();
    assert.ok(Math.abs(face.width / face.height - 455 / 1000) < 0.001);
    const modeKey = await page.locator('[data-name="mode"]').boundingBox();
    const logKey = await page.locator('[data-name="lnlog"]').boundingBox();
    const pad = await page.locator(".nav-pad").boundingBox();
    assert.ok(modeKey.y < logKey.y && pad.x > modeKey.x + modeKey.width);
    console.log(
      "PASS: physical face has 45 keys, original LCD font and reference proportions",
    );

    async function settled() {
      await page.evaluate(() => pendingAction);
    }
    async function click(name) {
      await page.locator(`[data-name="${name}"]`).click();
      await settled();
    }
    async function result(expected) {
      await page.waitForFunction(
        (value) => document.getElementById("result-line").textContent === value,
        expected,
      );
      assert.equal(await page.locator("#error-line").textContent(), "");
    }
    async function openTools() {
      await page.locator("#workspace-tools").evaluate((el) => {
        el.open = true;
      });
    }
    async function reset() {
      await openTools();
      await page.locator("#reset-btn").click();
      await settled();
    }

    const beforeLn = presses.length;
    await click("lnlog");
    assert.deepEqual(presses.slice(beforeLn), ["lnlog"]);
    assert.equal((await page.request.get(base + "/state")).status(), 200);
    assert.equal(await page.locator("#entry-line").innerText(), "ln(│");
    await reset();
    await click("lnlog");
    await click("lnlog");
    await page.keyboard.type("100)");
    await page.keyboard.press("Enter");
    await settled();
    await result("2");
    console.log("PASS: menu keys fire once and shifted logarithms work");

    await reset();
    await page.keyboard.type("123456789+1");
    await page.keyboard.press("Enter");
    await settled();
    await result("123456790");
    await page.keyboard.type("*2");
    await page.keyboard.press("Enter");
    await settled();
    await result("246913580");
    console.log("PASS: rapid keyboard input stays ordered and chains results");

    await reset();
    await click("math");
    assert.equal(await page.locator("#calculator-menu").isVisible(), true);
    const menuBox = await page.locator("#calculator-menu").boundingBox();
    const screenBox = await page.locator(".screen").boundingBox();
    const menuFace = await page.locator(".calc").boundingBox();
    assert.ok(
      menuBox.x >= screenBox.x &&
        menuBox.y >= screenBox.y &&
        menuBox.x + menuBox.width <= screenBox.x + screenBox.width &&
        menuBox.y + menuBox.height <= screenBox.y + screenBox.height,
    );
    assert.equal(menuFace.height, face.height);
    for (let index = 0; index < 5; index++) await click("down");
    const selectedItem = await page
      .locator(".menu-items .selected")
      .boundingBox();
    const itemWindow = await page.locator(".menu-items").boundingBox();
    assert.ok(
      selectedItem.y >= itemWindow.y &&
        selectedItem.y + selectedItem.height <=
          itemWindow.y + itemWindow.height + 1,
    );
    console.log(
      "PASS: menus stay inside the LCD, scroll to selection and preserve the casing",
    );
    await click("clear");
    await click("2nd");
    await click("sq");
    assert.equal(await page.locator("#calculator-menu").isVisible(), false);
    await page.keyboard.type("9)");
    await page.keyboard.press("Enter");
    await settled();
    await result("3");
    console.log("PASS: math menu opens once and evaluates square roots");

    await click("sto");
    await click("var");
    await click("var");
    await click("enter");
    assert.equal(
      (await (await page.request.get(base + "/state")).json()).memory.y,
      "3",
    );
    await click("2nd");
    await click("sto");
    await click("2");
    await page.keyboard.type("+1");
    await page.keyboard.press("Enter");
    await settled();
    await result("4");
    console.log(
      "PASS: guidebook memory storage and recall through the browser",
    );

    await reset();
    for (const key of ["1", "2nd", "7", "7", "down", "1", "2", "enter"])
      await click(key);
    await result("19/12");
    await reset();
    for (const key of ["2", "2nd", "frac", "enter"]) await click(key);
    await result("1/2");
    console.log(
      "PASS: mixed fraction and reciprocal actions match the physical blue legends",
    );

    await reset();
    await page.keyboard.type("1/0");
    await page.keyboard.press("Enter");
    await settled();
    assert.match(
      await page.locator("#error-line").textContent(),
      /DIVIDE BY 0/,
    );
    await click("clear");
    await click("clear");
    await page.keyboard.type("2+2");
    await page.keyboard.press("Enter");
    await settled();
    await result("4");
    console.log("PASS: math errors recover without stale messages");

    await context.setOffline(true);
    await page.waitForFunction(() =>
      document
        .getElementById("connection-status")
        .textContent.includes("Disconnected"),
    );
    await context.setOffline(false);
    await page.waitForFunction(
      () =>
        document.getElementById("connection-status").textContent ===
        "Connected",
      null,
      { timeout: 15000 },
    );
    assert.equal(await page.evaluate(() => window.eventSourcesCreated), 1);
    await page.locator("#reconnect-btn").click();
    await settled();
    await page.waitForFunction(
      () =>
        document.getElementById("connection-status").textContent ===
        "Connected",
    );
    const beforeRetry = presses.length;
    await click("lnlog");
    assert.deepEqual(presses.slice(beforeRetry), ["lnlog"]);
    console.log(
      "PASS: network reconnect and manual retry keep one event stream and one listener",
    );

    await reset();
    const animated = page.request.post(base + "/press_seq", {
      data: { keys: ["sin", "3", "0", "rparen", "enter"] },
    });
    await page
      .locator('[data-name="sin"].flash')
      .waitFor({ state: "attached" });
    assert.equal((await animated).status(), 200);
    await result("1/2");
    console.log("PASS: API key sequences animate in the browser");

    await reset();
    await click("mode");
    await page
      .locator(".menu-items button")
      .filter({ hasText: /^2: RAD/ })
      .click();
    await settled();
    await click("clear");
    assert.equal(
      (await (await page.request.get(base + "/state")).json()).angle,
      "RAD",
    );
    await reset();
    await click("2nd");
    await click("sin");
    await page.locator('#feature-form [name="expression"]').waitFor();
    await page.locator('#feature-form [name="expression"]').fill("x^2=2");
    await page.locator('#feature-form [name="guess"]').fill("1");
    await page.locator('#feature-form button[type="submit"]').click();
    await settled();
    const solverState = await (await page.request.get(base + "/state")).json();
    assert.equal(solverState.error, null);
    assert.ok(
      Math.abs(Number(solverState.feature_result.solution) - Math.SQRT2) <
        1e-10,
    );
    await reset();
    await click("table");
    await page
      .locator(".menu-items button")
      .filter({ hasText: "Edit function" })
      .click();
    await settled();
    await page.locator('#feature-form [name="expression"]').waitFor();
    await page.locator('#feature-form button[type="submit"]').click();
    await settled();
    const tableState = await (await page.request.get(base + "/state")).json();
    assert.equal(tableState.error, null);
    assert.equal(tableState.feature_result[1]["f(x)"], "324");
    console.log(
      "PASS: mode selection, numeric solver form and function table work",
    );

    for (const width of [320, 375, 740, 1100]) {
      await page.setViewportSize({ width, height: 900 });
      const dimensions = await page.evaluate(() => ({
        scroll: document.documentElement.scrollWidth,
        viewport: innerWidth,
      }));
      assert.ok(
        dimensions.scroll <= dimensions.viewport,
        `Horizontal overflow at ${width}px: ${JSON.stringify(dimensions)}`,
      );
    }
    await page.screenshot({
      path: process.env.BROWSER_SCREENSHOT || "/tmp/ti36x-browser.png",
      fullPage: true,
    });
    assert.deepEqual(errors, []);
    console.log(
      "PASS: mobile/desktop layouts fit and no JavaScript errors occurred",
    );
    await page.request.post(base + "/reset");
    console.log("13 browser checks passed.");
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
