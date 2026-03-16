const STORAGE_KEY = "aba_active_salesnav_requests";

function readStore() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeStore(rows) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(rows));
}

export function rememberSalesNavRequest(requestId) {
  const id = String(requestId);
  const rows = readStore().filter((row) => String(row.request_id) !== id);

  rows.unshift({
    request_id: id,
    started_at: new Date().toISOString(),
    status: "Running",
  });

  writeStore(rows.slice(0, 20));
}

export function markSalesNavRequestFinal(requestId, status) {
  const id = String(requestId);
  const rows = readStore().map((row) =>
    String(row.request_id) === id ? { ...row, status: status || row.status } : row
  );
  writeStore(rows);
}

export function getActiveSalesNavRequests() {
  return readStore().filter((row) => row.status === "Running");
}
