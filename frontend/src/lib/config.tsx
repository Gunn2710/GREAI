import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from './api'
import type { AppConfig } from './types'

const fallback: AppConfig = { ai_enabled: false, auth_mode: 'dev', model: '', loaded: false }
const ConfigContext = createContext<AppConfig>(fallback)

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig>(fallback)
  useEffect(() => {
    api
      .config()
      .then((c) => setConfig({ ...c, loaded: true }))
      .catch(() => setConfig(fallback))
  }, [])
  return <ConfigContext.Provider value={config}>{children}</ConfigContext.Provider>
}

export const useConfig = () => useContext(ConfigContext)
