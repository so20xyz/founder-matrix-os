// FMOS dispatcher — Discord ↔ git relay. One per machine.
//  Discord → files : хүний мессежийг relay файлд бичнэ. Зөвхөн WRITER машин бичнэ (legacy: PC) — давхардалгүй.
//  git → Discord : энэ машины сешнүүдийн бичсэн шинэ relay бичлэгийг харгалзах суваг руу нийтэлнэ.
// Run: node dispatcher.mjs   (token: ~/.fmos_discord_token)
// Config (same as fmconfig.py): env FM_VAULT > ~/.fmos/config.json {"vault","device","member"}.
//   vault mode → data in <vault>/_system/fm (registry.json, discord.json, org.md, groups/, s/), NO git (Drive syncs).
//   no config  → legacy <repo>/relay with git pull/commit/push, unchanged.
import { Client, GatewayIntentBits, Partials } from 'discord.js';
import { readFileSync, writeFileSync, existsSync, appendFileSync, mkdirSync, statSync, readdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { homedir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// legacy git mode: the checkout that holds .claude-plugin/marketplace.json (canonical copy: plugins/fm/tools/relay/dispatcher,
// byte-identical copy kept at tools/relay/dispatcher for the running LaunchAgent / scheduled task and its node_modules)
const findRepo = start => { for (let d = start, i = 0; i < 10; i++) { if (existsSync(join(d, '.claude-plugin', 'marketplace.json'))) return d; const up = dirname(d); if (up === d) break; d = up; } return resolve(start, '../../..'); };
const REPO = process.env.FMOS_REPO || findRepo(dirname(fileURLToPath(import.meta.url)));
const readJson = (f, d) => { try { return JSON.parse(readFileSync(f, 'utf8')); } catch { return d; } };
const FMCFG = (c => (c && typeof c === 'object' ? c : {}))(readJson(process.env.FMOS_CONFIG || join(homedir(), '.fmos', 'config.json'), {}));
const VAULT = process.env.FM_VAULT || FMCFG.vault || '';
const VAULT_MODE = !!VAULT;
const RELAY = VAULT_MODE ? join(VAULT.replace(/^~(?=$|[\\/])/, homedir()), '_system', 'fm') : join(REPO, 'relay');
const DEVICE = process.env.FMOS_DEVICE || FMCFG.device || (process.platform === 'darwin' ? 'Mac' : 'PC');
// writer = the ONE machine that writes Discord → files. Legacy: the PC. Vault mode: config "writer" (default true).
const WRITER = (process.env.FMOS_WRITER ?? (VAULT_MODE ? (FMCFG.writer === false ? '0' : '1') : (DEVICE === 'PC' ? '1' : '0'))) === '1';
const TOKEN = readFileSync(join(homedir(), '.fmos_discord_token'), 'utf8').trim();
const CFG = JSON.parse(readFileSync(join(RELAY, 'discord.json'), 'utf8'));
const MEMBER = process.env.FM_MEMBER || FMCFG.member || CFG.member || 'BD'; // label for human Discord messages
// separate read offsets per mode: legacy repo files and vault files share names (org.md, s/<x>.md) but not sizes
const STATE_F = join(homedir(), VAULT_MODE ? '.fmos_dispatch_state.vault.json' : '.fmos_dispatch_state.json');
const GROUPS = ['tasks', 'projects', 'areas', 'resources', 'archive'];
const POLL = 20_000;

const fileFor = ch => ch === 'org' ? 'org.md' : GROUPS.includes(ch) ? `groups/${ch}.md` : null;
const chanFor = rel => rel === 'org.md' ? 'org' : rel.startsWith('groups/') ? rel.slice(7, -3) : null;
const git = (...a) => { if (VAULT_MODE) return ''; try { return execFileSync('git', ['-C', REPO, ...a], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }); } catch (e) { return (e.stdout || '') + (e.stderr || ''); } };
const load = (f, d) => { try { return JSON.parse(readFileSync(f, 'utf8')); } catch { return d; } };
const state = load(STATE_F, {});
const saveState = () => writeFileSync(STATE_F, JSON.stringify(state));
const ts = () => new Date().toLocaleString('sv-SE', { hour12: false }).slice(0, 16);
const log = (...a) => console.log(ts(), ...a);

const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent], partials: [Partials.Channel] });
const channels = {};

// ── Discord → git
client.on('messageCreate', async m => {
  if (!WRITER || m.guildId !== CFG.guild.id || m.author.bot) return;
  const rel = fileFor(m.channel.name);
  if (!rel || !m.content.trim()) return;
  git('pull', '-q', '--rebase', '--autostash');
  const p = join(RELAY, rel);
  if (existsSync(p) && readFileSync(p, 'utf8').includes(`d:${m.id}`)) return;
  mkdirSync(dirname(p), { recursive: true });
  const [first, ...rest] = m.content.split('\n');
  appendFileSync(p, `\n## ${ts()} · ${MEMBER} (Discord) → ${m.channel.name === 'org' ? 'all' : '@' + m.channel.name} · ${first.slice(0, 80)}\n${rest.join('\n') || first}\n<!-- d:${m.id} -->\n`);
  state[rel] = statSync(p).size; saveState(); // don't echo it back
  git('add', p); git('commit', '-qm', `relay ${MEMBER} (Discord) → ${m.channel.name}`);
  const out = git('push', '-q');
  await m.react(out.includes('error') || out.includes('rejected') ? '⚠️' : '📥').catch(() => {});
  log('discord→git', m.channel.name, m.id);
});

// ── git → Discord
async function pump() {
  git('pull', '-q', '--rebase', '--autostash');
  const reg = load(join(RELAY, 'registry.json'), { sessions: {} }).sessions;
  const groupOf = name => Object.values(reg).find(s => s.name === name)?.group;
  const files = ['org.md', ...GROUPS.map(g => `groups/${g}.md`), ...listS()];
  for (const rel of files) {
    const p = join(RELAY, rel); if (!existsSync(p)) continue;
    const buf = readFileSync(p); const off = state[rel];
    if (off === undefined) { state[rel] = buf.length; continue; } // first sight: no replay
    if (buf.length <= off) continue;
    state[rel] = buf.length;
    const blocks = ('\n' + buf.subarray(off).toString('utf8')).split('\n## ').slice(1);
    for (const b of blocks) {
      if (b.includes('<!-- d:') || !b.split('\n')[0].includes(`(${DEVICE})`)) continue; // only this machine's sessions
      let ch = chanFor(rel);
      if (!ch && rel.startsWith('s/')) ch = groupOf(rel.slice(2, -3)) || 'org';
      const c = channels[ch]; if (!c) continue;
      const [head, ...body] = b.split('\n');
      const text = `**${head.trim()}**\n${body.join('\n').trim()}`;
      for (let i = 0; i < text.length; i += 1900) await c.send(text.slice(i, i + 1900)).catch(e => log('send fail', e.message));
      log('git→discord', ch, head.slice(0, 60));
    }
  }
  saveState();
}
function listS() {
  if (VAULT_MODE) { try { return readdirSync(join(RELAY, 's')).filter(f => f.endsWith('.md')).map(f => `s/${f}`); } catch { return []; } }
  try { return execFileSync('git', ['-C', REPO, 'ls-files', 'relay/s'], { encoding: 'utf8' }).split('\n').filter(Boolean).map(f => f.slice(6)); } catch { return []; }
}

client.once('clientReady', async () => {
  const g = await client.guilds.fetch(CFG.guild.id);
  for (const [, c] of await g.channels.fetch()) if (c?.isTextBased?.()) channels[c.name] = c;
  log(`online as ${client.user.tag} · ${DEVICE} · writer=${WRITER} · ${VAULT_MODE ? 'vault ' + RELAY : 'git ' + RELAY} · channels: ${Object.keys(channels).join(', ')}`);
  await pump();
  channels.org?.send(`🟢 ${DEVICE} dispatcher online (${client.user.username})`).catch(() => {});
  setInterval(() => pump().catch(e => log('pump', e.message)), POLL);
});
client.login(TOKEN);
