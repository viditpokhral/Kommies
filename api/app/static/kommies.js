/*!
 * Kommies Comment Plugin v2.0.0
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

  // ── STYLES ────────────────────────────────────────────────────────────────
  const CSS = `
    #kommies {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px; color: #1c1c1c; max-width: 740px; margin: 0 auto;
    }
    #kommies * { box-sizing: border-box; }
    #kommies h3 { font-size: 17px; font-weight: 700; margin: 0 0 18px; color: #0f0f0f; }

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

  function getVoterId() {
    let id = localStorage.getItem("kommies_vid");
    if (!id) {
      id = "v_" + Date.now().toString(36) + Math.random().toString(36).slice(2);
      localStorage.setItem("kommies_vid", id);
    }
    return id;
  }

  async function api(method, path, body) {
    const res = await fetch(`${API}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
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
  // Takes flat list from API, builds nested tree by parent_id
  function buildTree(flatList) {
    const map = {};
    const roots = [];
    flatList.forEach(c => { map[c.id] = { ...c, replies: [] }; });
    flatList.forEach(c => {
      if (c.parent_id && map[c.parent_id]) {
        map[c.parent_id].replies.push(map[c.id]);
      } else {
        roots.push(map[c.id]);
      }
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

    const bodyHtml = isDeleted
      ? `<p class="k-text k-deleted">[comment deleted]</p>`
      : `<p class="k-text">${sanitize(c.content)}</p>
         <div class="k-actions">
           <button class="k-btn-ghost" onclick="Kommies.showReplyForm('${c.id}')">💬 Reply</button>
           <button class="k-btn-ghost" onclick="Kommies.showFlagForm('${c.id}')">⚑ Flag</button>
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

  // ── CONTROLLER ────────────────────────────────────────────────────────────
  window.Kommies = {

    async init() {
      injectStyles();
      const container = document.getElementById("kommies-comments");
      if (!container) { console.error("[Kommies] #kommies-comments not found"); return; }
      container.innerHTML = `<div id="kommies"><p style="color:#878a8c;font-size:14px;">Loading comments...</p></div>`;

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
          <div class="k-form">
            <div class="k-row">
              <input id="k-name" placeholder="Name *" />
              <input id="k-email" type="email" placeholder="Email (optional)" />
            </div>
            <input id="k-website" placeholder="Website (optional)" />
            <textarea id="k-content" placeholder="What are your thoughts?"></textarea>
            <div style="display:flex;align-items:center;gap:10px;">
              <button class="k-btn" id="k-submit" onclick="Kommies.submitComment()">Comment</button>
              <span class="k-error" id="k-error"></span>
            </div>
          </div>
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

    async submitComment() {
      const name = (document.getElementById("k-name")?.value || "").trim();
      const email = (document.getElementById("k-email")?.value || "").trim();
      const website = (document.getElementById("k-website")?.value || "").trim();
      const content = (document.getElementById("k-content")?.value || "").trim();
      const errEl = document.getElementById("k-error");
      const btn = document.getElementById("k-submit");

      if (!name) { errEl.textContent = "Name is required."; return; }
      if (!content) { errEl.textContent = "Comment cannot be empty."; return; }
      errEl.textContent = "";
      btn.disabled = true; btn.textContent = "Posting...";

      try {
        const comment = await api("POST",
          `/comments/${cfg.api_key}/threads/${IDENTIFIER}/comments?url=${encodeURIComponent(PAGE_URL)}`,
          { author_name: name, author_email: email || null, author_website: website || null, content }
        );

        THREAD_ID = comment.thread_id;

        const countEl = document.getElementById("k-count");
        if (countEl) {
          const cur = parseInt(countEl.textContent) || 0;
          countEl.textContent = `${cur + 1} Comment${cur + 1 !== 1 ? "s" : ""}`;
        }

        ["k-name", "k-email", "k-website", "k-content"].forEach(id => {
          const el = document.getElementById(id); if (el) el.value = "";
        });

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
      el.innerHTML = `
        <div class="k-form" style="margin-top:10px;">
          <div class="k-row">
            <input id="rn-${parentId}" placeholder="Name *" />
            <input id="re-${parentId}" type="email" placeholder="Email (optional)" />
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
      const name = (document.getElementById(`rn-${parentId}`)?.value || "").trim();
      const email = (document.getElementById(`re-${parentId}`)?.value || "").trim();
      const content = (document.getElementById(`rc-${parentId}`)?.value || "").trim();
      const errEl = document.getElementById(`rerr-${parentId}`);

      if (!name) { errEl.textContent = "Name is required."; return; }
      if (!content) { errEl.textContent = "Reply cannot be empty."; return; }
      errEl.textContent = "";

      try {
        const comment = await api("POST",
          `/comments/${cfg.api_key}/threads/${IDENTIFIER}/comments?url=${encodeURIComponent(PAGE_URL)}`,
          { author_name: name, author_email: email || null, content, parent_id: parentId }
        );

        this.hideReplyForm(parentId);

        // Inject reply into parent's children container
        let children = document.getElementById(`kchildren-${parentId}`);
        if (children) {
          // If no thread line yet, wrap children with the line
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
      } catch (e) {
        console.warn("[Kommies] Vote:", e.message);
      }
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
      } catch (e) {
        if (errEl) errEl.textContent = e.message;
      }
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => Kommies.init());
  } else {
    Kommies.init();
  }

})();