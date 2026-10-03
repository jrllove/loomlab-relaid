// ChatGPT-specific DOM knowledge lives only in this isolated extension script.
// Observation reads the page; it never writes to the DOM or reads message text.
(() => {
  const UNKNOWN = "browser_state_unknown";
  const ORIGIN = "https://chatgpt.com";

  const unknown = (reason, extras = {}) => ({
    browser_state: UNKNOWN,
    page_is_chatgpt: true,
    authenticated: null,
    conversation_ref: null,
    conversation_url: null,
    response_streaming: null,
    reason,
    ...extras,
  });

  function visible(element) {
    if (!element || element.getClientRects().length === 0) return false;
    if (element.checkVisibility && !element.checkVisibility({ checkOpacity: true })) return false;
    const style = getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden";
  }

  function visibleMatches(selector) {
    return [...document.querySelectorAll(selector)].filter(visible);
  }

  function conversationReference(url) {
    // Only a normal conversation route is exported. Queries and fragments may
    // contain sensitive data and are never returned or logged.
    const match = url.pathname.match(/^\/(?:g\/[A-Za-z0-9-]{8,128}\/)?c\/([A-Za-z0-9-]{8,128})\/?$/);
    if (!match) return { conversation_ref: null, conversation_url: null };
    return {
      conversation_ref: match[1],
      conversation_url: `${ORIGIN}${url.pathname.replace(/\/$/, "")}`,
    };
  }

  function observePage() {
    let url;
    try {
      url = new URL(location.href);
    } catch {
      return unknown("invalid_page_url");
    }
    if (url.origin !== ORIGIN) return unknown("unexpected_origin", { page_is_chatgpt: false });

    const conversation = conversationReference(url);
    if (document.readyState === "loading") return unknown("page_loading", conversation);
    if (url.pathname.startsWith("/auth/")) {
      return unknown("signed_out", { ...conversation, authenticated: false });
    }
    if (url.pathname !== "/" && !conversation.conversation_ref) {
      return unknown("unsupported_page");
    }

    const profile = visibleMatches(
      '[data-testid="accounts-profile-button"], button[data-testid="profile-button"], button[aria-label="Open profile menu"]',
    );
    const login = visibleMatches(
      'a[href="/auth/login"], a[href="https://chatgpt.com/auth/login"], button[data-testid="login-button"]',
    );
    if (profile.length && login.length) return unknown("conflicting_auth_signals", conversation);
    if (login.length) return unknown("signed_out", { ...conversation, authenticated: false });
    if (profile.length !== 1) return unknown("auth_unknown", conversation);

    const authenticated = { ...conversation, authenticated: true };
    if (visibleMatches('[role="dialog"], [aria-modal="true"]').length) {
      return unknown("modal_open", authenticated);
    }
    const composer = visibleMatches('[data-testid="composer-input"], #prompt-textarea');
    if (composer.length !== 1) return unknown("composer_unavailable", authenticated);

    const stop = visibleMatches(
      'button[data-testid="stop-button"], button[aria-label="Stop generating"], button[aria-label="Stop streaming"]',
    );
    if (stop.length > 1 || (stop.length === 1 && stop[0].disabled)) {
      return unknown("streaming_signal_ambiguous", authenticated);
    }
    const responseStreaming = stop.length === 1;
    return {
      browser_state: responseStreaming ? "streaming" : "ready",
      page_is_chatgpt: true,
      authenticated: true,
      ...conversation,
      response_streaming: responseStreaming,
      reason: null,
    };
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "loomlab.observe") return;
    try {
      sendResponse(observePage());
    } catch {
      sendResponse(unknown("observation_error"));
    }
  });
})();
