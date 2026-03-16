/* kommies-dashboard utils.js
   Load at bottom of base.html scripts block, or via {% block scripts %} in child.
   window.toast() is already defined in base.html — don't duplicate it here.
*/

'use strict';

/* ── CSRF helper for fetch() calls ─────────────────── */
function getCsrf() {
    return document.cookie.split('; ')
        .find(r => r.startsWith('csrftoken='))
        ?.split('=')[1] || '';
}

/* ── Generic POST helper ────────────────────────────── */
async function dashPost(url, body) {
    const res = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCsrf(),
        },
        body: new URLSearchParams(body).toString(),
    });
    return res.json();
}

/* ── Confirm + action helper (moderation buttons) ───── */
async function confirmAction(msg, url, body, successMsg) {
    if (!confirm(msg)) return;
    const data = await dashPost(url, body);
    if (data.success) {
        window.toast(successMsg || 'Done', 'success');
    } else {
        window.toast(data.error || 'Action failed', 'error');
    }
    return data;
}

/* ── Fade-remove a DOM row ──────────────────────────── */
function fadeRemove(el, ms) {
    ms = ms || 280;
    el.style.transition = 'opacity ' + ms + 'ms';
    el.style.opacity = '0';
    setTimeout(function () { el.remove(); }, ms);
}