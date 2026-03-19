const ACTIVE_REQUESTS_KEY = "aba_active_agent_requests";
const GOOGLE_DRAFT_KEY = "aba_google_agent_draft";

function readLocalStore(key, fallback = []) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
    if (Array.isArray(fallback)) {
      return Array.isArray(parsed) ? parsed : fallback;
    }
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function writeLocalStore(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function readSessionStore(key, fallback = null) {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(key) || "null");
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function writeSessionStore(key, value) {
  sessionStorage.setItem(key, JSON.stringify(value));
}

function rememberActiveRequest(requestId, agentType) {
  const id = String(requestId);
  const rows = readLocalStore(ACTIVE_REQUESTS_KEY, []).filter((row) => String(row.request_id) !== id);

  rows.unshift({
    request_id: id,
    agent_type: agentType,
    started_at: new Date().toISOString(),
    status: "Running",
  });

  writeLocalStore(ACTIVE_REQUESTS_KEY, rows.slice(0, 50));
}

export function rememberSalesNavRequest(requestId) {
  rememberActiveRequest(requestId, "salesnav");
}

export function markSalesNavRequestFinal(requestId, status) {
  const id = String(requestId);
  const rows = readLocalStore(ACTIVE_REQUESTS_KEY, []).map((row) =>
    String(row.request_id) === id ? { ...row, status: status || row.status } : row
  );
  writeLocalStore(ACTIVE_REQUESTS_KEY, rows);
}

export function getActiveSalesNavRequests() {
  return readLocalStore(ACTIVE_REQUESTS_KEY, []).filter((row) => row.status === "Running" && row.agent_type === "salesnav");
}

export function saveGoogleDraft(draft) {
  writeSessionStore(GOOGLE_DRAFT_KEY, draft || {});
}

export function getGoogleDraft() {
  return readSessionStore(GOOGLE_DRAFT_KEY, null);
}

export function rememberGoogleActiveRequest(requestId) {
  rememberActiveRequest(requestId, "google");
}

export function getGoogleActiveRequest() {
  return readLocalStore(ACTIVE_REQUESTS_KEY, []).find(
    (row) => row.status === "Running" && row.agent_type === "google"
  ) || null;
}

export function clearGoogleActiveRequest() {
  const rows = readLocalStore(ACTIVE_REQUESTS_KEY, []).map((row) =>
    row.agent_type === "google" && row.status === "Running" ? { ...row, status: "Stopped" } : row
  );
  writeLocalStore(ACTIVE_REQUESTS_KEY, rows);
}

export function rememberEnrichmentActiveRequest(requestId) {
  rememberActiveRequest(requestId, "enrichment");
}

export function getEnrichmentActiveRequest() {
  return readLocalStore(ACTIVE_REQUESTS_KEY, []).find(
    (row) => row.status === "Running" && row.agent_type === "enrichment"
  ) || null;
}
