/**
 * IP-Guard Auth Module
 * 
 * JWT stored in a module-scoped closure variable (not localStorage).
 * Lost on page reload by design — user re-authenticates.
 * This is the conservative choice for a compliance tool.
 */

let _token = null;

/**
 * Decode JWT payload without verification.
 * Server is the trust boundary — this is for UI routing only.
 */
function _decodePayload(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64).split('').map(c =>
        '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
      ).join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

/**
 * Log in with email and password.
 * Returns the decoded JWT payload on success, null on failure.
 */
async function login(email, password) {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });

  if (!res.ok) {
    return null;
  }

  const data = await res.json();
  _token = data.access_token;
  return _decodePayload(_token);
}

/**
 * Fetch wrapper that injects Authorization header.
 * On 401, redirects to login page.
 */
async function apiFetch(url, options = {}) {
  if (!_token) {
    window.location.href = '/app/login.html';
    return;
  }

  const headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + _token,
    ...(options.headers || {})
  };

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    _token = null;
    window.location.href = '/app/login.html';
    return;
  }

  return res;
}

/**
 * Get the current user's role from the stored JWT.
 * Returns null if no token is stored.
 */
function getRole() {
  if (!_token) return null;
  const payload = _decodePayload(_token);
  return payload ? payload.role : null;
}

/**
 * Get the current user's org_id from the stored JWT.
 */
function getOrgId() {
  if (!_token) return null;
  const payload = _decodePayload(_token);
  return payload ? payload.org_id : null;
}

/**
 * Get the current user's user_id from the stored JWT.
 */
function getUserId() {
  if (!_token) return null;
  const payload = _decodePayload(_token);
  return payload ? payload.user_id : null;
}

/**
 * Check if the user has a valid token.
 */
function isAuthenticated() {
  return _token !== null;
}

/**
 * Route guard: require one of the given roles.
 * Redirects to the appropriate page if role doesn't match.
 * This is a UX convenience — real enforcement is server-side.
 */
function requireRole(allowedRoles) {
  if (!_token) {
    window.location.href = '/app/login.html';
    return false;
  }

  const role = getRole();
  if (!allowedRoles.includes(role)) {
    if (role === 'submitter') {
      window.location.href = '/app/submit.html';
    } else {
      window.location.href = '/app/dashboard.html';
    }
    return false;
  }

  return true;
}

/**
 * Clear the stored token (logout).
 */
function logout() {
  _token = null;
  window.location.href = '/app/login.html';
}
