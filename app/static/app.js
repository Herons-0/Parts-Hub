// Minimal vanilla JS: the "add to project" modal.
let currentProductId = null;

async function openModal(productId) {
  currentProductId = productId;
  document.getElementById("modal").classList.remove("hidden");
  document.getElementById("modal-qty").value = 1;
  const box = document.getElementById("modal-projects");
  box.innerHTML = "Loading…";

  const projects = await fetch("/api/projects").then((r) => r.json());
  if (!projects.length) {
    box.innerHTML = "<p class='muted'>No projects yet — create one below.</p>";
    return;
  }
  box.innerHTML = "";
  for (const p of projects) {
    const btn = document.createElement("button");
    btn.className = "project-pick";
    btn.textContent = `${p.name} (${p.item_count})`;
    btn.onclick = () => addToProject(p.id);
    box.appendChild(btn);
  }
}

function closeModal() {
  document.getElementById("modal").classList.add("hidden");
  currentProductId = null;
}

function qty() {
  return parseInt(document.getElementById("modal-qty").value || "1", 10);
}

async function addToProject(projectId) {
  await fetch(`/api/projects/${projectId}/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: currentProductId, quantity: qty() }),
  });
  toast("Added to project");
  closeModal();
}

async function createAndAdd() {
  const name = document.getElementById("new-project-name").value.trim();
  if (!name) return;
  const res = await fetch("/api/projects/quick", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  }).then((r) => r.json());
  await addToProject(res.project_id);
}

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 1800);
}

// Close modal when clicking the dark backdrop.
document.addEventListener("click", (e) => {
  if (e.target.id === "modal") closeModal();
});
