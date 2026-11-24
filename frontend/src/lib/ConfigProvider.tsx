import { useEffect, useState, type ReactNode } from 'react'
import { api } from './api'
import { ConfigContext, fallbackConfig } from './config'
import type { AppConfig } from './types'

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig>(fallbackConfig)
  useEffect(() => {
    api
      .config()
      .then((c) => setConfig({ ...c, loaded: true }))
      .catch(() => setConfig(fallbackConfig))
  }, [])
  return <ConfigContext.Provider value={config}>{children}</ConfigContext.Provider>
}
