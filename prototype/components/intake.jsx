// ARTIS — Add Client: blueprint upload tab. text/babel → window.

function IntakeClient() {
  const [file, setFile] = React.useState(null);
  const [drag, setDrag] = React.useState(false);
  const [status, setStatus] = React.useState("idle"); // idle | uploading | done | error
  const [msg, setMsg] = React.useState("");
  const [savedName, setSavedName] = React.useState("");
  const [code, setCode] = React.useState("");
  const inputRef = React.useRef(null);

  const pickFile = (f) => {
    if (!f) return;
    if (!/\.(md|markdown|txt)$/i.test(f.name)) {
      setStatus("error");
      setMsg("Please choose a Markdown blueprint (.md).");
      setFile(null);
      return;
    }
    setFile(f);
    setStatus("idle");
    setMsg("");
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    pickFile(e.dataTransfer.files && e.dataTransfer.files[0]);
  };

  const submit = async () => {
    if (!file) return;
    setStatus("uploading");
    setMsg("");
    try {
      const text = await file.text();
      const headers = { "Content-Type": "text/markdown; charset=utf-8", "X-Filename": file.name };
      if (code.trim()) headers["X-Upload-Token"] = code.trim();
      const res = await fetch("/api/upload-blueprint", { method: "POST", headers, body: text });
      if (res.status === 401) throw new Error("Invalid or missing access code.");
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) throw new Error(data.error || ("HTTP " + res.status));
      setSavedName(data.filename || file.name);
      setStatus("done");
    } catch (e) {
      setStatus("error");
      setMsg(
        /Failed to fetch|NetworkError/i.test(e.message)
          ? "Couldn't reach the intake server. Start it with: python serve.py"
          : (e.message || "Upload failed.")
      );
    }
  };

  const reset = () => { setFile(null); setStatus("idle"); setMsg(""); setSavedName(""); };

  if (status === "done") {
    return (
      <div className="ec-intake">
        <div className="ec-intake-done">
          <div className="ec-intake-check"><Icon name="sparkle" size={26} /></div>
          <h2 className="ec-intake-done-title">Blueprint queued</h2>
          <p className="ec-intake-done-sub">
            <b>{savedName}</b> has been added to the intake folder. The next time the
            research pipeline runs, this firm's profile and tailored strategy will appear
            here alongside Doniphan Moore — scored against every trend by the Artis engine.
          </p>
          <button className="ec-btn" onClick={reset}>Add another <Icon name="arrow-right" size={15} /></button>
        </div>
      </div>
    );
  }

  return (
    <div className="ec-intake">
      <div className="ec-pickclient-head">
        <h2>Add a client</h2>
        <p>Upload a content blueprint (Markdown). It's queued for the next pipeline run — the
          firm is then profiled and every trend scored against its convictions, just like Doniphan Moore.</p>
      </div>

      <label
        className={"ec-drop" + (drag ? " is-drag" : "") + (file ? " has-file" : "")}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".md,.markdown,.txt,text/markdown"
          style={{ display: "none" }}
          onChange={(e) => pickFile(e.target.files && e.target.files[0])}
        />
        <span className="ec-drop-ico"><Icon name="layers" size={30} /></span>
        {file ? (
          <span className="ec-drop-file">{file.name}<span className="ec-drop-size">{(file.size / 1024).toFixed(1)} KB</span></span>
        ) : (
          <>
            <span className="ec-drop-title">Drop a blueprint here</span>
            <span className="ec-drop-sub">or click to choose a .md file</span>
          </>
        )}
      </label>

      <div className="ec-intake-field">
        <label className="ec-intake-label">Access code <span>— if this workspace is gated</span></label>
        <input className="ec-intake-input" type="password" value={code} autoComplete="off"
          onChange={(e) => setCode(e.target.value)} placeholder="Leave blank if uploads are open" />
      </div>

      {status === "error" && <p className="ec-intake-err">{msg}</p>}

      <div className="ec-intake-actions">
        <button className="ec-btn" disabled={!file || status === "uploading"} onClick={submit}
          style={!file || status === "uploading" ? { opacity: .5, pointerEvents: "none" } : null}>
          {status === "uploading" ? "Uploading…" : "Queue for next run"}
          {status !== "uploading" && <Icon name="arrow-right" size={15} />}
        </button>
        {file && status !== "uploading" && (
          <button className="ec-btn ec-btn--ghost" onClick={reset}>Clear</button>
        )}
      </div>

      <div className="ec-intake-note">
        <Eyebrow>How it works</Eyebrow>
        <ol className="ec-intake-steps">
          <li>Your blueprint is saved to the pipeline's intake folder.</li>
          <li>On the next orchestration run, the editorial engine builds a profile + strategy for the firm.</li>
          <li>The app dataset is rebuilt and the new client appears under <b>By Client</b>.</li>
        </ol>
      </div>
    </div>
  );
}

Object.assign(window, { IntakeClient });
