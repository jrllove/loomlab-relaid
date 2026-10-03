const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const extension = path.join(__dirname, "..", "loomlab", "test_extension");
const observerSource = fs.readFileSync(path.join(extension, "observer.js"), "utf8");
const workerSource = fs.readFileSync(path.join(extension, "worker.js"), "utf8");

function element(selector, options = {}) {
  return {
    selector,
    disabled: options.disabled ?? false,
    hidden: options.hidden ?? false,
    getClientRects() { return this.hidden ? [] : [{}]; },
  };
}

function observe(url, elements = [], readyState = "complete") {
  let listener;
  const sandbox = {
    URL,
    location: { href: url },
    document: {
      readyState,
      querySelectorAll(selectors) {
        const parts = selectors.split(",").map((part) => part.trim());
        return elements.filter((item) => parts.includes(item.selector));
      },
    },
    getComputedStyle: () => ({ display: "block", visibility: "visible" }),
    chrome: { runtime: { onMessage: { addListener(callback) { listener = callback; } } } },
  };
  vm.runInNewContext(observerSource, sandbox);
  let result;
  listener({ type: "loomlab.observe" }, null, (value) => { result = value; });
  return JSON.parse(JSON.stringify(result));
}

const profile = element('[data-testid="accounts-profile-button"]');
const composer = element('[data-testid="composer-input"]');
const stop = element('button[data-testid="stop-button"]');
const conversation = "12345678-1234-1234-1234-123456789abc";

test("ready observation is stable, read-only, and omits URL query and fragment", () => {
  const result = observe(
    `https://chatgpt.com/c/${conversation}?token=secret#prompt=secret`,
    [profile, composer],
  );
  assert.equal(result.browser_state, "ready");
  assert.equal(result.authenticated, true);
  assert.equal(result.response_streaming, false);
  assert.equal(result.conversation_ref, conversation);
  assert.equal(result.conversation_url, `https://chatgpt.com/c/${conversation}`);
  assert.equal(JSON.stringify(result).includes("secret"), false);
});

test("visible stop control reports streaming", () => {
  const result = observe("https://chatgpt.com/", [profile, composer, stop]);
  assert.equal(result.browser_state, "streaming");
  assert.equal(result.response_streaming, true);
  assert.equal(
    observe("https://chatgpt.com/", [profile, composer, element('button[aria-label="Stop generating"]')]).browser_state,
    "streaming",
  );
});

test("guest composer cannot establish authentication", () => {
  const result = observe("https://chatgpt.com/", [composer]);
  assert.equal(result.browser_state, "browser_state_unknown");
  assert.equal(result.authenticated, null);
  assert.equal(result.response_streaming, null);
});

test("non-conversation ChatGPT routes do not report ready", () => {
  const result = observe("https://chatgpt.com/share/12345678", [profile, composer]);
  assert.equal(result.page_is_chatgpt, true);
  assert.equal(result.browser_state, "browser_state_unknown");
  assert.equal(result.reason, "unsupported_page");
});

test("explicit login and conflicting UI fail closed", () => {
  const login = element('a[href="/auth/login"]');
  assert.equal(observe("https://chatgpt.com/", [login, composer]).authenticated, false);
  assert.equal(
    observe("https://chatgpt.com/", [profile, login, composer]).reason,
    "conflicting_auth_signals",
  );
});

test("modal, disabled stop button, and loading page are unknown", () => {
  assert.equal(
    observe("https://chatgpt.com/", [profile, composer, element('[role="dialog"]')]).reason,
    "modal_open",
  );
  assert.equal(
    observe("https://chatgpt.com/", [profile, composer, element(stop.selector, { disabled: true })]).reason,
    "streaming_signal_ambiguous",
  );
  assert.equal(observe("https://chatgpt.com/", [profile, composer], "loading").reason, "page_loading");
});

async function observeActive(tabs, replies = []) {
  let calls = 0;
  const sandbox = {
    URL,
    self: {},
    setTimeout: (callback) => callback(),
    chrome: {
      tabs: {
        query: async () => tabs[Math.min(calls, tabs.length - 1)],
        sendMessage: async () => replies.shift(),
      },
    },
  };
  // Count tab reads so tests can change the active tab between samples.
  sandbox.chrome.tabs.query = async () => tabs[Math.min(calls++, tabs.length - 1)];
  vm.runInNewContext(workerSource, sandbox);
  return JSON.parse(JSON.stringify(await sandbox.self.loomlabObserve()));
}

test("non-ChatGPT tab is reported without contacting a content script", async () => {
  const result = await observeActive([[{ id: 1, url: "https://example.com/" }]]);
  assert.equal(result.page_is_chatgpt, false);
  assert.equal(result.browser_state, "browser_state_unknown");
  assert.equal(result.reason, "not_chatgpt");
});

test("changed active tab or changed page sample is unknown", async () => {
  const tab = { id: 1, url: "https://chatgpt.com/" };
  const ready = observe("https://chatgpt.com/", [profile, composer]);
  const streaming = observe("https://chatgpt.com/", [profile, composer, stop]);
  assert.equal(
    (await observeActive([[tab], [{ id: 2, url: tab.url }]], [ready])).reason,
    "unstable_observation",
  );
  assert.equal(
    (await observeActive([[tab], [tab]], [ready, streaming])).reason,
    "unstable_observation",
  );
});
