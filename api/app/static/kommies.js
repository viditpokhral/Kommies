/*!
 * Kommies Comment Plugin v2.1.0
 * Usage:
 *   <div id="kommies-comments"></div>
 *   <script>
 *     window.kommies = {
 *       api_key: "cpk_...",
 *       page_url: window.location.href,
 *       identifier: "post-1"
 *     }
 *   </script>
 *   <script src="http://localhost:8000/static/kommies.js"></script>
 */
(function () {
  "use strict";

  const API = "http://localhost:8000/api/v1";
  const cfg = window.kommies || {};

  if (!cfg.api_key) {
    console.error("[Kommies] Missing api_key in window.kommies config");
    return;
  }

  const PAGE_URL = cfg.page_url || window.location.href;
  const IDENTIFIER = cfg.identifier
    || window.location.pathname.replace(/\//g, "-").replace(/^-|-$/g, "")
    || "home";

  let THREAD_ID = null;

  // ── AUTH STATE ────────────────────────────────────────────────────────────
  let _currentUser = null; // { id, email, display_name } or null

  function getToken() { return localStorage.getItem("kommies_token"); }
  function setToken(t) { localStorage.setItem("kommies_token", t); }
  function clearToken() { localStorage.removeItem("kommies_token"); _currentUser = null; }
  function isLoggedIn() { return !!getToken() && !!_currentUser; }

  async function loadCurrentUser() {
    const token = getToken();
    if (!token) return null;
    try {
      const res = await fetch(`${API}/commenters/me`, {
        headers: { "Authorization": `Bearer ${token}` },
      });
      if (!res.ok) { clearToken(); return null; }
      _currentUser = await res.json();
      return _currentUser;
    } catch { clearToken(); return null; }
  }

  // ── STYLES ────────────────────────────────────────────────────────────────
  const CSS = `
    #kommies {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px; color: #1c1c1c; max-width: 740px; margin: 0 auto;
    }
    #kommies * { box-sizing: border-box; }
    #kommies h3 { font-size: 17px; font-weight: 700; margin: 0 0 18px; color: #0f0f0f; }

    /* ── Auth bar ── */
    #kommies .k-auth-bar {
      background: #f6f7f8; border: 1px solid #edeff1;
      border-radius: 4px; padding: 12px 14px; margin-bottom: 10px;
    }
    #kommies .k-auth-tabs {
      display: flex; gap: 0; border-bottom: 1px solid #edeff1; margin-bottom: 12px;
    }
    #kommies .k-auth-tab {
      background: none; border: none; cursor: pointer;
      font-size: 13px; font-weight: 700; color: #878a8c;
      padding: 6px 14px 8px; border-bottom: 2px solid transparent;
      margin-bottom: -1px; transition: color .15s, border-color .15s;
    }
    #kommies .k-auth-tab.active { color: #ff4500; border-bottom-color: #ff4500; }
    #kommies .k-auth-panel { display: none; }
    #kommies .k-auth-panel.active { display: block; }
    #kommies .k-auth-bar input {
      width: 100%; border: 1px solid #edeff1; border-radius: 4px;
      padding: 9px 11px; font-size: 13px; margin-bottom: 8px;
      font-family: inherit; outline: none; background: #fff;
      transition: border .15s;
    }
    #kommies .k-auth-bar input:focus { border-color: #0079d3; }
    #kommies .k-auth-row { display: flex; gap: 8px; align-items: center; }
    #kommies .k-auth-error { color: #ea0027; font-size: 12px; }
    #kommies .k-auth-hint  { font-size: 12px; color: #878a8c; }

    /* ── Logged-in pill ── */
    #kommies .k-user-pill {
      display: flex; align-items: center; gap: 8px;
      font-size: 13px; color: #1c1c1c;
    }
    #kommies .k-user-pill .k-avatar { width: 22px; height: 22px; font-size: 10px; }
    #kommies .k-user-name { font-weight: 700; }
    #kommies .k-signout {
      background: none; border: none; cursor: pointer;
      font-size: 12px; color: #878a8c; padding: 2px 6px;
      border-radius: 3px; transition: background .15s;
    }
    #kommies .k-signout:hover { background: #edeff1; color: #ea0027; }

    /* ── Comment form ── */
    #kommies .k-form {
      background: #f6f7f8; border: 1px solid #edeff1;
      border-radius: 4px; padding: 14px; margin-bottom: 20px;
    }
    #kommies .k-form input,
    #kommies .k-form textarea {
      width: 100%; border: 1px solid #edeff1; border-radius: 4px;
      padding: 9px 11px; font-size: 14px; margin-bottom: 8px;
      font-family: inherit; outline: none; background: #fff;
      transition: border 0.15s;
    }
    #kommies .k-form input:focus,
    #kommies .k-form textarea:focus { border-color: #0079d3; }
    #kommies .k-form input[readonly] {
      background: #f0f0f0; color: #878a8c; cursor: default;
    }
    #kommies .k-form .k-row { display: flex; gap: 8px; }
    #kommies .k-form .k-row input { flex: 1; }
    #kommies .k-form textarea { height: 80px; resize: vertical; margin-bottom: 10px; }

    #kommies .k-btn {
      background: #ff4500; color: #fff; border: none;
      border-radius: 20px; padding: 6px 18px; font-size: 13px; font-weight: 700;
      cursor: pointer; transition: background 0.15s;
    }
    #kommies .k-btn:hover { background: #e03d00; }
    #kommies .k-btn:disabled { background: #ffb09e; cursor: not-allowed; }
    #kommies .k-btn-ghost {
      background: transparent; color: #878a8c; border: none;
      padding: 6px 8px; font-size: 12px; font-weight: 700;
      cursor: pointer; border-radius: 2px; transition: background 0.15s;
      display: inline-flex; align-items: center; gap: 4px;
    }
    #kommies .k-btn-ghost:hover { background: #e8e8e8; color: #1c1c1c; }
    #kommies .k-btn-sm {
      background: #ff4500; color: #fff; border: none;
      border-radius: 3px; padding: 5px 14px; font-size: 12px; font-weight: 700;
      cursor: pointer; transition: background .15s;
    }
    #kommies .k-btn-sm:hover { background: #e03d00; }
    #kommies .k-btn-sm:disabled { background: #ffb09e; cursor: not-allowed; }

    #kommies .k-thread { position: relative; margin-bottom: 2px; }
    #kommies .k-comment { display: flex; gap: 0; padding: 8px 0 4px; }

    #kommies .k-rail {
      display: flex; flex-direction: column; align-items: center;
      min-width: 32px; padding-top: 2px; gap: 2px;
    }
    #kommies .k-vote-btn {
      background: none; border: none; cursor: pointer;
      color: #878a8c; padding: 3px; border-radius: 2px;
      font-size: 16px; line-height: 1; transition: color 0.1s;
    }
    #kommies .k-vote-btn.up:hover { color: #ff4500; }
    #kommies .k-vote-btn.down:hover { color: #7193ff; }
    #kommies .k-vote-btn.active-up { color: #ff4500; }
    #kommies .k-vote-btn.active-down { color: #7193ff; }
    #kommies .k-score {
      font-size: 11px; font-weight: 700; color: #1c1c1c;
      min-width: 20px; text-align: center;
    }

    #kommies .k-thread-line-wrap { display: flex; }
    #kommies .k-thread-line {
      width: 2px; background: #edeff1; margin: 0 15px;
      cursor: pointer; flex-shrink: 0; border-radius: 2px;
      transition: background 0.15s; align-self: stretch; min-height: 20px;
    }
    #kommies .k-thread-line:hover { background: #0079d3; }

    #kommies .k-body { flex: 1; min-width: 0; }
    #kommies .k-meta {
      display: flex; align-items: center; gap: 6px;
      margin-bottom: 5px; flex-wrap: wrap;
    }
    #kommies .k-avatar {
      width: 24px; height: 24px; border-radius: 50%; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      color: #fff; font-size: 11px; font-weight: 700;
    }
    #kommies .k-author { font-weight: 700; font-size: 13px; color: #0079d3; }
    #kommies .k-time { font-size: 12px; color: #878a8c; }
    #kommies .k-text { line-height: 1.65; color: #1c1c1c; margin: 0 0 6px; word-break: break-word; }
    #kommies .k-actions { display: flex; align-items: center; gap: 2px; flex-wrap: wrap; margin-bottom: 4px; }
    #kommies .k-divider { border: none; border-top: 1px solid #edeff1; margin: 8px 0; }
    #kommies .k-empty { text-align: center; color: #878a8c; padding: 40px 0; font-size: 14px; }
    #kommies .k-error { color: #ea0027; font-size: 12px; }
    #kommies .k-pending {
      font-size: 11px; color: #cc8500; background: #fff3cd; border-radius: 3px; padding: 1px 6px;
    }
    #kommies .k-deleted { color: #878a8c; font-style: italic; }
    #kommies .k-flag-form {
      margin-top: 8px; background: #f6f7f8; border: 1px solid #edeff1;
      border-radius: 4px; padding: 10px;
    }
    #kommies .k-flag-form select {
      width: 100%; padding: 7px; border: 1px solid #edeff1; border-radius: 4px;
      margin-bottom: 8px; font-family: inherit; font-size: 13px; background: #fff;
    }
  `;

  function injectStyles() {
    if (document.getElementById("kommies-css")) return;
    const el = document.createElement("style");
    el.id = "kommies-css";
    el.textContent = CSS;
    document.head.appendChild(el);
  }

  function timeAgo(dateStr) {
    const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
    if (diff < 60) return "just now";
    if (diff < 3600) return Math.floor(diff / 60) + "m ago";
    if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
    if (diff < 2592000) return Math.floor(diff / 86400) + "d ago";
    return new Date(dateStr).toLocaleDateString();
  }

  function avatar(name) {
    const colors = ["#ff4500", "#ff6534", "#46d160", "#0079d3", "#ff585b", "#7193ff", "#ffd635", "#46a508"];
    const color = colors[(name.charCodeAt(0) + name.length) % colors.length];
    return `<div class="k-avatar" style="background:${color};">${(name[0] || "?").toUpperCase()}</div>`;
  }

  function sanitize(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function getAuthoredComments() {
    try { return JSON.parse(localStorage.getItem("kommies_authored") || "[]"); }
    catch { return []; }
  }

  function markAuthored(id) {
    const list = getAuthoredComments();
    if (!list.includes(id)) { list.push(id); localStorage.setItem("kommies_authored", JSON.stringify(list)); }
  }

  function isAuthored(id) { return getAuthoredComments().includes(id); }

  function getVoterId() {
    let id = localStorage.getItem("kommies_vid");
    if (!id) { id = "v_" + Date.now().toString(36) + Math.random().toString(36).slice(2); localStorage.setItem("kommies_vid", id); }
    return id;
  }

  function validate(name, email, content) {
    if (!name) return "Name is required.";
    if (name.length > 100) return "Name must be under 100 characters.";
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return "Please enter a valid email address.";
    if (!content) return "Comment cannot be empty.";
    if (content.length < 2) return "Comment is too short.";
    if (content.length > 5000) return "Comment must be under 5000 characters.";
    return null;
  }

  async function api(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json();
    if (!res.ok) {
      const msg = typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map(e => e.msg).join(", ")
          : "Request failed";
      throw new Error(msg);
    }
    return data;
  }

  // ── TREE BUILDER ──────────────────────────────────────────────────────────
  function buildTree(flatList) {
    const map = {};
    const roots = [];
    flatList.forEach(c => { map[c.id] = { ...c, replies: [] }; });
    flatList.forEach(c => {
      if (c.parent_id && map[c.parent_id]) map[c.parent_id].replies.push(map[c.id]);
      else roots.push(map[c.id]);
    });
    return roots;
  }

  // ── RENDER ────────────────────────────────────────────────────────────────
  function renderComment(c, depth) {
    depth = depth || 0;
    const score = (c.upvotes || 0) - (c.downvotes || 0);
    const isDeleted = c.is_deleted || c.status === "deleted";
    const isPending = c.status === "pending";
    const repliesHtml = (c.replies || []).map(r => renderComment(r, depth + 1)).join("");

    const canDelete = isAuthored(c.id) || (isLoggedIn() && _currentUser && c.commenter_id && _currentUser.id === c.commenter_id);

    const bodyHtml = isDeleted
      ? `<p class="k-text k-deleted">[comment deleted]</p>`
      : `<p class="k-text">${sanitize(c.content)}</p>
         <div class="k-actions">
           <button class="k-btn-ghost" onclick="Kommies.showReplyForm('${c.id}')">💬 Reply</button>
           <button class="k-btn-ghost" onclick="Kommies.showFlagForm('${c.id}')">⚑ Flag</button>
           ${canDelete ? `<button class="k-btn-ghost" style="color:#ea0027;" onclick="Kommies.deleteComment('${c.id}')">🗑 Delete</button>` : ""}
           ${c.is_edited ? '<span class="k-time">· edited</span>' : ""}
           ${isPending ? '<span class="k-pending">pending approval</span>' : ""}
         </div>
         <div id="krf-${c.id}"></div>
         <div id="kff-${c.id}"></div>`;

    const childrenHtml = repliesHtml
      ? `<div class="k-thread-line-wrap">
           <div class="k-thread-line" onclick="Kommies.collapse('${c.id}')" title="Collapse thread"></div>
           <div style="flex:1;min-width:0;" id="kchildren-${c.id}">${repliesHtml}</div>
         </div>`
      : `<div id="kchildren-${c.id}"></div>`;

    return `
      <div class="k-thread" id="kt-${c.id}">
        <div class="k-comment">
          <div class="k-rail">
            <button class="k-vote-btn up" onclick="Kommies.vote('${c.id}','upvote',this)" title="Upvote">▲</button>
            <span class="k-score" id="ks-${c.id}">${score}</span>
            <button class="k-vote-btn down" onclick="Kommies.vote('${c.id}','downvote',this)" title="Downvote">▼</button>
          </div>
          <div class="k-body">
            <div class="k-meta">
              ${avatar(c.author_name)}
              <span class="k-author">${sanitize(c.author_name)}</span>
              <span class="k-time">${timeAgo(c.created_at)}</span>
            </div>
            ${bodyHtml}
          </div>
        </div>
        ${childrenHtml}
      </div>`;
  }

  // ── AUTH UI HELPERS ───────────────────────────────────────────────────────
  function renderAuthBar() {
    if (isLoggedIn() && _currentUser) {
      const name = sanitize(_currentUser.display_name || _currentUser.email);
      return `
        <div class="k-auth-bar">
          <div class="k-user-pill">
            ${avatar(_currentUser.display_name || _currentUser.email)}
            <span class="k-user-name">${name}</span>
            <span class="k-auth-hint" style="flex:1;">· signed in</span>
            <button class="k-signout" onclick="Kommies.signOut()">Sign out</button>
          </div>
        </div>`;
    }

    return `
      <div class="k-auth-bar">
        <div class="k-auth-tabs">
          <button class="k-auth-tab active" id="k-tab-login" onclick="Kommies.switchTab('login')">Sign in</button>
          <button class="k-auth-tab" id="k-tab-register" onclick="Kommies.switchTab('register')">Register</button>
          <button class="k-auth-tab" id="k-tab-guest" onclick="Kommies.switchTab('guest')">Guest</button>
        </div>

        <!-- Login -->
        <div class="k-auth-panel active" id="k-panel-login">
          <input type="email" id="k-li-email" placeholder="Email" autocomplete="email" />
          <input type="password" id="k-li-pass" placeholder="Password" autocomplete="current-password" />
          <div class="k-auth-row">
            <button class="k-btn-sm" id="k-li-btn" onclick="Kommies.login()">Sign in</button>
            <span class="k-auth-error" id="k-li-err"></span>
          </div>
        </div>

        <!-- Register -->
        <div class="k-auth-panel" id="k-panel-register">
          <input type="text"  id="k-rg-name"  placeholder="Display name *" />
          <input type="email" id="k-rg-email" placeholder="Email *" autocomplete="email" />
          <input type="password" id="k-rg-pass" placeholder="Password *" autocomplete="new-password" />
          <div class="k-auth-row">
            <button class="k-btn-sm" id="k-rg-btn" onclick="Kommies.register()">Create account</button>
            <span class="k-auth-error" id="k-rg-err"></span>
          </div>
          <p class="k-auth-hint" style="margin-top:6px;">You'll receive a verification email before you can sign in.</p>
        </div>

        <!-- Guest -->
        <div class="k-auth-panel" id="k-panel-guest">
          <p class="k-auth-hint">Posting as guest — enter your name and optional email below.</p>
        </div>
      </div>`;
  }

  function renderCommentForm() {
    const locked = isLoggedIn() && _currentUser;
    const nameVal = locked ? (_currentUser.display_name || "") : "";
    const emailVal = locked ? (_currentUser.email || "") : "";
    const readOnly = locked ? 'readonly' : '';

    return `
      <div class="k-form">
        <div class="k-row">
          <input id="k-name"  placeholder="Name *"              value="${sanitize(nameVal)}"  ${readOnly} />
          <input id="k-email" type="email" placeholder="Email (optional)" value="${sanitize(emailVal)}" ${readOnly} />
        </div>
        ${!locked ? '<input id="k-website" placeholder="Website (optional)" />' : ''}
        <textarea id="k-content" placeholder="What are your thoughts?"></textarea>
        <div style="display:flex;align-items:center;gap:10px;">
          <button class="k-btn" id="k-submit" onclick="Kommies.submitComment()">Comment</button>
          <span class="k-error" id="k-error"></span>
        </div>
      </div>`;
  }

  // ── CONTROLLER ────────────────────────────────────────────────────────────
  window.Kommies = {

    async init() {
      injectStyles();
      const container = document.getElementById("kommies-comments");
      if (!container) { console.error("[Kommies] #kommies-comments not found"); return; }
      container.innerHTML = `<div id="kommies"><p style="color:#878a8c;font-size:14px;">Loading...</p></div>`;

      // Restore session if token exists
      await loadCurrentUser();

      try {
        let thread;
        try {
          thread = await api("GET", `/comments/${cfg.api_key}/threads/${IDENTIFIER}`);
          THREAD_ID = thread.id;
        } catch {
          thread = { id: null, comment_count: 0 };
        }

        THREAD_ID = thread.id;
        this._renderShell(container, thread.comment_count || 0);
        if (THREAD_ID) await this._loadComments();
      } catch (e) {
        container.innerHTML = `<div id="kommies"><p class="k-error">Failed to load: ${e.message}</p></div>`;
      }
    },

    _renderShell(container, count) {
      container.innerHTML = `
        <div id="kommies">
          <h3 id="k-count">${count} Comment${count !== 1 ? "s" : ""}</h3>
          ${renderAuthBar()}
          ${renderCommentForm()}
          <div id="k-list"></div>
        </div>`;
    },

    async _loadComments() {
      if (!THREAD_ID) return;
      const list = document.getElementById("k-list");
      if (!list) return;
      try {
        const data = await api("GET",
          `/comments/${cfg.api_key}/threads/${IDENTIFIER}/comments?page=1&page_size=500`);
        const tree = buildTree(data.items || []);
        list.innerHTML = tree.length === 0
          ? '<p class="k-empty">No comments yet — be the first!</p>'
          : tree.map(c => renderComment(c, 0)).join('<hr class="k-divider"/>');
      } catch (e) {
        if (list) list.innerHTML = `<p class="k-error">${e.message}</p>`;
      }
    },

    // ── AUTH ACTIONS ───────────────────────────────────────────────────────

    switchTab(tab) {
      ["login", "register", "guest"].forEach(t => {
        const tabEl = document.getElementById(`k-tab-${t}`);
        const panelEl = document.getElementById(`k-panel-${t}`);
        if (tabEl) tabEl.classList.toggle("active", t === tab);
        if (panelEl) panelEl.classList.toggle("active", t === tab);
      });
    },

    async login() {
      const email = (document.getElementById("k-li-email")?.value || "").trim();
      const pass = (document.getElementById("k-li-pass")?.value || "").trim();
      const errEl = document.getElementById("k-li-err");
      const btn = document.getElementById("k-li-btn");

      if (!email || !pass) { errEl.textContent = "Email and password required."; return; }
      errEl.textContent = "";
      btn.disabled = true; btn.textContent = "Signing in...";

      try {
        const data = await api("POST", "/commenters/login", { email, password: pass });
        setToken(data.access_token);
        await loadCurrentUser();
        this._refreshAuthUI();
      } catch (e) {
        errEl.textContent = e.message;
      } finally {
        btn.disabled = false; btn.textContent = "Sign in";
      }
    },

    async register() {
      const name = (document.getElementById("k-rg-name")?.value || "").trim();
      const email = (document.getElementById("k-rg-email")?.value || "").trim();
      const pass = (document.getElementById("k-rg-pass")?.value || "").trim();
      const errEl = document.getElementById("k-rg-err");
      const btn = document.getElementById("k-rg-btn");

      if (!name) { errEl.textContent = "Display name is required."; return; }
      if (!email) { errEl.textContent = "Email is required."; return; }
      if (!pass || pass.length < 6) { errEl.textContent = "Password must be at least 6 characters."; return; }
      errEl.textContent = "";
      btn.disabled = true; btn.textContent = "Creating...";

      try {
        await api("POST", "/commenters/register", { display_name: name, email, password: pass });
        // Show success — user needs to verify email before logging in
        const panel = document.getElementById("k-panel-register");
        if (panel) panel.innerHTML = `
          <p style="color:#46a508;font-size:13px;font-weight:600;">Account created!</p>
          <p class="k-auth-hint">Check your inbox to verify your email, then sign in.</p>
          <button class="k-btn-sm" style="margin-top:8px;" onclick="Kommies.switchTab('login')">Go to sign in</button>`;
      } catch (e) {
        errEl.textContent = e.message;
        btn.disabled = false; btn.textContent = "Create account";
      }
    },

    signOut() {
      clearToken();
      this._refreshAuthUI();
    },

    _refreshAuthUI() {
      // Rebuild auth bar + comment form in place without reloading comments
      const authBarEl = document.querySelector("#kommies .k-auth-bar");
      const formEl = document.querySelector("#kommies .k-form");

      if (authBarEl) authBarEl.outerHTML = renderAuthBar();
      if (formEl) formEl.outerHTML = renderCommentForm();
    },

    // ── COMMENT ACTIONS ────────────────────────────────────────────────────

    async submitComment() {
      const locked = isLoggedIn() && _currentUser;
      const name = locked
        ? (_currentUser.display_name || _currentUser.email)
        : (document.getElementById("k-name")?.value || "").trim();
      const email = locked
        ? _currentUser.email
        : (document.getElementById("k-email")?.value || "").trim();
      const website = locked ? null : (document.getElementById("k-website")?.value || "").trim();
      const content = (document.getElementById("k-content")?.value || "").trim();
      const errEl = document.getElementById("k-error");
      const btn = document.getElementById("k-submit");

      const err = validate(name, email, content);
      if (err) { errEl.textContent = err; return; }
      errEl.textContent = "";
      btn.disabled = true; btn.textContent = "Posting...";

      try {
        const comment = await api("POST",
          `/comments/${cfg.api_key}/threads/${IDENTIFIER}/comments?url=${encodeURIComponent(PAGE_URL)}`,
          { author_name: name, author_email: email || null, author_website: website || null, content }
        );

        THREAD_ID = comment.thread_id;
        markAuthored(comment.id);

        const countEl = document.getElementById("k-count");
        if (countEl) {
          const cur = parseInt(countEl.textContent) || 0;
          countEl.textContent = `${cur + 1} Comment${cur + 1 !== 1 ? "s" : ""}`;
        }

        document.getElementById("k-content").value = "";

        const list = document.getElementById("k-list");
        if (list) {
          const empty = list.querySelector(".k-empty");
          if (empty) empty.remove();
          const div = document.createElement("div");
          div.innerHTML = renderComment({ ...comment, replies: [] }, 0) + '<hr class="k-divider"/>';
          list.insertBefore(div, list.firstChild);
        }
      } catch (e) {
        errEl.textContent = e.message;
      } finally {
        btn.disabled = false; btn.textContent = "Comment";
      }
    },

    showReplyForm(parentId) {
      const el = document.getElementById(`krf-${parentId}`);
      if (!el || el.innerHTML) return;
      const locked = isLoggedIn() && _currentUser;
      const nameVal = locked ? sanitize(_currentUser.display_name || _currentUser.email) : "";
      const emailVal = locked ? sanitize(_currentUser.email) : "";
      const ro = locked ? "readonly" : "";
      el.innerHTML = `
        <div class="k-form" style="margin-top:10px;">
          <div class="k-row">
            <input id="rn-${parentId}" placeholder="Name *"           value="${nameVal}"  ${ro} />
            <input id="re-${parentId}" type="email" placeholder="Email (optional)" value="${emailVal}" ${ro} />
          </div>
          <textarea id="rc-${parentId}" placeholder="Write a reply..."></textarea>
          <div style="display:flex;align-items:center;gap:8px;">
            <button class="k-btn" onclick="Kommies.submitReply('${parentId}')">Reply</button>
            <button class="k-btn-ghost" onclick="Kommies.hideReplyForm('${parentId}')">Cancel</button>
            <span class="k-error" id="rerr-${parentId}"></span>
          </div>
        </div>`;
    },

    hideReplyForm(parentId) {
      const el = document.getElementById(`krf-${parentId}`);
      if (el) el.innerHTML = "";
    },

    async submitReply(parentId) {
      const locked = isLoggedIn() && _currentUser;
      const name = locked
        ? (_currentUser.display_name || _currentUser.email)
        : (document.getElementById(`rn-${parentId}`)?.value || "").trim();
      const email = locked
        ? _currentUser.email
        : (document.getElementById(`re-${parentId}`)?.value || "").trim();
      const content = (document.getElementById(`rc-${parentId}`)?.value || "").trim();
      const errEl = document.getElementById(`rerr-${parentId}`);

      const err = validate(name, email, content);
      if (err) { errEl.textContent = err; return; }
      errEl.textContent = "";

      try {
        const comment = await api("POST",
          `/comments/${cfg.api_key}/threads/${IDENTIFIER}/comments?url=${encodeURIComponent(PAGE_URL)}`,
          { author_name: name, author_email: email || null, content, parent_id: parentId }
        );

        markAuthored(comment.id);
        this.hideReplyForm(parentId);

        let children = document.getElementById(`kchildren-${parentId}`);
        if (children) {
          const parentThread = document.getElementById(`kt-${parentId}`);
          const hasLine = parentThread?.querySelector(".k-thread-line");
          if (!hasLine && children.innerHTML === "") {
            const wrapper = document.createElement("div");
            wrapper.className = "k-thread-line-wrap";
            wrapper.innerHTML = `<div class="k-thread-line" onclick="Kommies.collapse('${parentId}')" title="Collapse thread"></div>
              <div style="flex:1;min-width:0;" id="kchildren-${parentId}"></div>`;
            children.replaceWith(wrapper);
            children = document.getElementById(`kchildren-${parentId}`);
          }
          if (children) {
            const div = document.createElement("div");
            div.innerHTML = renderComment({ ...comment, replies: [] }, 0);
            children.appendChild(div);
          }
        }
      } catch (e) {
        errEl.textContent = e.message;
      }
    },

    async vote(commentId, voteType, btn) {
      try {
        const result = await api("POST",
          `/comments/${cfg.api_key}/comments/${commentId}/vote`,
          { vote_type: voteType, voter_identifier: getVoterId() }
        );
        const scoreEl = document.getElementById(`ks-${commentId}`);
        if (scoreEl) scoreEl.textContent = (result.upvotes || 0) - (result.downvotes || 0);
        const thread = document.getElementById(`kt-${commentId}`);
        if (thread) {
          thread.querySelectorAll(".k-vote-btn").forEach(b => b.classList.remove("active-up", "active-down"));
          btn.classList.add(voteType === "upvote" ? "active-up" : "active-down");
        }
      } catch (e) { console.warn("[Kommies] Vote:", e.message); }
    },

    collapse(commentId) {
      const children = document.getElementById(`kchildren-${commentId}`);
      const wrap = children?.parentElement;
      if (!wrap) return;
      wrap.style.display = wrap.style.display === "none" ? "" : "none";
    },

    showFlagForm(commentId) {
      const el = document.getElementById(`kff-${commentId}`);
      if (!el || el.innerHTML) return;
      el.innerHTML = `
        <div class="k-flag-form">
          <select id="fr-${commentId}">
            <option value="spam">Spam</option>
            <option value="offensive">Offensive or abusive</option>
            <option value="off_topic">Off topic</option>
            <option value="misinformation">Misinformation</option>
            <option value="other">Other</option>
          </select>
          <div style="display:flex;gap:8px;align-items:center;">
            <button class="k-btn" style="background:#ea0027;" onclick="Kommies.submitFlag('${commentId}')">Report</button>
            <button class="k-btn-ghost" onclick="Kommies.hideFlagForm('${commentId}')">Cancel</button>
            <span class="k-error" id="ferr-${commentId}"></span>
          </div>
        </div>`;
    },

    hideFlagForm(commentId) {
      const el = document.getElementById(`kff-${commentId}`);
      if (el) el.innerHTML = "";
    },

    async deleteComment(commentId) {
      if (!confirm("Delete your comment? This cannot be undone.")) return;
      try {
        await api("DELETE", `/comments/${cfg.api_key}/comments/${commentId}`);
        const body = document.querySelector(`#kt-${commentId} .k-body`);
        if (body) {
          const text = body.querySelector(".k-text");
          if (text) text.outerHTML = '<p class="k-text k-deleted">[comment deleted]</p>';
          const actions = body.querySelector(".k-actions");
          if (actions) actions.remove();
        }
        const scoreEl = document.getElementById(`ks-${commentId}`);
        if (scoreEl) scoreEl.closest(".k-rail")?.querySelectorAll(".k-vote-btn").forEach(b => b.remove());
      } catch (e) { alert("Could not delete: " + e.message); }
    },

    async submitFlag(commentId) {
      const reason = document.getElementById(`fr-${commentId}`)?.value;
      const errEl = document.getElementById(`ferr-${commentId}`);
      try {
        await api("POST",
          `/comments/${cfg.api_key}/comments/${commentId}/flag`,
          { reason, reporter_identifier: getVoterId() }
        );
        this.hideFlagForm(commentId);
        alert("Reported. Thank you!");
      } catch (e) { if (errEl) errEl.textContent = e.message; }
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => Kommies.init());
  } else {
    Kommies.init();
  }

})();