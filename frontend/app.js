const API_BASE = "/api";

let sessionId = "session_" + Math.random().toString(36).slice(2);
let generatedImages = [];
let currentImage = null;
let talentCandidate = null;
let talentEvaluation = null;
let talentPlacement = null;
let providerState = { active: "", last_used: "", last_fallbacks: [], providers: {} };
let fallbackChain = [];
const PROMPT_VAULT_KEY_BASE = "unified_studio_prompt_vault";
const PROJECT_STATE_KEY_BASE = "unified_studio_project_state";
let currentUserId = "";
function userStorageKey(base) { return currentUserId ? `${base}_${currentUserId}` : base; }

let authMode = "login";

document.addEventListener("DOMContentLoaded", async () => {
    await initAuthentication();
});

async function initAuthentication() {
    const form = byId("authForm");
    const toggle = byId("authToggle");
    if (toggle) toggle.addEventListener("click", toggleAuthMode);
    if (form) form.addEventListener("submit", submitAuth);
    const logout = byId("logoutBtn");
    if (logout) logout.addEventListener("click", logoutUser);
    try {
        const status = await fetchJson("/auth/status");
        if (status.authenticated) {
            enterStudio(status.user);
            return;
        }
        showAuthScreen(status);
    } catch (error) {
        showAuthMessage("Unable to reach the Unified Studio server: " + error.message, "error");
        showAuthScreen({registration_enabled: true});
    }
}

function showAuthScreen(status) {
    document.documentElement.classList.remove("auth-loading");
    byId("authScreen").classList.remove("hidden");
    byId("appShell")?.classList.add("auth-hidden");
    if (status && status.registration_enabled === false) byId("authToggle").classList.add("hidden");
}

function toggleAuthMode() {
    authMode = authMode === "login" ? "register" : "login";
    const register = authMode === "register";
    byId("authTitle").textContent = register ? "Create account" : "Sign in";
    byId("authSubtitle").textContent = register ? "Create a private Unified Studio workspace." : "Access your private workspace.";
    byId("displayNameWrap").classList.toggle("hidden", !register);
    byId("authPassword").autocomplete = register ? "new-password" : "current-password";
    byId("authSubmit").textContent = register ? "Create account" : "Sign in";
    byId("authToggle").textContent = register ? "Back to sign in" : "Create an account";
    showAuthMessage("");
}

async function submitAuth(event) {
    event.preventDefault();
    const register = authMode === "register";
    const payload = {
        username: byId("authUsername").value.trim(),
        password: byId("authPassword").value,
    };
    if (register) payload.display_name = byId("authDisplayName").value.trim();
    const button = byId("authSubmit");
    button.disabled = true;
    showAuthMessage(register ? "Creating account..." : "Signing in...", "info");
    try {
        const data = await fetchJson(register ? "/auth/register" : "/auth/login", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
        });
        enterStudio(data.user);
    } catch (error) {
        showAuthMessage(error.message, "error");
    } finally {
        button.disabled = false;
    }
}

function showAuthMessage(message, type = "info") {
    const box = byId("authMessage");
    if (!box) return;
    box.textContent = message || "";
    box.className = "auth-message";
    if (message) box.classList.add(type);
}

function enterStudio(user) {
    byId("authScreen")?.classList.add("hidden");
    byId("appShell")?.classList.remove("auth-hidden");
    document.documentElement.classList.remove("auth-loading");
    currentUserId = user?.id || user?.username || "";
    if (byId("currentUser")) byId("currentUser").textContent = "Signed in: " + (user?.display_name || user?.username || "user");
    byId("sessionId").textContent = sessionId;
    setupTabs();
    setupMobileNavigation();
    setupEvents();
    loadStudioData();
}

let studioInitialized = false;
async function loadStudioData() {
    if (studioInitialized) return;
    studioInitialized = true;
    await loadConfigWithRetry();
    loadProjectState();
    await loadProviderHealth();
    renderPromptVault();
    updateDashboardStats();
    await loadTalentJobs();
    updateServerStatus();
    setInterval(updateServerStatus, 10000);
}

async function logoutUser() {
    try { await fetchJson("/auth/logout", {method: "POST"}); } catch {}
    window.location.reload();
}

function byId(id) {
    return document.getElementById(id);
}

function log(id, value) {
    byId(id).textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

let toastTimer = null;

function showToast(message, type = "info", duration = 2800) {
    const toast = byId("appToast");
    if (!toast) return;

    clearTimeout(toastTimer);
    toast.textContent = String(message ?? "");
    toast.className = "app-toast";
    if (["success", "error", "info"].includes(type)) toast.classList.add(type);
    toast.classList.add("show");

    if (duration > 0) {
        toastTimer = setTimeout(() => {
            toast.classList.remove("show");
        }, duration);
    }
}

function setupTabs() {
    document.querySelectorAll(".nav-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            openTab(btn.dataset.tab);
        });
    });
}

function setupMobileNavigation() {
    const toggle = byId("mobileMenuToggle");
    const overlay = byId("mobileNavOverlay");
    const sidebar = byId("appSidebar");
    if (!toggle || !overlay || !sidebar) return;

    const setOpen = (open) => {
        sidebar.classList.toggle("mobile-open", open);
        overlay.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
        document.body.classList.toggle("mobile-nav-open", open);
    };

    toggle.addEventListener("click", () => setOpen(!sidebar.classList.contains("mobile-open")));
    overlay.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") setOpen(false);
    });

    document.querySelectorAll(".nav-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            if (window.matchMedia("(max-width: 780px)").matches) setOpen(false);
        });
    });

    window.addEventListener("resize", () => {
        if (!window.matchMedia("(max-width: 780px)").matches) setOpen(false);
    });
}

function openTab(tabName) {
    document.querySelectorAll(".nav-btn").forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tabName));
    document.querySelectorAll(".tab-content").forEach((tab) => tab.classList.toggle("active", tab.id === `${tabName}-tab`));
    const workspace = document.querySelector(".workspace");
    if (workspace) workspace.scrollTop = 0;
}

function setupEvents() {
    byId("chatSend").addEventListener("click", sendMessage);
    byId("chatInput").addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    byId("clearChat").addEventListener("click", clearChat);
    byId("exportChat").addEventListener("click", exportChat);
    byId("loadHistory").addEventListener("click", loadHistory);

    byId("promptImport").addEventListener("change", importPrompts);
    byId("applyStyle").addEventListener("click", () => transformPrompts({ style: byId("stylePreset").value }));
    byId("applyCharacter").addEventListener("click", () => transformPrompts({ character: collectControls("characterControls") }));
    byId("applyClothes").addEventListener("click", () => transformPrompts({ clothes: collectControls("clothesControls") }));
    byId("generateComic").addEventListener("click", generateComic);
    byId("exportComic").addEventListener("click", exportComic);
    byId("clearComic").addEventListener("click", () => {
        generatedImages = [];
        byId("comicResult").innerHTML = "";
        log("comicLog", "");
    });

    byId("generateImage").addEventListener("click", generateImage);
    byId("applyFilter").addEventListener("click", applyFilter);
    setupImageEditorEvents();

    byId("executeCode").addEventListener("click", executeCode);
    byId("searchBtn").addEventListener("click", webSearch);
    byId("searchInput").addEventListener("keydown", (e) => {
        if (e.key === "Enter") webSearch();
    });
    byId("processFile").addEventListener("click", processFile);
    byId("saveMemory").addEventListener("click", saveMemory);
    byId("refreshMemories").addEventListener("click", refreshMemories);
    byId("refreshSessions").addEventListener("click", refreshSessions);
    byId("createAutomation").addEventListener("click", createAutomation);
    byId("createWorkflow").addEventListener("click", createWorkflow);
    byId("refreshAutomations").addEventListener("click", refreshAutomations);
    byId("refreshWorkflows").addEventListener("click", refreshWorkflows);
    byId("refreshProviders").addEventListener("click", loadProviderHealth);
    byId("switchProvider").addEventListener("click", switchActiveProvider);
    byId("autoSelectProvider").addEventListener("click", autoSelectProvider);
    byId("addFallbackProvider").addEventListener("click", addFallbackProvider);
    byId("saveFallbackChain").addEventListener("click", saveFallbackChain);
    byId("fallbackChain").addEventListener("click", handleFallbackAction);

    document.querySelectorAll("[data-open-tab]").forEach((button) => {
        button.addEventListener("click", () => openTab(button.dataset.openTab));
    });
    byId("dashboardNewPrompt").addEventListener("click", () => {
        openTab("prompts");
        byId("promptName").focus();
    });
    byId("savePrompt").addEventListener("click", savePromptToVault);
    byId("promptSearch").addEventListener("input", renderPromptVault);
    byId("exportPrompts").addEventListener("click", exportPromptVault);
    byId("importPromptsFile").addEventListener("change", importPromptVault);
    byId("uploadTalentCv").addEventListener("click", uploadTalentCv);
    byId("startTalentPlacement").addEventListener("click", startTalentPlacement);
    byId("generateTalentAd").addEventListener("click", generateTalentAd);

    ["comicPrompts", "comicNegative", "comicEngine", "comicModel", "comicWidth", "comicHeight", "comicSteps", "comicCfg", "imagePrompt", "imageEngine", "imageWidth", "imageHeight"]
        .forEach((id) => byId(id).addEventListener("input", persistProjectState));
    ["comicEngine", "comicModel", "comicWidth", "comicHeight", "comicSteps", "comicCfg", "imageEngine", "imageWidth", "imageHeight"]
        .forEach((id) => byId(id).addEventListener("change", persistProjectState));
}

async function loadTalentJobs() {
    try {
        const data = await fetchJson("/talent/jobs");
        const select = byId("talentJobSelect");
        select.innerHTML = (data.jobs || []).map((job) => `<option value="${escapeHtml(job.id)}">${escapeHtml(job.title)}</option>`).join("");
    } catch (error) {
        byId("talentCvStatus").textContent = `Could not load jobs: ${error.message}`;
    }
}

async function uploadTalentCv() {
    const file = byId("talentCvFile").files[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    byId("talentCvStatus").textContent = "Analyzing candidate CV...";
    try {
        const uploaded = await fetchJson("/talent/candidates", { method: "POST", body });
        talentCandidate = uploaded.candidate;
        talentEvaluation = await fetchJson("/talent/evaluate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ candidate_id: talentCandidate.id, job_id: byId("talentJobSelect").value }),
        });
        renderTalentEvaluation();
        byId("talentCvStatus").textContent = `${file.name} analyzed successfully.`;
    } catch (error) {
        byId("talentCvStatus").textContent = `Analysis failed: ${error.message}`;
    }
}

function renderTalentEvaluation() {
    const selected = talentEvaluation.selected;
    const retention = talentEvaluation.retention;
    const alternatives = talentEvaluation.alternatives || [];
    byId("talentAssessment").className = "talent-result";
    byId("talentAssessment").innerHTML = `
        <div class="talent-score-row"><div><span class="dashboard-label">Candidate suitability</span><strong>${selected.suitability_score}%</strong></div><div><span class="dashboard-label">Estimated retention potential</span><strong>${retention.retention_score}%</strong></div></div>
        <p>${escapeHtml(selected.explanation)}</p>
        <div class="assessment-columns"><div><h4>Strong matches</h4><ul>${selected.matched_requirements.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>None identified</li>"}</ul></div><div><h4>Missing or unverified</h4><ul>${selected.missing_requirements.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>None identified</li>"}</ul></div></div>
        <h4>Retention factors</h4><p>${escapeHtml([...retention.factors_for, ...retention.factors_against].join(". ") || "More evidence is needed.")}</p><small>${escapeHtml(retention.disclaimer)}</small>
        <h4>Alternative jobs</h4><div class="alternative-list">${alternatives.map((item) => `<button class="alternative-card" data-talent-job="${escapeHtml(item.job_id)}"><strong>${escapeHtml(item.job_title)} · ${item.suitability_score}%</strong><span>${escapeHtml(item.explanation)}</span></button>`).join("") || "<span>No alternatives available.</span>"}</div>`;
    byId("startTalentPlacement").disabled = false;
    byId("talentPlacementStatus").textContent = `Ready to track placement for ${talentEvaluation.selected.job_title}.`;
    byId("talentAssessment").querySelectorAll("[data-talent-job]").forEach((button) => button.addEventListener("click", async () => {
        talentEvaluation = await fetchJson("/talent/evaluate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ candidate_id: talentCandidate.id, job_id: button.dataset.talentJob }) });
        byId("talentJobSelect").value = button.dataset.talentJob;
        renderTalentEvaluation();
    }));
}

async function startTalentPlacement() {
    if (!talentCandidate || !talentEvaluation) return;
    talentPlacement = (await fetchJson("/talent/placements", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ candidate_id: talentCandidate.id, job_id: talentEvaluation.selected.job_id }) })).placement;
    renderTalentMilestones();
}

function renderTalentMilestones() {
    const labels = { day_1: "Day 1", week_1: "Week 1", month_1: "Month 1", month_2: "Month 2", month_3: "Month 3" };
    byId("talentMilestones").innerHTML = Object.entries(talentPlacement.milestones).map(([key, item]) => `<div class="milestone-item"><label>${labels[key]}<select data-milestone-status="${key}"><option ${item.status === "pending" ? "selected" : ""}>pending</option><option ${item.status === "active" ? "selected" : ""}>active</option><option ${item.status === "completed" ? "selected" : ""}>completed</option><option ${item.status === "at_risk" ? "selected" : ""}>at_risk</option></select></label><input data-milestone-notes="${key}" value="${escapeHtml(item.notes || "")}" placeholder="Feedback or status notes"></div>`).join("") + `<button id="saveTalentMilestones" class="btn-secondary">Save Milestones</button><pre id="talentPlacementReport" class="log-box"></pre>`;
    byId("saveTalentMilestones").addEventListener("click", saveTalentMilestones);
}

async function saveTalentMilestones() {
    for (const [key, item] of Object.entries(talentPlacement.milestones)) {
        const status = document.querySelector(`[data-milestone-status="${key}"]`).value;
        const notes = document.querySelector(`[data-milestone-notes="${key}"]`).value;
        talentPlacement = (await fetchJson(`/talent/placements/${talentPlacement.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ milestone: key, status, notes }) })).placement;
    }
    const report = await fetchJson(`/talent/placements/${talentPlacement.id}/report`);
    log("talentPlacementReport", report.report);
    byId("talentPlacementStatus").textContent = `Placement status: ${report.report.status} · success score ${report.report.placement_success_score}%`;
}

async function generateTalentAd() {
    const offer = byId("talentOffer").value.trim();
    if (!offer) return;
    const data = await fetchJson("/talent/advertisements", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ offer, preferences: { title: byId("talentAdTitle").value, target_profile: byId("talentAdTarget").value, tone: byId("talentAdTone").value, platform: byId("talentAdPlatform").value, language: byId("talentAdLanguage").value } }) });
    byId("talentAdOutput").value = data.advertisement || "";
}

async function loadConfigWithRetry(attempts = 5, delayMs = 1000) {
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
        try {
            await loadConfig();
            return true;
        } catch (error) {
            if (attempt === attempts) {
                showToast("Server configuration unavailable; retry with Refresh", "error", 4500);
                return false;
            }
            await new Promise((resolve) => setTimeout(resolve, delayMs * attempt));
        }
    }
    return false;
}

async function loadConfig() {
    const config = await fetchJson("/config");

    fillSelect("comicModel", config.horde_models || []);
    fillSelect("stylePreset", config.style_presets || []);

    const agentSelect = byId("globalAgent");
    (config.agents || []).forEach((name) => {
        if (name === "triage") return;
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        agentSelect.appendChild(option);
    });

    buildOptionControls("characterControls", config.character_options || {});
    buildOptionControls("clothesControls", config.clothes_options || {});
    renderProviderOptions(config.providers || {}, config.active_provider || "ollama", config.fallbacks || []);
}

function renderProviderOptions(providers, active, chain) {
    const activeSelect = byId("activeProviderSelect");
    const fallbackSelect = byId("fallbackProviderSelect");
    if (!activeSelect || !fallbackSelect) return;
    const entries = Object.entries(providers);
    activeSelect.innerHTML = entries.map(([id, cfg]) => `<option value="${escapeHtml(id)}">${escapeHtml(cfg.name)}${cfg.configured ? "" : " (not configured)"}</option>`).join("");
    activeSelect.value = active;
    fallbackSelect.innerHTML = entries.map(([id, cfg]) => `<option value="${escapeHtml(id)}">${escapeHtml(cfg.name)}</option>`).join("");
    fallbackChain = Array.isArray(chain) ? [...chain] : [];
    renderFallbackChain();
}

async function loadProviderHealth() {
    try {
        const data = await fetchJson("/providers/health");
        providerState = data;
        renderProviderHealth();
        renderProviderOptions(Object.fromEntries(Object.entries(data.providers || {}).map(([id, item]) => [id, { name: item.name, configured: item.configured }])), data.active || "", fallbackChain);
        const fallbackData = await fetchJson("/providers/fallback");
        fallbackChain = Array.isArray(fallbackData.chain) ? fallbackData.chain : [];
        renderFallbackChain();
    } catch (error) {
        byId("providerHealth").innerHTML = `<div class="empty-state"><strong>Provider health unavailable</strong><span>${escapeHtml(error.message)}</span></div>`;
    }
}

function renderProviderHealth() {
    const container = byId("providerHealth");
    const providers = providerState.providers || {};
    container.innerHTML = Object.entries(providers).map(([id, item]) => `
        <article class="provider-card ${item.healthy ? "healthy" : "unhealthy"}">
            <div class="provider-card-head"><div><h3>${escapeHtml(item.name)}</h3><span>${escapeHtml(id)} · ${escapeHtml(item.model || "")}</span></div><strong>${item.healthy ? "ONLINE" : (item.configured ? "OFFLINE" : "UNCONFIGURED")}</strong></div>
            <div class="provider-meta"><span>${Number(item.latency_ms || 0)} ms</span><span>${item.configured ? "Configured" : "Key required"}</span></div>
            ${item.error ? `<p class="provider-error">${escapeHtml(item.error)}</p>` : ""}
            <button class="btn-secondary provider-test-button" data-provider-test="${escapeHtml(id)}">Test Completion</button>
        </article>`).join("");
    container.querySelectorAll("[data-provider-test]").forEach((button) => {
        button.addEventListener("click", () => testSingleProvider(button.dataset.providerTest, button));
    });
}

async function testSingleProvider(provider, button) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Testing...";
    try {
        const result = await fetchJson("/providers/test", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ provider }) });
        showToast(result.success ? `${provider} test passed (${result.latency_ms} ms)` : `${provider} test failed: ${result.error}`, result.success ? "success" : "error");
    } finally {
        button.disabled = false;
        button.textContent = original;
    }
}

async function switchActiveProvider() {
    const provider = byId("activeProviderSelect").value;
    try {
        const data = await fetchJson("/providers/switch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ provider }) });
        providerState.active = data.active_provider;
        showToast(`Active provider: ${data.active_provider}`, "success");
        await loadProviderHealth();
    } catch (error) {
        showToast(error.message, "error");
    }
}

function addFallbackProvider() {
    const provider = byId("fallbackProviderSelect").value;
    if (!provider || provider === providerState.active || fallbackChain.includes(provider)) return;
    fallbackChain.push(provider);
    renderFallbackChain();
}

function renderFallbackChain() {
    const container = byId("fallbackChain");
    if (!fallbackChain.length) {
        container.innerHTML = `<div class="fallback-empty">No fallbacks configured.</div>`;
        return;
    }
    container.innerHTML = fallbackChain.map((provider, index) => `<div class="fallback-item"><span>${index + 1}. ${escapeHtml(provider)}</span><div><button class="icon-action" data-fallback-up="${index}" ${index === 0 ? "disabled" : ""}>↑</button><button class="icon-action" data-fallback-down="${index}" ${index === fallbackChain.length - 1 ? "disabled" : ""}>↓</button><button class="icon-action" data-fallback-remove="${index}">Remove</button></div></div>`).join("");
}

function handleFallbackAction(event) {
    const button = event.target.closest("button");
    if (!button) return;
    const up = button.dataset.fallbackUp;
    const down = button.dataset.fallbackDown;
    const remove = button.dataset.fallbackRemove;
    if (up !== undefined && Number(up) > 0) [fallbackChain[up - 1], fallbackChain[up]] = [fallbackChain[up], fallbackChain[up - 1]];
    if (down !== undefined && Number(down) < fallbackChain.length - 1) [fallbackChain[down], fallbackChain[Number(down) + 1]] = [fallbackChain[Number(down) + 1], fallbackChain[down]];
    if (remove !== undefined) fallbackChain.splice(Number(remove), 1);
    renderFallbackChain();
}

async function saveFallbackChain() {
    try {
        await fetchJson("/providers/fallback", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ chain: fallbackChain }) });
        showToast("Fallback chain saved", "success");
        await loadProviderHealth();
    } catch (error) {
        showToast(error.message, "error");
    }
}

async function autoSelectProvider() {
    const healthy = Object.entries(providerState.providers || {}).filter(([id, item]) => item.healthy);
    if (!healthy.length) { showToast("No healthy configured provider", "error"); return; }
    healthy.sort((a, b) => Number(a[1].latency_ms || Infinity) - Number(b[1].latency_ms || Infinity));
    byId("activeProviderSelect").value = healthy[0][0];
    await switchActiveProvider();
}

function getPromptVault() {
    try {
        const saved = JSON.parse(localStorage.getItem(userStorageKey(PROMPT_VAULT_KEY_BASE)) || "[]");
        return Array.isArray(saved) ? saved : [];
    } catch {
        return [];
    }
}

function savePromptVault(prompts) {
    localStorage.setItem(userStorageKey(PROMPT_VAULT_KEY_BASE), JSON.stringify(prompts));
    updateDashboardStats();
}

function savePromptToVault() {
    const content = byId("promptVaultText").value.trim();
    const title = byId("promptName").value.trim() || `Prompt ${getPromptVault().length + 1}`;
    if (!content) return;

    const prompts = getPromptVault();
    prompts.unshift({
        id: `prompt_${Date.now()}`,
        title,
        category: byId("promptCategory").value,
        tags: byId("promptTags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
        content,
        updatedAt: new Date().toISOString(),
    });
    savePromptVault(prompts);
    byId("promptName").value = "";
    byId("promptTags").value = "";
    byId("promptVaultText").value = "";
    renderPromptVault();
}

function renderPromptVault() {
    const container = byId("promptVaultList");
    if (!container) return;
    const query = (byId("promptSearch")?.value || "").trim().toLowerCase();
    const prompts = getPromptVault().filter((prompt) => [prompt.title, prompt.category, prompt.content, ...(prompt.tags || [])].join(" ").toLowerCase().includes(query));

    if (!prompts.length) {
        container.innerHTML = `<div class="empty-state"><strong>No prompts saved yet</strong><span>Save a reusable prompt here and it will stay available in this browser.</span></div>`;
        return;
    }

    container.innerHTML = prompts.map((prompt) => `
        <article class="prompt-card">
            <div class="prompt-card-header"><div><h4>${escapeHtml(prompt.title)}</h4><span>${escapeHtml(prompt.category)}</span></div><button class="icon-action" data-delete-prompt="${escapeHtml(prompt.id)}" title="Delete prompt">Delete</button></div>
            <p>${escapeHtml(prompt.content)}</p>
            <div class="prompt-card-footer"><small>${escapeHtml((prompt.tags || []).join(" · "))}</small><button class="btn-secondary use-prompt" data-use-prompt="${escapeHtml(prompt.id)}">Use in Comic Forge</button></div>
        </article>
    `).join("");

    container.querySelectorAll("[data-delete-prompt]").forEach((button) => button.addEventListener("click", () => {
        savePromptVault(getPromptVault().filter((prompt) => prompt.id !== button.dataset.deletePrompt));
        renderPromptVault();
    }));
    container.querySelectorAll("[data-use-prompt]").forEach((button) => button.addEventListener("click", () => {
        const prompt = getPromptVault().find((item) => item.id === button.dataset.usePrompt);
        if (!prompt) return;
        byId("comicPrompts").value = prompt.content;
        persistProjectState();
        openTab("comic");
    }));
}

function exportPromptVault() {
    downloadText("unified-studio-prompts.json", JSON.stringify({ version: 1, prompts: getPromptVault() }, null, 2));
}

async function importPromptVault() {
    const file = byId("importPromptsFile").files[0];
    if (!file) return;
    try {
        const parsed = JSON.parse(await file.text());
        const imported = Array.isArray(parsed) ? parsed : parsed.prompts;
        if (!Array.isArray(imported)) throw new Error("Invalid prompt vault");
        const existing = getPromptVault();
        const merged = [...imported, ...existing].filter((prompt, index, all) => prompt && prompt.content && all.findIndex((item) => item.id === prompt.id) === index);
        savePromptVault(merged);
        renderPromptVault();
    } catch (error) {
        window.alert(`Could not import prompt vault: ${error.message}`);
    }
    byId("importPromptsFile").value = "";
}

function persistProjectState() {
    const state = {};
    ["comicPrompts", "comicNegative", "comicEngine", "comicModel", "comicWidth", "comicHeight", "comicSteps", "comicCfg", "imagePrompt", "imageEngine", "imageWidth", "imageHeight"].forEach((id) => {
        const element = byId(id);
        if (element) state[id] = element.value;
    });
    localStorage.setItem(userStorageKey(PROJECT_STATE_KEY_BASE), JSON.stringify(state));
}

function loadProjectState() {
    try {
        const state = JSON.parse(localStorage.getItem(userStorageKey(PROJECT_STATE_KEY_BASE)) || "{}");
        Object.entries(state).forEach(([id, value]) => {
            const element = byId(id);
            if (element && value !== undefined) element.value = value;
        });
    } catch {
        localStorage.removeItem(userStorageKey(PROJECT_STATE_KEY_BASE));
    }
}

async function updateDashboardStats() {
    const promptCount = getPromptVault().length;
    byId("dashboardPromptCount").textContent = promptCount;
    byId("dashboardPanelCount").textContent = generatedImages.length;
    try {
        const data = await fetchJson(`/images/${encodeURIComponent(sessionId)}`);
        byId("dashboardImageCount").textContent = (data.images || []).length;
    } catch {
        byId("dashboardImageCount").textContent = "0";
    }
}

function fillSelect(id, values) {
    byId(id).innerHTML = values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
}

function buildOptionControls(containerId, options) {
    const container = byId(containerId);
    container.innerHTML = "";
    Object.entries(options).forEach(([label, values]) => {
        const wrapper = document.createElement("label");
        wrapper.textContent = label;
        const select = document.createElement("select");
        select.dataset.key = label;
        values.forEach((value) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = value;
            select.appendChild(option);
        });
        wrapper.appendChild(select);
        container.appendChild(wrapper);
    });
}

function collectControls(containerId) {
    const result = {};
    byId(containerId).querySelectorAll("select").forEach((select) => {
        result[select.dataset.key] = select.value;
    });
    return result;
}

async function updateServerStatus() {
    try {
        await fetchJson("/status");
        byId("serverStatus").textContent = "Server online";
        byId("serverStatus").className = "ok";
    } catch {
        byId("serverStatus").textContent = "Server offline";
        byId("serverStatus").className = "bad";
    }
}

async function fetchJson(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, { credentials: "same-origin", ...options });
    const text = await response.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { error: text || response.statusText }; }
    if (!response.ok) throw new Error(data.detail || data.error || response.statusText);
    return data;
}

async function sendMessage() {
    const input = byId("chatInput");
    const message = input.value.trim();
    if (!message) return;

    addChatMessage(message, "user");
    input.value = "";

    try {
        const agent = byId("globalAgent").value || null;
        const data = await fetchJson("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, session_id: sessionId, agent }),
        });
        addChatMessage(data.response || "(no response)", "assistant", data.agent_emoji || "");
    } catch (error) {
        addChatMessage(`Connection error: ${error.message}`, "assistant");
    }
}

function addChatMessage(content, role, marker = "") {
    const row = document.createElement("div");
    row.className = `message ${role}`;
    row.textContent = marker ? `${marker} ${content}` : content;
    byId("chatDisplay").appendChild(row);
    byId("chatDisplay").scrollTop = byId("chatDisplay").scrollHeight;
}

function clearChat() {
    byId("chatDisplay").innerHTML = "";
    sessionId = "session_" + Math.random().toString(36).slice(2);
    byId("sessionId").textContent = sessionId;
}

function exportChat() {
    const text = Array.from(byId("chatDisplay").children).map((node) => node.textContent).join("\n\n");
    downloadText(`chat_${sessionId}.txt`, text);
}

async function loadHistory() {
    const data = await fetchJson(`/history/${encodeURIComponent(sessionId)}`);
    byId("chatDisplay").innerHTML = "";
    (data.messages || []).forEach((msg) => addChatMessage(msg.content, msg.role));
}

async function importPrompts() {
    const file = byId("promptImport").files[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    const data = await fetchJson("/import-prompts", { method: "POST", body });
    if (data.text) byId("comicPrompts").value = data.text;
    log("comicLog", data);
}

async function transformPrompts(extra) {
    const data = await fetchJson("/prompts/transform", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompts: byId("comicPrompts").value, ...extra }),
    });
    byId("comicPrompts").value = data.prompts;
}

async function generateComic() {
    const prompts = byId("comicPrompts").value.split("\n").map((line) => line.trim()).filter(Boolean);
    if (!prompts.length) return;

    log("comicLog", "Generating panels...");
    const data = await fetchJson("/generate-comic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            prompts,
            engine: byId("comicEngine").value,
            model: byId("comicModel").value,
            width: Number(byId("comicWidth").value),
            height: Number(byId("comicHeight").value),
            steps: Number(byId("comicSteps").value),
            cfg_scale: Number(byId("comicCfg").value),
            negative_prompt: byId("comicNegative").value,
            nsfw: byId("comicNsfw").checked,
            session_id: sessionId,
        }),
    });
    (data.images || []).forEach((item) => {
        generatedImages.push(item);
        addGalleryCard("comicResult", item);
    });
    log("comicLog", data);
}

async function exportComic() {
    const data = await fetchJson("/export-comic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ images: generatedImages }),
    });
    log("comicLog", data);
    if (data.url) window.open(data.url, "_blank");
}

async function generateImage() {
    const prompt = byId("imagePrompt").value.trim();
    if (!prompt) return;
    byId("imageResult").textContent = "Generating...";
    const data = await fetchJson("/generate-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            prompt,
            engine: byId("imageEngine").value,
            width: Number(byId("imageWidth").value),
            height: Number(byId("imageHeight").value),
            nsfw: byId("imageNSFW").checked,
            session_id: sessionId,
        }),
    });
    if (!data.success) {
        byId("imageResult").textContent = data.error || "Image generation failed";
        return;
    }
    currentImage = { filename: data.filename, url: data.url, prompt };
    renderImageResult(data.url);
    addGalleryCard("imageGallery", currentImage);
    initializeImageEditor(data.url);
}

function isSafeMediaUrl(value) {
    try {
        const parsed = new URL(value, window.location.origin);
        return (parsed.origin === window.location.origin && parsed.pathname.startsWith("/outputs/"));
    } catch {
        return false;
    }
}

function renderImageResult(url) {
    const container = byId("imageResult");
    if (!container || !isSafeMediaUrl(url)) {
        if (container) container.textContent = "Invalid image URL";
        return;
    }
    container.replaceChildren();
    const img = document.createElement("img");
    img.className = "main-image";
    img.alt = "";
    img.src = url;
    container.appendChild(img);
}

async function applyFilter() {
    if (!currentImage) return;
    const data = await fetchJson("/edit-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            filename: currentImage.filename,
            filter: byId("filterName").value,
            brightness: Number(byId("brightness").value),
            contrast: Number(byId("contrast").value),
            saturation: Number(byId("saturation").value),
            caption: byId("captionText").value,
            caption_position: byId("captionPosition").value,
            session_id: sessionId,
        }),
    });
    if (data.success) {
        currentImage = { ...currentImage, filename: data.filename, url: data.url };
        renderImageResult(data.url);
        initializeImageEditor(data.url);
        addGalleryCard("imageGallery", currentImage);
    }
}

let editorState = { canvas: null, ctx: null, img: null, drawing: false, tool: "brush", size: 5, color: "#ff2f7a" };

function initializeImageEditor(url) {
    byId("imageEditor").classList.remove("hidden");
    const canvas = byId("editCanvas");
    const ctx = canvas.getContext("2d");
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
        editorState = { ...editorState, canvas, ctx, img };
    };
    img.src = url;
}

function setupImageEditorEvents() {
    byId("brushTool").addEventListener("click", () => setTool("brush"));
    byId("eraserTool").addEventListener("click", () => setTool("eraser"));
    byId("brushSize").addEventListener("input", (e) => editorState.size = Number(e.target.value));
    byId("brushColor").addEventListener("input", (e) => editorState.color = e.target.value);
    byId("clearCanvas").addEventListener("click", () => {
        if (editorState.img) {
            editorState.ctx.globalCompositeOperation = "source-over";
            editorState.ctx.clearRect(0, 0, editorState.canvas.width, editorState.canvas.height);
            editorState.ctx.drawImage(editorState.img, 0, 0);
        }
    });
    byId("saveEdited").addEventListener("click", saveEditedDrawing);
    byId("downloadImage").addEventListener("click", () => {
        if (!editorState.canvas) return;
        const link = document.createElement("a");
        link.href = editorState.canvas.toDataURL("image/png");
        link.download = `edited_${Date.now()}.png`;
        link.click();
    });
    const canvas = byId("editCanvas");
    canvas.addEventListener("mousedown", startDraw);
    canvas.addEventListener("mousemove", draw);
    window.addEventListener("mouseup", () => editorState.drawing = false);
}

function setTool(tool) {
    editorState.tool = tool;
    byId("brushTool").classList.toggle("active", tool === "brush");
    byId("eraserTool").classList.toggle("active", tool === "eraser");
}

function startDraw(e) {
    if (!editorState.ctx) return;
    editorState.drawing = true;
    editorState.ctx.beginPath();
    const { x, y } = canvasPoint(e);
    editorState.ctx.moveTo(x, y);
}

function draw(e) {
    if (!editorState.drawing || !editorState.ctx) return;
    const { x, y } = canvasPoint(e);
    editorState.ctx.lineWidth = editorState.size;
    editorState.ctx.lineCap = "round";
    if (editorState.tool === "eraser") {
        editorState.ctx.globalCompositeOperation = "destination-out";
    } else {
        editorState.ctx.globalCompositeOperation = "source-over";
        editorState.ctx.strokeStyle = editorState.color;
    }
    editorState.ctx.lineTo(x, y);
    editorState.ctx.stroke();
}

function canvasPoint(e) {
    const rect = editorState.canvas.getBoundingClientRect();
    return {
        x: (e.clientX - rect.left) * (editorState.canvas.width / rect.width),
        y: (e.clientY - rect.top) * (editorState.canvas.height / rect.height),
    };
}

async function saveEditedDrawing() {
    if (!editorState.canvas) return;
    const data = await fetchJson("/save-edited-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_data: editorState.canvas.toDataURL("image/png"), session_id: sessionId }),
    });
    if (data.success) {
        currentImage = { filename: data.filename, url: data.url, prompt: "edited image" };
        addGalleryCard("imageGallery", currentImage);
    }
}

async function executeCode() {
    const data = await fetchJson("/execute-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: byId("codeInput").value, language: "python" }),
    });
    log("codeOutput", data.success ? (data.stdout || "(no output)") : data.stderr);
}

async function webSearch() {
    const q = byId("searchInput").value.trim();
    if (!q) return;
    const data = await fetchJson(`/search?q=${encodeURIComponent(q)}`);
    log("searchResults", data.results || data.error || data);
}

async function processFile() {
    const file = byId("fileInput").files[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    body.append("operation", byId("fileOperation").value);
    const data = await fetchJson("/process-file", { method: "POST", body });
    log("fileOutput", data);
}

async function saveMemory() {
    const data = await fetchJson("/memories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: byId("memoryKey").value, value: byId("memoryValue").value }),
    });
    log("memoryOutput", data);
}

async function refreshMemories() {
    log("memoryOutput", await fetchJson("/memories"));
}

async function refreshSessions() {
    log("memoryOutput", await fetchJson("/sessions"));
}

async function createAutomation() {
    const data = await fetchJson("/automations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            name: byId("automationName").value,
            trigger_type: byId("automationTrigger").value,
            schedule: byId("automationSchedule").value,
            action: byId("automationAction").value,
        }),
    });
    log("automationOutput", data);
}

async function createWorkflow() {
    const steps = byId("workflowSteps").value.split("\n").map((name) => ({ name: name.trim() })).filter((s) => s.name);
    const data = await fetchJson("/workflows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: byId("workflowName").value, steps }),
    });
    log("automationOutput", data);
}

async function refreshAutomations() {
    log("automationOutput", await fetchJson("/automations"));
}

async function refreshWorkflows() {
    log("automationOutput", await fetchJson("/workflows"));
}

function addGalleryCard(containerId, item) {
    const container = byId(containerId);
    if (!container || !isSafeMediaUrl(item.url)) return;
    const card = document.createElement("article");
    card.className = "gallery-item";
    const img = document.createElement("img");
    img.alt = "";
    img.src = item.url;
    const text = document.createElement("p");
    text.textContent = item.prompt || item.filename || "";
    card.append(img, text);
    card.addEventListener("click", () => {
        currentImage = { filename: item.filename, url: item.url, prompt: item.prompt || "" };
        renderImageResult(item.url);
        initializeImageEditor(item.url);
    });
    container.prepend(card);
}

function downloadText(filename, text) {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    link.download = filename;
    link.click();
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"'`/]/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
        "`": "&#096;",
        "/": "&#047;",
    }[char]));
}
