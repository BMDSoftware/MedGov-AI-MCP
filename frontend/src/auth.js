const TOKEN_KEY = 'auth_token';
const USERNAME_KEY = 'auth_username';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const getUsername = () => localStorage.getItem(USERNAME_KEY);
export const setAuth = (token, username) => {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USERNAME_KEY, username);
};
export const clearAuth = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USERNAME_KEY);
};
export const isAuthenticated = () => !!getToken();

export const authHeaders = () => {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
};
