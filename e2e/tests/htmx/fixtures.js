import { readFileSync } from 'node:fs';

export const backend = 'http://localhost:8765';
const base = process.env.HTMX_BASE_URL || `${backend}${process.env.FRONTEND_MODE === 'react' ? '/v2/' : '/'}`;
export const uiURL = (path = '') => new URL(path, base.replace(/\/?$/, '/')).href;
export const uiPath = (path = '') => new URL(uiURL(path)).pathname;
export const fixture = () => JSON.parse(readFileSync(new URL('../../test-results/report-parity.json', import.meta.url)));
