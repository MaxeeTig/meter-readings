/** Base path for API requests (e.g. '' or '/app1'). Set at build via VITE_APP_API_BASE. */
export const apiBase = (import.meta as unknown as { env: { VITE_APP_API_BASE?: string } }).env
  .VITE_APP_API_BASE ?? '';
