export type VaultTask = { title: string; status: string; due: string; owner: string; project?: string }

declare module 'claude-code' {
  interface PluginState {
    'fm': { tasks: VaultTask[]; isHidden: boolean }
  }
}
