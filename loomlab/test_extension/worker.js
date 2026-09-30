self.loomlabPing = async (url) => {
  const response = await fetch(url, { method: "POST", body: "PING" });
  if (!response.ok) {
    throw new Error(`Local PING failed: HTTP ${response.status}`);
  }
  return response.text();
};
