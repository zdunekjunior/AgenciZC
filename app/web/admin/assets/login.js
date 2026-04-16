const els = (id) => document.getElementById(id);

function toast(msg, kind = "ok") {
  const t = els("toast");
  t.textContent = msg;
  t.classList.remove("hidden", "ok", "err");
  t.classList.add(kind === "err" ? "err" : "ok");
  setTimeout(() => t.classList.add("hidden"), 3500);
}

async function apiLogin(password) {
  const res = await fetch("/admin/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
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

function bind() {
  const form = els("loginForm");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const pw = els("password").value || "";
    try {
      await apiLogin(pw);
      toast("Zalogowano", "ok");
      window.location.href = "/admin";
    } catch (err) {
      toast(`Login failed: ${err.message}`, "err");
    }
  });
}

bind();

