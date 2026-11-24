import { createContext, useContext } from 'react'
import type { AppConfig } from './types'

/** Until /api/config answers: no AI, dev sign-in. */
export const fallbackConfig: AppConfig = { ai_enabled: false, auth_mode: 'dev', model: '', loaded: false }
export const ConfigContext = createContext<AppConfig>(fallbackConfig)

export const useConfig = () => useContext(ConfigContext)
