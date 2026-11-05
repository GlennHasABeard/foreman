export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if ("" && !"".includes(".pages.dev") && url.hostname.endsWith(".pages.dev")) {
      return Response.redirect("" + url.pathname + url.search, 302);
    }
    if (url.pathname === "/api/checks") return checks(request, env, url);
    return env.ASSETS.fetch(request);
  },
};

// Checkmarks for each list page, kept in the CHECKS KV namespace so they
// follow you across browsers and devices. Same Access login as the pages.
async function checks(request, env, url) {
  const h = { "content-type": "application/json", "cache-control": "no-store" };
  const out = (body, status) => new Response(body, { status: status || 200, headers: h });
  if (!env.CHECKS) return out('{"error":"no CHECKS binding"}', 503);
  const page = url.searchParams.get("page") || "";
  if (!/^[A-Za-z0-9_.:-]{1,80}$/.test(page)) return out('{"error":"bad page"}', 400);
  const key = "checks:" + page;
  if (request.method === "GET") {
    const v = await env.CHECKS.get(key);
    return out(v === null ? "null" : v);
  }
  if (request.method === "PUT") {
    const body = await request.text();
    if (body.length > 200000) return out('{"error":"too big"}', 413);
    let obj;
    try { obj = JSON.parse(body); } catch (e) { return out('{"error":"bad json"}', 400); }
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return out('{"error":"bad json"}', 400);
    if (page.startsWith("marks-")) {
      // v1.1 page marks: merge with what is saved, newest mark wins per person,
      // so two devices saving at once never drop each other's marks
      let cur = null;
      try { cur = JSON.parse((await env.CHECKS.get(key)) || "null"); } catch (e) { cur = null; }
      obj = mergeMarks(cur, obj);
    }
    await env.CHECKS.put(key, JSON.stringify(obj), { expirationTtl: 60 * 60 * 24 * 180 });
    return out(page.startsWith("marks-") ? JSON.stringify(obj) : '{"ok":true}');
  }
  return out('{"error":"method"}', 405);
}

function mergeMarks(a, b) {
  const o = {};
  a = a && typeof a === "object" ? a : {};
  b = b && typeof b === "object" ? b : {};
  for (const k of ["never", "done", "stages", "follow_ups"]) {
    o[k] = Object.assign({}, a[k] || {});
    for (const [h, e] of Object.entries(b[k] || {})) {
      const c = o[k][h];
      if (!c || String((e && e.ts) || "") >= String((c && c.ts) || "")) o[k][h] = e;
    }
  }
  o.notes = {};
  for (const src of [a.notes || {}, b.notes || {}]) {
    for (const [h, ns] of Object.entries(src)) {
      const have = o.notes[h] || (o.notes[h] = []);
      for (const n of Array.isArray(ns) ? ns : []) if (!have.some(x => x.ts === n.ts)) have.push(n);
    }
  }
  return o;
}
