export const environment = {
  production: true,
  // Backend base URL. For the two-service Render deploy, set this to the
  // backend service URL at build time. CORS is open on the backend (no auth
  // in the MVP), so a cross-origin call is fine.
  apiUrl: 'https://sico-pandas-lab-backend.onrender.com',
};
