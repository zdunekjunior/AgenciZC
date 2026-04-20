const els = (id) => document.getElementById(id);

const state = {
  pending: [],
  selected: null,
  cases: [],
};

function fmtTs(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

function toast(msg, kind = "ok") {
  const t = els("toast");
  t.textContent = msg;
  t.classList.remove("hidden", "ok", "err");
  t.classList.add(kind === "err" ? "err" : "ok");
  setTimeout(() => t.classList.add("hidden"), 3500);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const text = await res.text();
  let json = null;
  try { json = text ? JSON.parse(text) : null; } catch { /* ignore */ }
  if (!res.ok) {
    const detail = json?.detail ? ` — ${json.detail}` : "";
    throw new Error(`${res.status} ${res.statusText}${detail}`);
  }
  return json;
}

function yn(v) {
  return v ? "yes" : "—";
}

function trunc(s, n = 80) {
  if (!s) return "—";
  const t = String(s);
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
}

function renderCases() {
  const tbody = els("casesTbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  const rows = state.cases || [];
  els("casesMeta").textContent = `${rows.length} item(s)`;
  els("casesEmpty").classList.toggle("hidden", rows.length !== 0);
  els("casesTable").classList.toggle("hidden", rows.length === 0);

  for (const c of rows) {
    const tr = document.createElement("tr");
    const agents = (c.assigned_agents || []).join(", ");
    const drafts = (c.draft_ids || []).length ? String((c.draft_ids || []).length) : "—";
    const risksN = Array.isArray(c.key_risks) ? c.key_risks.length : 0;
    const qN = Array.isArray(c.key_questions) ? c.key_questions.length : 0;
    tr.innerHTML = `
      <td class="mono">${c.case_id}</td>
      <td>${c.subject || "—"}</td>
      <td>${c.current_status || "—"}</td>
      <td>${c.lead_stage || "—"}</td>
      <td>${c.recommended_next_action || "—"}</td>
      <td>${yn(c.expert_summary)}</td>
      <td>${risksN ? String(risksN) : "—"}</td>
      <td>${qN ? String(qN) : "—"}</td>
      <td>${trunc(c.recommended_expert_next_step, 70)}</td>
      <td>${agents || "—"}</td>
      <td>${drafts}</td>
      <td>${yn(c.lead_summary)}</td>
      <td>${yn(c.research_summary)}</td>
    `;
    tbody.appendChild(tr);
  }
}

function renderPending() {
  const tbody = els("pendingTbody");
  tbody.innerHTML = "";
  const rows = state.pending || [];
  els("pendingMeta").textContent = `${rows.length} item(s)`;
  els("pendingEmpty").classList.toggle("hidden", rows.length !== 0);
  els("pendingTable").classList.toggle("hidden", rows.length === 0);

  for (const d of rows) {
    const tr = document.createElement("tr");
    tr.dataset.draftId = d.draft_id;
    if (state.selected?.draft_id === d.draft_id) tr.classList.add("selected");
    tr.innerHTML = `
      <td class="mono">${d.draft_id}</td>
      <td>${d.provider || "—"}</td>
      <td class="mono">${d.message_id || "—"}</td>
      <td class="mono">${d.thread_id || "—"}</td>
      <td>${fmtTs(d.created_at)}</td>
      <td>${d.status}</td>
    `;
    tr.addEventListener("click", () => selectDraft(d.draft_id));
    tbody.appendChild(tr);
  }
}

function setSelectedUI(d) {
  els("selectedMeta").textContent = d ? `Wybrany: ${d.draft_id}` : "Nie wybrano draftu";
  els("d_draft_id").textContent = d?.draft_id || "—";
  els("d_provider").textContent = d?.provider || "—";
  els("d_message_id").textContent = d?.message_id || "—";
  els("d_thread_id").textContent = d?.thread_id || "—";
  els("d_created_at").textContent = fmtTs(d?.created_at);
  els("d_status").textContent = d?.status || "—";
  els("d_preview").textContent = d?.draft_preview || "—";
  const ls = d?.lead_scoring || null;
  els("d_lead_score").textContent = ls ? String(ls.lead_score) : "—";
  els("d_lead_temp").textContent = ls ? ls.lead_temperature : "—";
  els("d_lead_intent").textContent = ls ? ls.business_intent : "—";
  els("d_lead_priority").textContent = ls ? ls.sales_priority : "—";

  const has = !!d;
  els("approveBtn").disabled = !has;
  els("rejectBtn").disabled = !has;
  els("sendBtn").disabled = !has;
}

function renderAudit(events) {
  const tbody = els("auditTbody");
  tbody.innerHTML = "";
  const rows = events || [];
  els("auditEmpty").classList.toggle("hidden", rows.length !== 0);
  els("auditTable").classList.toggle("hidden", rows.length === 0);

  for (const e of rows) {
    const tr = document.createElement("tr");
    const actor = `${e.actor_type}/${e.actor_name}`;
    const meta = e.metadata ? JSON.stringify(e.metadata) : "{}";
    tr.innerHTML = `
      <td>${fmtTs(e.timestamp)}</td>
      <td class="mono">${e.action}</td>
      <td>${actor}</td>
      <td>${e.status}</td>
      <td class="mono">${meta}</td>
    `;
    tbody.appendChild(tr);
  }
}

async function loadPending() {
  const data = await api("/drafts/pending");
  state.pending = data?.drafts || [];
  if (state.selected) {
    const still = state.pending.find((x) => x.draft_id === state.selected.draft_id);
    state.selected = still || state.selected;
  }
  renderPending();
}

async function loadCases() {
  const rows = await api("/cases?limit=50");
  state.cases = Array.isArray(rows) ? rows : [];
  renderCases();
}

async function selectDraft(draftId) {
  const d = state.pending.find((x) => x.draft_id === draftId) || null;
  state.selected = d;
  setSelectedUI(d);
  renderPending();

  if (!d) return;
  try {
    const ev = await api(`/audit/events/${encodeURIComponent(d.draft_id)}?limit=200`);
    renderAudit(ev?.events || []);
  } catch (e) {
    renderAudit([]);
    toast(`Audit: ${e.message}`, "err");
  }
}

async function doAction(kind) {
  const d = state.selected;
  if (!d) return;
  const id = d.draft_id;
  const url = `/drafts/${encodeURIComponent(id)}/${kind}`;
  try {
    const out = await api(url, { method: "POST" });
    toast(`${kind.toUpperCase()} OK (${out?.draft?.status || "—"})`, "ok");
    await loadPending();
    // after approve/reject/send it might disappear from pending; still show audit for the id
    state.selected = out?.draft || { ...d, status: out?.draft?.status };
    setSelectedUI(state.selected);
    const ev = await api(`/audit/events/${encodeURIComponent(id)}?limit=200`);
    renderAudit(ev?.events || []);
  } catch (e) {
    toast(`${kind.toUpperCase()} failed: ${e.message}`, "err");
  }
}

function bind() {
  els("refreshBtn").addEventListener("click", async () => {
    try { await loadPending(); toast("Odświeżono", "ok"); } catch (e) { toast(e.message, "err"); }
    try { await loadCases(); } catch (e) { /* ignore */ }
  });
  els("logoutBtn").addEventListener("click", async () => {
    try {
      await api("/admin/logout", { method: "POST" });
      window.location.href = "/admin";
    } catch (e) {
      toast(`Logout failed: ${e.message}`, "err");
    }
  });
  els("approveBtn").addEventListener("click", () => doAction("approve"));
  els("rejectBtn").addEventListener("click", () => doAction("reject"));
  els("sendBtn").addEventListener("click", () => doAction("send"));
}

async function boot() {
  bind();
  setSelectedUI(null);
  renderAudit([]);
  try {
    await loadPending();
    await loadCases();
  } catch (e) {
    toast(`Nie udało się pobrać pending drafts: ${e.message}`, "err");
  }
}

boot();

