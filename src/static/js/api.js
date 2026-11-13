export async function api(path, { method = "GET", body, params } = {}) {
  const url = new URL("/api" + path, location.origin);
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== "" && v != null) url.searchParams.set(k, v);
  }
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Cannot reach the server. Is it running?");
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.detail ?? `Request failed (${res.status})`);
  return data;
}
