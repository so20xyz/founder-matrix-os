export type VaultTask = { title: string; status: string; due: string; owner: string; project?: string; updated?: string; file?: string }

declare module 'claude-code' {
  interface PluginState {
    'fm': { tasks: VaultTask[]; isHidden: boolean; collapsed: boolean; commenting: string; confirming: string; vault: string; feed: string[]; watching: boolean; goals: string[]; health: string; target: string }
  }
}
