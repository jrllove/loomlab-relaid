self.loomlabPing = async (url) => {
  const response = await fetch(url, { method: "POST", body: "PING" });
  if (!response.ok) {
    throw new Error(`Local PING failed: HTTP ${response.status}`);
  }
  return response.text();
};

const unknown = (reason, pageIsChatGPT = null) => ({
  browser_state: "browser_state_unknown",
  page_is_chatgpt: pageIsChatGPT,
  authenticated: null,
  conversation_ref: null,
  conversation_url: null,
  response_streaming: null,
  reason,
});

function isChatGPT(url) {
  try {
    return new URL(url).origin === "https://chatgpt.com";
  } catch {
    return false;
  }
}

async function activeTab() {
  const tabs = await chrome.tabs.query({ active: true });
  if (tabs.length !== 1) return { error: tabs.length ? "ambiguous_active_tab" : "no_active_tab" };
  if (typeof tabs[0].url !== "string") return { error: "tab_url_unavailable" };
  return { tab: tabs[0] };
}

self.loomlabObserve = async () => {
  try {
    const firstTab = await activeTab();
    if (firstTab.error) return unknown(firstTab.error);
    if (!isChatGPT(firstTab.tab.url)) return unknown("not_chatgpt", false);

    const first = await chrome.tabs.sendMessage(firstTab.tab.id, { type: "loomlab.observe" });
    await new Promise((resolve) => setTimeout(resolve, 350));
    const secondTab = await activeTab();
    if (secondTab.error || secondTab.tab.id !== firstTab.tab.id ||
        secondTab.tab.url !== firstTab.tab.url) {
      return unknown("unstable_observation", true);
    }
    const second = await chrome.tabs.sendMessage(firstTab.tab.id, { type: "loomlab.observe" });
    if (!first || !second || JSON.stringify(first) !== JSON.stringify(second)) {
      return unknown("unstable_observation", true);
    }
    return second;
  } catch {
    return unknown("observer_unavailable", true);
  }
};
