// Vercel serverless function — commit an uploaded blueprint into a GitHub folder.
//
// The deployed "Add Client" tab POSTs the blueprint here; this function commits it
// to a GitHub repo folder via the Contents API. The automation pipeline then pulls
// that folder before each run (see github_blueprints.py).
//
// Required env vars (set in the Vercel project → Settings → Environment Variables):
//   GITHUB_TOKEN          fine-grained PAT with "Contents: Read and write" on the repo
//   GITHUB_REPO           "owner/repo"
// Optional:
//   GITHUB_BRANCH         default "main"
//   GITHUB_BLUEPRINT_DIR  default "blueprints"
//   UPLOAD_TOKEN          if set, requests must send a matching "X-Upload-Token" header
//
// Runs on the Node runtime (global fetch + Buffer, Node 18+). CommonJS to avoid ESM config.

function sanitize(name) {
  let b = String(name || "").split(/[\\/]/).pop() || "client-blueprint.md";
  b = b.replace(/[^A-Za-z0-9._-]/g, "_").replace(/^[._]+|[._]+$/g, "") || "client-blueprint";
  if (!/\.(md|markdown|txt)$/i.test(b)) b += ".md";
  return b.replace(/\.(markdown|txt)$/i, ".md");
}

async function readBody(req) {
  if (typeof req.body === "string") return req.body;
  if (Buffer.isBuffer(req.body)) return req.body.toString("utf8");
  if (req.body && typeof req.body === "object") return JSON.stringify(req.body);
  return await new Promise((resolve, reject) => {
    let d = "";
    req.setEncoding("utf8");
    req.on("data", (c) => (d += c));
    req.on("end", () => resolve(d));
    req.on("error", reject);
  });
}

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ ok: false, error: "POST only" });

  const need = process.env.UPLOAD_TOKEN;
  if (need && req.headers["x-upload-token"] !== need)
    return res.status(401).json({ ok: false, error: "unauthorized" });

  const repo = process.env.GITHUB_REPO;
  const token = process.env.GITHUB_TOKEN;
  const branch = process.env.GITHUB_BRANCH || "main";
  const dir = process.env.GITHUB_BLUEPRINT_DIR || "blueprints";
  if (!repo || !token)
    return res.status(500).json({ ok: false, error: "server not configured (GITHUB_REPO / GITHUB_TOKEN)" });

  try {
    const filename = sanitize(req.headers["x-filename"] || "client-blueprint.md");
    const text = await readBody(req);
    if (!text || !text.trim()) return res.status(400).json({ ok: false, error: "empty upload" });

    const path = `${dir}/${filename}`;
    const api = `https://api.github.com/repos/${repo}/contents/${path.split("/").map(encodeURIComponent).join("/")}`;
    const gh = (extra) => ({
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "artis-uploader",
      ...extra,
    });

    // If the file already exists we must pass its blob sha to update it.
    let sha;
    const cur = await fetch(`${api}?ref=${encodeURIComponent(branch)}`, { headers: gh() });
    if (cur.status === 200) sha = (await cur.json()).sha;

    const put = await fetch(api, {
      method: "PUT",
      headers: gh({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        message: `Add client blueprint: ${filename}`,
        content: Buffer.from(text, "utf8").toString("base64"),
        branch,
        ...(sha ? { sha } : {}),
      }),
    });

    if (!put.ok) {
      const e = await put.text();
      return res.status(502).json({ ok: false, error: `GitHub ${put.status}: ${e.slice(0, 200)}` });
    }

    return res.status(200).json({ ok: true, filename, path });
  } catch (e) {
    return res.status(500).json({ ok: false, error: String(e && e.message ? e.message : e) });
  }
};
