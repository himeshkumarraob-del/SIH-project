/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Optional absolute base URL of the FastAPI backend, e.g.
   * `https://thermalwatch-api.example.com/api/v1`.
   *
   * When unset, the app calls same-origin `/api/v1` and relies on the
   * hosting platform to reverse-proxy `/api` (Vercel: vercel.json rewrite).
   */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
