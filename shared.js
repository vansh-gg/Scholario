// ── CONFIG ────────────────────────────────────────────────────
// Works whether you open via localhost:8000 or file:// 
const API = 'http://localhost:8000/api';

function getUser() {
  const u = localStorage.getItem('scholario_user');
  if (!u) { location.href = 'index.html'; return null; }
  return JSON.parse(u);
}

function logout() {
  localStorage.removeItem('scholario_user');
  location.href = 'index.html';
}

// ── DATE / TIME ───────────────────────────────────────────────
function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = (Date.now() - new Date(dateStr)) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function formatDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatDateTime(d) {
  if (!d) return '—';
  return new Date(d).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function countdownHTML(dueDateStr) {
  if (!dueDateStr) return '';
  const ms = new Date(dueDateStr) - Date.now();
  if (ms <= 0) return `<span class="badge badge-red">Overdue</span>`;
  const h = Math.floor(ms / 3600000);
  const d = Math.floor(h / 24);
  if (d > 1) return `<span class="badge badge-gray">⏰ ${d}d left</span>`;
  if (h >= 1) return `<span class="badge badge-yellow">⏰ ${h}h left</span>`;
  return `<span class="badge badge-red">⏰ &lt;1h left</span>`;
}

// ── COLORS / BADGES ───────────────────────────────────────────
function attColor(pct) {
  if (pct >= 85) return 'var(--green)';
  if (pct >= 75) return 'var(--yellow)';
  return 'var(--red)';
}

function notifColor(t) {
  return { info: 'var(--accent)', warning: 'var(--yellow)', success: 'var(--green)', urgent: 'var(--red)' }[t] || 'var(--text3)';
}

function gradeBadgeClass(g) {
  return { 'O': 'grade-O', 'A+': 'grade-Ap', 'A': 'grade-A', 'B+': 'grade-Bp', 'B': 'grade-B', 'F': 'grade-F' }[g] || 'grade-F';
}

function gradeBadgeHTML(g) {
  return `<span class="grade-badge ${gradeBadgeClass(g)}">${g || '—'}</span>`;
}

function statusBadge(status) {
  const map = {
    checked:    `<span class="badge badge-green">✓ Graded</span>`,
    submitted:  `<span class="badge badge-blue">⏳ Submitted</span>`,
    pending:    `<span class="badge badge-gray">— Pending</span>`,
    present:    `<span class="badge badge-green">Present</span>`,
    absent:     `<span class="badge badge-red">Absent</span>`,
    late:       `<span class="badge badge-yellow">Late</span>`,
    not_marked: `<span class="badge badge-gray">Not Marked</span>`,
    info:       `<span class="badge badge-blue">Info</span>`,
    warning:    `<span class="badge badge-yellow">Warning</span>`,
    success:    `<span class="badge badge-green">Success</span>`,
    urgent:     `<span class="badge badge-red">Urgent</span>`,
  };
  return map[status] || `<span class="badge badge-gray">${status || '—'}</span>`;
}

function diffBadge(d) {
  if (!d) return '';
  const map = { Easy: 'badge-green', Medium: 'badge-yellow', Hard: 'badge-red' };
  return `<span class="badge ${map[d] || 'badge-gray'}">${d}</span>`;
}

function plagBadge(flag) {
  return flag ? `<span class="badge badge-red">⚠ Plagiarism</span>` : '';
}

function lateBadge(flag) {
  return flag ? `<span class="badge badge-yellow">Late</span>` : '';
}

// ── MODAL ─────────────────────────────────────────────────────
function openModal(id) {
  document.getElementById(id)?.classList.add('open');
}

function closeModal(id) {
  document.getElementById(id)?.classList.remove('open');
}

// ── TOAST ─────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const existing = document.getElementById('__toast');
  if (existing) existing.remove();
  const colors = {
    success: { bg: 'var(--green-bg)', border: 'rgba(22,163,74,0.3)', text: 'var(--green)' },
    error:   { bg: 'var(--red-bg)',   border: 'rgba(220,38,38,0.3)', text: 'var(--red)' },
    info:    { bg: 'var(--accent-bg)', border: 'rgba(37,99,235,0.3)', text: 'var(--accent)' },
  };
  const c = colors[type] || colors.info;
  const t = document.createElement('div');
  t.id = '__toast';
  t.style.cssText = `position:fixed;bottom:24px;right:24px;z-index:9999;background:${c.bg};border:1px solid ${c.border};color:${c.text};padding:12px 18px;border-radius:10px;font-size:13px;font-weight:600;box-shadow:0 8px 24px rgba(0,0,0,0.12);animation:fadeUp 0.3s ease`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

// ── API ───────────────────────────────────────────────────────
async function apiFetch(url, opts = {}) {
  try {
    const res = await fetch(API + url, {
      headers: { 'Content-Type': 'application/json' },
      ...opts
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${res.status})`);
    }
    return await res.json();
  } catch (e) {
    console.error('API error:', e);
    throw e;
  }
}

// ── SIDEBAR ───────────────────────────────────────────────────
function buildSidebar(role, active) {
  const user = getUser();
  if (!user) return;

  const navs = {
    student: [
      { icon: '🏠', label: 'Dashboard',     href: 'student-dashboard.html' },
      { icon: '📋', label: 'Assignments',   href: 'student-assignments.html' },
      { icon: '📅', label: 'Attendance',    href: 'student-attendance.html' },
      { icon: '💬', label: 'Remarks',       href: 'student-remarks.html' },
      { icon: '🔔', label: 'Notifications', href: 'student-notifications.html' },
    ],
    faculty: [
      { icon: '🏠', label: 'Dashboard',    href: 'faculty-dashboard.html' },
      { icon: '📝', label: 'Assignments',  href: 'faculty-assignments.html' },
      { icon: '📬', label: 'Submissions',  href: 'faculty-submissions.html' },
      { icon: '📅', label: 'Attendance',   href: 'faculty-attendance.html' },
      { icon: '⚠️', label: 'At-Risk',      href: 'faculty-atrisk.html' },
      { icon: '🔍', label: 'Plagiarism',   href: 'faculty-plagiarism.html' },
    ],
    admin: [
      { icon: '🏠', label: 'Dashboard',  href: 'admin-dashboard.html' },
      { icon: '👥', label: 'Students',   href: 'admin-students.html' },
      { icon: '⚠️', label: 'At-Risk',    href: 'admin-atrisk.html' },
      { icon: '🔍', label: 'Plagiarism', href: 'admin-plagiarism.html' },
      { icon: '📋', label: 'Audit Log',  href: 'admin-audit.html' },
    ]
  };

  const initials = user.name.split(' ').slice(0, 2).map(n => n[0]).join('').toUpperCase();
  const roleLabel = { student: 'Student', faculty: 'Faculty', admin: 'Administrator' }[user.role];

  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;

  sidebar.innerHTML = `
    <div class="sidebar-logo">
      <div class="logo-mark">
        <div class="logo-icon">🎓</div>
        <div>
          <div class="logo-text">Scholario</div>
          <div class="logo-sub">SRMIST · CSE-A · Sem 4</div>
        </div>
      </div>
    </div>
    <div class="sidebar-user">
      <div class="user-avatar">${initials}</div>
      <div class="user-info">
        <div class="user-name">${user.name}</div>
        <div class="user-role">${roleLabel}</div>
      </div>
    </div>
    <nav class="sidebar-nav">
      ${(navs[role] || []).map(n => `
        <a href="${n.href}" class="nav-item ${active === n.label ? 'active' : ''}">
          <span class="nav-icon">${n.icon}</span>
          ${n.label}
          ${n.label === 'Notifications' ? '<span class="nav-badge" id="notif-count" style="display:none">0</span>' : ''}
        </a>
      `).join('')}
    </nav>
    <div class="sidebar-footer">
      <button class="logout-btn" onclick="logout()">
        <span>↩</span> Sign Out
      </button>
    </div>
  `;

  // Load unread notification count
  if (user.user_id) {
    fetch(`${API}/notifications/${user.user_id}/unread-count`)
      .then(r => r.json())
      .then(d => {
        const el = document.getElementById('notif-count');
        if (el && d.count > 0) { el.textContent = d.count; el.style.display = 'inline'; }
      }).catch(() => {});
  }
}