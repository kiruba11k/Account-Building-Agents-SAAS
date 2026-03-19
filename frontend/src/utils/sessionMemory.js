const SALESNAV_KEY = "aba_active_salesnav_requests";
const GOOGLE_ACTIVE_KEY = "aba_active_google_request";
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

export function rememberSalesNavRequest(requestId) {
  const id = String(requestId);
  const rows = readLocalStore(SALESNAV_KEY, []).filter((row) => String(row.request_id) !== id);

  rows.unshift({
    request_id: id,
    started_at: new Date().toISOString(),
    status: "Running",
  });

  writeLocalStore(SALESNAV_KEY, rows.slice(0, 20));
}

export function markSalesNavRequestFinal(requestId, status) {
  const id = String(requestId);
  const rows = readLocalStore(SALESNAV_KEY, []).map((row) =>
    String(row.request_id) === id ? { ...row, status: status || row.status } : row
  );
  writeLocalStore(SALESNAV_KEY, rows);

  const googleActive = getGoogleActiveRequest();
  if (googleActive?.request_id === id && ["Completed", "Failed", "Timeout"].includes(status)) {
    clearGoogleActiveRequest();
  }
}

export function getActiveSalesNavRequests() {
  return readLocalStore(SALESNAV_KEY, []).filter((row) => row.status === "Running");
}

export function saveGoogleDraft(draft) {
  writeSessionStore(GOOGLE_DRAFT_KEY, draft || {});
}

export function getGoogleDraft() {
  return readSessionStore(GOOGLE_DRAFT_KEY, null);
}

export function rememberGoogleActiveRequest(requestId) {
  writeSessionStore(GOOGLE_ACTIVE_KEY, {
    request_id: String(requestId),
    started_at: new Date().toISOString(),
    status: "Running",
  });
}

export function getGoogleActiveRequest() {
  return readSessionStore(GOOGLE_ACTIVE_KEY, null);
}

export function clearGoogleActiveRequest() {
  sessionStorage.removeItem(GOOGLE_ACTIVE_KEY);
}
