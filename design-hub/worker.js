// Identity-based auth — password maps to a display name
const IDENTITIES = {
  'jackie2026': 'Jackie',
  'michele2026': 'Michele',
  'gabriel2026': 'Gabriel',
  'nex2026': 'Nex',
};

const COOKIE_NAME = '__ldb_auth';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

const LOGIN_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Little Dot Book — Design Review Portal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet" />
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --primary: #FF6B6B;
      --secondary: #4ECDC4;
      --accent: #FFE66D;
      --dark: #2C3E50;
      --light: #F7F7F7;
    }

    body {
      font-family: 'Nunito', sans-serif;
      background: var(--light);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      background-image:
        radial-gradient(circle at 20% 20%, rgba(255, 107, 107, 0.12) 0%, transparent 50%),
        radial-gradient(circle at 80% 80%, rgba(78, 205, 196, 0.12) 0%, transparent 50%),
        radial-gradient(circle at 50% 50%, rgba(255, 230, 109, 0.08) 0%, transparent 60%);
    }

    .card {
      background: #fff;
      border-radius: 24px;
      padding: 48px 40px;
      width: 100%;
      max-width: 420px;
      box-shadow:
        0 4px 6px rgba(0,0,0,0.04),
        0 20px 40px rgba(0,0,0,0.08);
      text-align: center;
    }

    .dot-row {
      display: flex;
      justify-content: center;
      gap: 8px;
      margin-bottom: 24px;
    }

    .dot {
      width: 14px;
      height: 14px;
      border-radius: 50%;
    }
    .dot-1 { background: var(--primary); }
    .dot-2 { background: var(--accent); }
    .dot-3 { background: var(--secondary); }

    h1 {
      font-size: 2rem;
      font-weight: 900;
      color: var(--dark);
      letter-spacing: -0.5px;
      line-height: 1.1;
    }

    h1 span {
      color: var(--primary);
    }

    .subtitle {
      font-size: 0.9rem;
      font-weight: 700;
      color: var(--secondary);
      letter-spacing: 1.5px;
      text-transform: uppercase;
      margin-top: 6px;
      margin-bottom: 32px;
    }

    .divider {
      width: 48px;
      height: 4px;
      border-radius: 2px;
      background: linear-gradient(90deg, var(--primary), var(--secondary));
      margin: 0 auto 32px;
    }

    label {
      display: block;
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--dark);
      text-align: left;
      margin-bottom: 8px;
      letter-spacing: 0.5px;
    }

    input[type="password"] {
      width: 100%;
      padding: 14px 18px;
      border: 2px solid #e8e8e8;
      border-radius: 12px;
      font-family: 'Nunito', sans-serif;
      font-size: 1rem;
      font-weight: 600;
      color: var(--dark);
      background: var(--light);
      transition: border-color 0.2s, box-shadow 0.2s;
      outline: none;
      letter-spacing: 2px;
    }

    input[type="password"]:focus {
      border-color: var(--secondary);
      box-shadow: 0 0 0 4px rgba(78, 205, 196, 0.15);
      background: #fff;
    }

    button {
      width: 100%;
      margin-top: 16px;
      padding: 15px;
      background: linear-gradient(135deg, var(--primary), #ff8e8e);
      color: #fff;
      border: none;
      border-radius: 12px;
      font-family: 'Nunito', sans-serif;
      font-size: 1rem;
      font-weight: 800;
      cursor: pointer;
      transition: transform 0.15s, box-shadow 0.15s;
      box-shadow: 0 4px 12px rgba(255, 107, 107, 0.35);
      letter-spacing: 0.5px;
    }

    button:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 18px rgba(255, 107, 107, 0.45);
    }

    button:active {
      transform: translateY(0);
    }

    .error-msg {
      margin-top: 14px;
      padding: 10px 16px;
      background: rgba(255, 107, 107, 0.1);
      border: 1.5px solid rgba(255, 107, 107, 0.3);
      border-radius: 10px;
      color: var(--primary);
      font-size: 0.875rem;
      font-weight: 700;
    }

    .footer-note {
      margin-top: 28px;
      font-size: 0.78rem;
      color: #aaa;
      font-weight: 600;
    }

    @media (max-width: 480px) {
      .card {
        padding: 36px 24px;
      }
      h1 { font-size: 1.75rem; }
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="dot-row">
      <div class="dot dot-1"></div>
      <div class="dot dot-2"></div>
      <div class="dot dot-3"></div>
    </div>
    <h1>Little <span>Dot</span> Book</h1>
    <p class="subtitle">Design Review Portal</p>
    <div class="divider"></div>

    <form method="POST">
      <label for="pw">Enter your password</label>
      <input
        type="password"
        id="pw"
        name="password"
        placeholder="••••••••••••"
        autocomplete="current-password"
        required
        autofocus
      />
      <button type="submit">Enter &rarr;</button>
      ERROR_PLACEHOLDER
    </form>

    <p class="footer-note">Little Dot Book &mdash; Design Review Portal</p>
  </div>
</body>
</html>`;

// ---- Helpers ----

function getCookie(request, name) {
  const cookieHeader = request.headers.get('Cookie') || '';
  const cookies = cookieHeader.split(';').map(c => c.trim());
  for (const cookie of cookies) {
    const [key, ...val] = cookie.split('=');
    if (key.trim() === name) return val.join('=').trim();
  }
  return null;
}

function getIdentity(request) {
  // Cookie stores the identity name directly (e.g. "Jackie", "Michele", "Gabriel")
  const identity = getCookie(request, COOKIE_NAME);
  const validIdentities = Object.values(IDENTITIES);
  if (identity && validIdentities.includes(identity)) return identity;
  return null;
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json;charset=UTF-8' },
  });
}

function unauthorized() {
  return jsonResponse({ error: 'Unauthorized' }, 401);
}

function forbidden() {
  return jsonResponse({ error: 'Forbidden' }, 403);
}

function buildLoginPage(showError = false) {
  const errorHtml = showError
    ? `<div class="error-msg">Oops! Wrong password. Try again.</div>`
    : '';
  const html = LOGIN_HTML.replace('ERROR_PLACEHOLDER', errorHtml);
  return new Response(html, {
    status: showError ? 401 : 200,
    headers: { 'Content-Type': 'text/html;charset=UTF-8' },
  });
}

// ---- API Handlers ----

async function handleGetMe(identity) {
  return jsonResponse({ name: identity });
}

async function handleGetComments(request, env) {
  const url = new URL(request.url);
  const iconId = url.searchParams.get('icon_id');
  if (!iconId) {
    return jsonResponse({ error: 'Missing icon_id query parameter' }, 400);
  }

  const result = await env.DB.prepare(
    `SELECT id, icon_id, author, message, created_at
     FROM comments
     WHERE icon_id = ? AND deleted = 0
     ORDER BY created_at ASC`
  ).bind(iconId).all();

  return jsonResponse({ comments: result.results || [] });
}

async function handlePostComment(request, env, identity) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: 'Invalid JSON body' }, 400);
  }

  const { icon_id, message } = body || {};
  if (!icon_id || !message) {
    return jsonResponse({ error: 'Missing icon_id or message' }, 400);
  }

  const createdAt = new Date().toISOString();

  const insertResult = await env.DB.prepare(
    `INSERT INTO comments (icon_id, author, message, created_at, deleted)
     VALUES (?, ?, ?, ?, 0)`
  ).bind(icon_id, identity, message, createdAt).run();

  const commentId = insertResult.meta?.last_row_id ?? insertResult.lastRowId;

  await env.DB.prepare(
    `INSERT INTO audit_log (author, action, comment_id, message_text, timestamp)
     VALUES (?, 'add', ?, ?, ?)`
  ).bind(identity, commentId, message, createdAt).run();

  const comment = {
    id: commentId,
    icon_id,
    author: identity,
    message,
    created_at: createdAt,
  };

  return jsonResponse({ ok: true, comment }, 201);
}

async function handleDeleteComment(request, env, identity, commentId) {
  // Fetch the comment first
  const row = await env.DB.prepare(
    `SELECT id, author, message FROM comments WHERE id = ? AND deleted = 0`
  ).bind(commentId).first();

  if (!row) {
    return jsonResponse({ error: 'Comment not found' }, 404);
  }

  // Only the author, Gabriel, or Nex can delete
  if (identity !== 'Gabriel' && identity !== 'Nex' && identity !== row.author) {
    return forbidden();
  }

  const deletedAt = new Date().toISOString();

  await env.DB.prepare(
    `UPDATE comments SET deleted = 1 WHERE id = ?`
  ).bind(commentId).run();

  await env.DB.prepare(
    `INSERT INTO audit_log (author, action, comment_id, message_text, timestamp)
     VALUES (?, 'delete', ?, ?, ?)`
  ).bind(identity, commentId, row.message, deletedAt).run();

  return jsonResponse({ ok: true });
}

async function handleGetAudit(env, identity) {
  if (identity !== 'Gabriel' && identity !== 'Nex') {
    return forbidden();
  }

  const result = await env.DB.prepare(
    `SELECT id, author, action, comment_id, message_text, timestamp
     FROM audit_log
     ORDER BY timestamp DESC`
  ).all();

  return jsonResponse({ log: result.results || [] });
}

// ---- Main Fetch Handler ----

export default {
  async fetch(request, env) {
   try {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();
    const pathname = url.pathname;

    // ---- POST / → Login form submission ----
    if (method === 'POST' && pathname === '/') {
      let password = '';
      try {
        const formData = await request.formData();
        password = formData.get('password') || '';
      } catch {
        return buildLoginPage(true);
      }

      // Normalize: trim + lowercase for lookup
      const identity = IDENTITIES[password.trim().toLowerCase()];

      if (identity) {
        // Store the identity name (e.g. "Jackie") in the cookie
        const cookieValue = `${COOKIE_NAME}=${identity}; HttpOnly; SameSite=Lax; Path=/; Max-Age=${COOKIE_MAX_AGE}`;
        return new Response(null, {
          status: 302,
          headers: {
            'Location': '/hub.html',
            'Set-Cookie': cookieValue,
          },
        });
      }

      return buildLoginPage(true);
    }

    // ---- All /api/* routes require authentication ----
    if (pathname.startsWith('/api/')) {
      const identity = getIdentity(request);
      if (!identity) return unauthorized();

      // GET /api/me
      if (method === 'GET' && pathname === '/api/me') {
        return handleGetMe(identity);
      }

      // GET /api/comments?icon_id=XX
      if (method === 'GET' && pathname === '/api/comments') {
        return handleGetComments(request, env);
      }

      // POST /api/comments
      if (method === 'POST' && pathname === '/api/comments') {
        return handlePostComment(request, env, identity);
      }

      // DELETE /api/comments/:id
      const deleteMatch = pathname.match(/^\/api\/comments\/(\d+)$/);
      if (method === 'DELETE' && deleteMatch) {
        const commentId = parseInt(deleteMatch[1], 10);
        return handleDeleteComment(request, env, identity, commentId);
      }

      // GET /api/audit (Gabriel only)
      if (method === 'GET' && pathname === '/api/audit') {
        return handleGetAudit(env, identity);
      }

      // No matching API route
      return jsonResponse({ error: 'Not found' }, 404);
    }

    // ---- GET /logout → Clear cookie and redirect to login ----
    if (method === 'GET' && pathname === '/logout') {
      return new Response(null, {
        status: 302,
        headers: {
          'Location': '/',
          'Set-Cookie': `${COOKIE_NAME}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0`,
        },
      });
    }

    // ---- GET /* → Static assets (requires auth) ----
    const identity = getIdentity(request);

    if (identity) {
      return env.ASSETS.fetch(request);
    }

    // Not authenticated — show login page
    return buildLoginPage(false);
   } catch (err) {
    // Catch-all: never throw 1101 — show login page as fallback
    return buildLoginPage(false);
   }
  },
};
