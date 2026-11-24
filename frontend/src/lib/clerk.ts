/** Clerk sign-in is on when a publishable key is set (see .env). */
export const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined
export const clerkEnabled = Boolean(CLERK_PUBLISHABLE_KEY)
