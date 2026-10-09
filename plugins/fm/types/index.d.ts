export type CalItem = { kind: 'task' | 'event'; title: string; date: string; time: string; status: string; owner: string; owners?: string[]; project: string; activity?: string; priority?: string; research?: string; file: string; started?: string; completed?: string; claimed?: string; updated?: string }

export type VaultTask = { title: string; status: string; due: string; owner: string; owners?: string[]; project?: string; updated?: string; file?: string; started?: string; completed?: string; claimed?: string }

declare module 'claude-code' {
  interface PluginState {
    'fm': { tasks: VaultTask[]; isHidden: boolean; collapsed: boolean; commenting: string; confirming: string; vault: string; feed: string[]; watching: boolean; goals: string[]; health: string; target: string; cal: CalItem[]; calDay: string; calWeek: number; calScope: string; calSel: string; names: string[]; proj: string; calView: string; calDone: boolean; projDir: string; researchHub: { file: string; status: string; open?: number }; busy: { since: number; turn: boolean }; offers: string[]; devices: string[] }
  }
}
