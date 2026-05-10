'use strict';

// ── Toast notifications ───────────────────────────────────────────────────────
function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const icons = { info: 'i', success: '✓', error: '✕', warning: '!' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.setAttribute('role', 'status');
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || 'i'}</span>
    <div class="toast-body"><div class="toast-title">${escHtml(message)}</div></div>
    <button class="toast-close" aria-label="Закрыть">✕</button>
  `;
  const close = () => { toast.classList.add('removing'); toast.addEventListener('animationend', () => toast.remove(), { once: true }); };
  toast.querySelector('.toast-close').addEventListener('click', close);
  container.appendChild(toast);
  setTimeout(close, duration);
}

function escHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── Dropdowns ─────────────────────────────────────────────────────────────────
document.querySelectorAll('[data-dropdown]').forEach(wrap => {
  const toggle = wrap.querySelector('button');
  const menu = wrap.querySelector('[role="menu"]');
  if (!toggle || !menu) return;
  toggle.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = !menu.hidden;
    menu.hidden = isOpen;
    toggle.setAttribute('aria-expanded', !isOpen);
  });
  document.addEventListener('click', () => { menu.hidden = true; toggle.setAttribute('aria-expanded', 'false'); });
  menu.addEventListener('click', e => e.stopPropagation());
});

// ── Logout ────────────────────────────────────────────────────────────────────
document.querySelectorAll('[data-action="logout"]').forEach(btn => {
  btn.addEventListener('click', async () => {
    await fetch('/api/v1/auth/logout', { method: 'POST' });
    window.location.href = '/auth/login';
  });
});

// ── API fetch helper ──────────────────────────────────────────────────────────
function apiFetch(url, options = {}) {
  return fetch(url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    credentials: 'same-origin',
  });
}

// ── Real Notifications System ─────────────────────────────────────────────────
let _notifOpen = false;

function formatTimeAgo(iso) {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso)) / 1000;
  if (diff < 60) return 'только что';
  if (diff < 3600) return Math.floor(diff / 60) + ' мин. назад';
  if (diff < 86400) return Math.floor(diff / 3600) + ' ч. назад';
  if (diff < 604800) return Math.floor(diff / 86400) + ' дн. назад';
  return new Date(iso).toLocaleDateString('ru-RU');
}

function getNotifIcon(kind) {
  const icons = {
    ban: '🚫', unban: '✅', role_changed: '👤', book_removed: '📕',
    moderation: '⚠️', review: '💬', bookmark: '🔖', follow: '👥', default: '🔔'
  };
  return icons[kind] || icons.default;
}

async function loadNotifications() {
  const list = document.getElementById('notif-list');
  const badge = document.getElementById('notif-badge');
  if (!list) return;
  try {
    const resp = await fetch('/api/notifications', { credentials: 'same-origin' });
    if (!resp.ok) throw new Error('not logged in');
    const data = await resp.json();

    // Update badge
    if (badge) {
      if (data.unread > 0) {
        badge.textContent = data.unread > 9 ? '9+' : data.unread;
        badge.style.display = 'flex';
      } else {
        badge.style.display = 'none';
      }
    }

    if (!data.items || data.items.length === 0) {
      list.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--text-muted);font-family:var(--font-serif);font-size:1rem;">Уведомлений нет</div>';
      return;
    }

    list.innerHTML = data.items.map(n => `
      <div data-notif-id="${n.id}" onclick="clickNotif(${n.id},'${n.link||''}')"
           style="padding:0.85rem 1rem;border-bottom:1px solid var(--border-light);cursor:pointer;transition:background 0.15s;${n.is_read ? 'opacity:0.65;' : 'background:rgba(139,115,85,0.04);'}">
        <div style="display:flex;align-items:flex-start;gap:0.6rem;">
          <span style="font-size:1.1rem;flex-shrink:0;">${getNotifIcon(n.kind)}</span>
          <div style="flex:1;min-width:0;">
            <div style="font-family:var(--font-sans);font-size:0.88rem;font-weight:${n.is_read ? '400' : '600'};color:var(--text-primary);margin-bottom:0.2rem;">${escHtml(n.title)}</div>
            ${n.body ? `<div style="font-family:var(--font-sans);font-size:0.78rem;color:var(--text-muted);">${escHtml(n.body)}</div>` : ''}
            <div style="font-family:var(--font-sans);font-size:0.72rem;color:var(--text-muted);margin-top:0.25rem;">${formatTimeAgo(n.created_at)}</div>
          </div>
          ${!n.is_read ? '<div style="width:8px;height:8px;border-radius:50%;background:var(--primary);flex-shrink:0;margin-top:4px;"></div>' : ''}
        </div>
      </div>
    `).join('');
  } catch (e) {
    if (list) list.innerHTML = '';
    if (badge) badge.style.display = 'none';
  }
}

async function clickNotif(id, link) {
  await fetch(`/api/notifications/${id}/read`, { method: 'POST', credentials: 'same-origin' });
  const el = document.querySelector(`[data-notif-id="${id}"]`);
  if (el) { el.style.opacity = '0.65'; el.querySelector('div[style*="border-radius:50%"]')?.remove(); }
  const badge = document.getElementById('notif-badge');
  if (badge) {
    const cur = parseInt(badge.textContent) || 0;
    if (cur <= 1) badge.style.display = 'none';
    else badge.textContent = cur - 1;
  }
  if (link) window.location.href = link;
}

async function markAllRead() {
  await fetch('/api/notifications/read-all', { method: 'POST', credentials: 'same-origin' });
  document.getElementById('notif-badge')?.style && (document.getElementById('notif-badge').style.display = 'none');
  await loadNotifications();
}

function toggleNotifPanel() {
  const panel = document.getElementById('notif-panel');
  if (!panel) return;
  _notifOpen = !_notifOpen;
  panel.style.display = _notifOpen ? 'block' : 'none';
  if (_notifOpen) {
    loadNotifications();
    setTimeout(() => {
      document.addEventListener('click', function closePanel(e) {
        const wrapper = document.getElementById('notif-wrapper');
        if (!wrapper || !wrapper.contains(e.target)) {
          panel.style.display = 'none';
          _notifOpen = false;
          document.removeEventListener('click', closePanel);
        }
      });
    }, 50);
  }
}

// Load badge count on page load
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('notif-badge')) {
    loadNotifications();
    setInterval(loadNotifications, 60000); // refresh every minute
  }
});

// ── Bookmark button ───────────────────────────────────────────────────────────
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-bookmark]');
  if (!btn) return;
  e.preventDefault();
  const bookId = btn.dataset.bookmark;
  try {
    const resp = await fetch(`/api/books/${bookId}/bookmark`, { method: 'POST', credentials: 'same-origin' });
    if (resp.status === 401) { showToast('Войдите, чтобы добавить в закладки', 'warning'); return; }
    const data = await resp.json();
    const isNow = data.bookmarked;
    btn.setAttribute('aria-pressed', isNow ? 'true' : 'false');
    btn.style.background = isNow ? 'var(--primary)' : 'transparent';
    btn.style.color = isNow ? 'white' : 'var(--primary)';
    const countEl = btn.querySelector('[data-count]');
    if (countEl) countEl.textContent = data.count ?? (parseInt(countEl.textContent || '0') + (isNow ? 1 : -1));
    // Update SVG fill
    const svg = btn.querySelector('svg path');
    if (svg) svg.setAttribute('fill', isNow ? 'currentColor' : 'none');
    showToast(isNow ? 'Добавлено в закладки' : 'Удалено из закладок', 'success');
  } catch { showToast('Ошибка', 'error'); }
});

// ── Report book modal ─────────────────────────────────────────────────────────
window.openReportModal = function(bookId) {
  let modal = document.getElementById('report-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'report-modal';
    modal.style.cssText = 'display:flex;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:500;align-items:center;justify-content:center;';
    modal.innerHTML = `
      <div style="background:var(--bg-surface);border-radius:var(--radius-xl);padding:2rem;max-width:420px;width:90%;box-shadow:var(--shadow-xl);">
        <h3 style="font-family:var(--font-serif);font-size:1.2rem;margin-bottom:1rem;">Пожаловаться на книгу</h3>
        <div style="display:flex;flex-direction:column;gap:0.5rem;margin-bottom:1rem;" id="report-reasons">
          ${['spam','prohibited','copyright','adult_no_mark','other'].map(r => {
            const labels = {spam:'Спам',prohibited:'Запрещённый контент',copyright:'Нарушение авторских прав',adult_no_mark:'18+ без маркировки',other:'Другое'};
            return `<label style="display:flex;align-items:center;gap:0.5rem;padding:0.5rem 0.75rem;border-radius:var(--radius-md);border:1px solid var(--border-light);cursor:pointer;font-family:var(--font-sans);font-size:0.88rem;">
              <input type="radio" name="report-reason" value="${r}"> ${labels[r]}
            </label>`;
          }).join('')}
        </div>
        <textarea id="report-comment" placeholder="Комментарий (необязательно)" class="form-control" rows="2" style="margin-bottom:1rem;"></textarea>
        <div style="display:flex;gap:0.75rem;justify-content:flex-end;">
          <button onclick="document.getElementById('report-modal').remove()" class="btn btn-ghost">Отмена</button>
          <button id="report-submit" class="btn btn-primary">Отправить</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  }
  modal.style.display = 'flex';
  document.getElementById('report-submit').onclick = async () => {
    const reason = document.querySelector('input[name="report-reason"]:checked')?.value;
    if (!reason) { showToast('Выберите причину', 'warning'); return; }
    const comment = document.getElementById('report-comment')?.value || '';
    try {
      const resp = await fetch(`/api/books/${bookId}/report?reason=${encodeURIComponent(reason)}&comment=${encodeURIComponent(comment)}`, { method:'POST', credentials:'same-origin' });
      if (resp.status === 401) { showToast('Войдите, чтобы отправить жалобу', 'warning'); return; }
      showToast('Жалоба отправлена. Спасибо!', 'success');
      modal.remove();
    } catch { showToast('Ошибка', 'error'); }
  };
};

// ── Toggle book/chapter visibility (author) ───────────────────────────────────
window.toggleBookVisibility = async function(bookId, btn) {
  try {
    const resp = await fetch(`/api/books/${bookId}/toggle-visibility`, { method:'POST', credentials:'same-origin' });
    const data = await resp.json();
    if (btn) btn.textContent = data.hidden ? 'Показать' : 'Скрыть';
    showToast(data.hidden ? 'Книга скрыта в черновики' : 'Книга снова видна', 'success');
  } catch { showToast('Ошибка', 'error'); }
};

window.toggleChapterVisibility = async function(chapterId, btn) {
  const SVG_VISIBLE = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>';
  const SVG_HIDDEN  = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
  try {
    const resp = await fetch(`/api/chapters/${chapterId}/toggle-visibility`, { method:'POST', credentials:'same-origin' });
    const data = await resp.json();
    if (btn) {
      btn.innerHTML = data.hidden ? SVG_HIDDEN : SVG_VISIBLE;
      btn.title = data.hidden ? 'Показать' : 'Скрыть';
      btn.style.color = data.hidden ? '#dc2626' : 'var(--text-muted)';
      btn.style.borderColor = data.hidden ? '#fca5a5' : 'var(--border-light)';
      const row = btn.closest('div');
      if (row) {
        row.style.borderColor = data.hidden ? '#fecaca' : 'var(--border-light)';
        row.style.background = data.hidden ? '#fef2f2' : 'transparent';
      }
    }
    showToast(data.hidden ? 'Глава скрыта' : 'Глава видна', 'success');
  } catch { showToast('Ошибка', 'error'); }
};

// ── Password strength ─────────────────────────────────────────────────────────
const pwdInput = document.getElementById('password');
const pwdBar = document.querySelector('.pwd-bar');
if (pwdInput && pwdBar) {
  pwdInput.addEventListener('input', () => {
    const v = pwdInput.value;
    let score = 0;
    if (v.length >= 8) score++;
    if (/[A-Z]/.test(v)) score++;
    if (/[0-9]/.test(v)) score++;
    if (/[^a-zA-Z0-9]/.test(v)) score++;
    const colors = ['', '#C4566A', '#E4943A', '#C4973A', '#4A8B7A'];
    pwdBar.style.width = `${score * 25}%`;
    pwdBar.style.background = colors[score] || colors[1];
  });
}

// ── Password toggle ───────────────────────────────────────────────────────────
document.querySelectorAll('.pwd-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    const input = document.getElementById(btn.dataset.target);
    if (!input) return;
    input.type = input.type === 'password' ? 'text' : 'password';
  });
});

// ── Auto-hide alerts ──────────────────────────────────────────────────────────
document.querySelectorAll('[data-auto-hide]').forEach(el => {
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.5s'; setTimeout(() => el.remove(), 500); }, 4000);
});

// ── Auto-refresh access token ─────────────────────────────────────────────────
setInterval(async () => {
  try { await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'same-origin' }); } catch {}
}, (30 - 2) * 60 * 1000);