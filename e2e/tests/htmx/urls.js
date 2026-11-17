// Include the mount path: HTMX lives at / in htmx mode and /v2/ in react mode.
export const backend = (process.env.DJANGO_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
export const baseURL = (process.env.HTMX_BASE_URL ||
  `${backend}${process.env.FRONTEND_MODE === 'react' ? '/v2/' : '/'}`).replace(/\/?$/, '/');
export const uiURL = (path = '') => new URL(path, baseURL).href;
export const uiPath = (path = '') => new URL(uiURL(path)).pathname;
