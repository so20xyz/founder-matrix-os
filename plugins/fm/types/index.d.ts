export type CalItem = { kind: 'task' | 'event'; title: string; date: string; time: string; status: string; owner: string; project: string; activity?: string; priority?: string; file: string }

export type VaultTask = { title: string; status: string; due: string; owner: string; project?: string; updated?: string; file?: string }

declare module 'claude-code' {
  interface PluginState {
    'fm': { tasks: VaultTask[]; isHidden: boolean; collapsed: boolean; commenting: string; confirming: string; vault: string; feed: string[]; watching: boolean; goals: string[]; health: string; target: string; cal: CalItem[]; calDay: string; calWeek: number; calScope: string; calSel: string; names: string[] }
  }
}
