<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AI Code Helper</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: system-ui, Arial, sans-serif; margin: 24px; }
    textarea { width: 100%; height: 140px; }
    pre { background:#111; color:#eee; padding:12px; overflow:auto; }
    .btn { padding:10px 14px; margin-right:8px; cursor:pointer; }
  </style>
</head>
<body>
  <h1>AI Code Helper</h1>
  <p>Describe what you want changed. Example: “Wire missions.html to show real missions from app.py and fix broken links.”</p>
  <textarea id="instruction" placeholder="Type your instruction..."></textarea><br>
  <button class="btn" id="planBtn">Plan (dry run)</button>
  <button class="btn" id="applyBtn" disabled>Apply</button>
  <div id="out"></div>

  <script>
    const out = document.getElementById('out');
    const planBtn = document.getElementById('planBtn');
    const applyBtn = document.getElementById('applyBtn');
    let lastPlan = null;

    planBtn.onclick = async () => {
      out.innerHTML = "Planning…";
      applyBtn.disabled = true;
      const instruction = document.getElementById('instruction').value;
      const res = await fetch('/admin/ai/plan', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({instruction})
      });
      const data = await res.json();
      if (!res.ok) { out.innerHTML = `<pre>${JSON.stringify(data,null,2)}</pre>`; return; }
      lastPlan = data.plan;
      applyBtn.disabled = !lastPlan || !lastPlan.changes || !lastPlan.changes.length;
      out.innerHTML = `<h3>Proposed changes</h3>
        <ul>${(data.preview||[]).map(p=>`<li>${p}</li>`).join('')}</ul>
        <details><summary>Full JSON</summary><pre>${JSON.stringify(data.plan,null,2)}</pre></details>`;
    };

    applyBtn.onclick = async () => {
      if (!lastPlan) return;
      out.innerHTML = "Applying…";
      const res = await fetch('/admin/ai/apply', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(lastPlan)
      });
      const data = await res.json();
      out.innerHTML = `<pre>${JSON.stringify(data,null,2)}</pre>`;
    };
  </script>
</body>
</html>