/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Clerk publishable key (pk_test_... / pk_live_...). Unset = dev mode. */
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
