/** `private` = a 🔒 task / event (private: true, a private owner, a finances/ path): listed only in a private session. */
export type CalItem = { kind: 'task' | 'event'; title: string; date: string; time: string; status: string; owner: string; owners?: string[]; project: string; activity?: string; priority?: string; research?: string; file: string; started?: string; completed?: string; claimed?: string; updated?: string; log?: Array<{ at: string; what: string }>; private?: boolean }

export type VaultTask = { title: string; status: string; due: string; owner: string; owners?: string[]; project?: string; updated?: string; file?: string; started?: string; completed?: string; claimed?: string; private?: boolean }

export type RoleInfo = { slug: string; label: string; agent: string; skills: string[]; note: string; channel: string; private: boolean }

export type ToolStatus = { state: 'ok' | 'off' | 'checking' | 'error'; credits?: number; at: number }

export type ProjMeta = { name: string; file: string; stage: string; desc: string; due: string; links: { name: string; url: string }[]; lastMsg: Record<string, string> }

export type InboxItem = { file: string; title: string; text: string; day: string; hm: string; src: string; kind: string; route: string; agent?: string; project?: string; due?: string; url?: string; status: string; routed?: string; routedTo?: string; masked?: boolean }

/** One item of Claude's own task list (TaskCreated / TaskCompleted); `at` = local-shifted ms when it was created. */
export type PlanStep = { id: string; subject: string; done: boolean; at: number }

/** In-flight background work as the last main-loop Stop reported it (background_tasks). */
export type BgTask = { id: string; type: string; status: string; description: string }

/** A ⚡ Skill quick-run pin: a catalog note (03-Areas/AI Team/skills/catalog) with `pane: true`; `id` = the note's name, `roles` lowercased ('all' = every role). */
export type SkillPin = { id: string; file: string; command: string; icon: string; label: string; description: string; when: string; roles: string[]; order: number }

declare module 'claude-code' {
  interface PluginState {
    'fm': { tasks: VaultTask[]; isHidden: boolean; collapsed: boolean; commenting: string; confirming: string; vault: string; feed: string[]; watching: boolean; goals: string[]; health: string; target: string; cal: CalItem[]; calDay: string; calWeek: number; scopePick: string; scopeMenu: boolean; calSel: string; names: string[]; proj: string; projDir: string; researchHub: { file: string; status: string; open?: number }; busy: { since: number; turn: boolean }; offers: string[]; devices: string[]; tsagTab: string; phaseOpen: Record<string, boolean>; tick: number; kanbanCol: string; newTaskCol: string; role: string; roles: RoleInfo[]; toolsRole: string; toolOpen: string; toolStatus: Record<string, ToolStatus>; projPick: string; projMeta: ProjMeta; projMenu: boolean; inbox: InboxItem[]; inboxBusy: Record<string, string>; reviewAt: string; planSteps: PlanStep[]; bgTasks: BgTask[]; planFile: { file: string; at: number }; projList: string[]; toolUsed: Record<string, number>; privSession: boolean; secretKeys: string[]; skills: SkillPin[]; skillSel: string }
  }
}
