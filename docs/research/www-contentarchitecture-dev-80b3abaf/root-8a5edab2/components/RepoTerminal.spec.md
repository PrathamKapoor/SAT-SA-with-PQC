# RepoTerminal Specification (B7c)

## Overview
- **Target files** (under `…/root-8a5edab2/repo/`):
  - `terminal-engine.ts`: a pure shell interpreter with no React, which is unit-testable
  - `RepoTerminal.tsx`: replace the foreman stub and keep its props interface **exactly**
  - `CrashScreen.tsx`: the BIOS easter-egg overlay
- **Screenshots:** `05-repo-1440.jpeg` (bottom pane) and `40-crash-screen-1440.jpeg`.
- **Interaction model:** keyboard-driven fake shell, with time-driven output for plop and `rm -rf /`.

## Props contract (in the stub; do not change)
```ts
export interface RepoTerminalProps {
  edition: RepoEdition;           // root name + repo stats (git chart)
  tree: RepoFolderNode;           // CURRENT tree (includes files added by plop)
  cta: RepoCta;                   // pinned line: label, note, href
  placeholder: string;            // CA "try: git, ls, tree, plop, cat README.md"
  title: string;                  // header "Terminal"
  request?: { id: number; command: string };  // run this command when `id` changes (footer "commits" button → "git")
  onOpenFile: (path: string) => void;          // `open`, and after plop
  onAddFile: (folderPath: string, file: RepoFileNode) => void; // plop
}
```
The parent remounts the terminal (`key={edition.id}`) on an edition switch, which resets the session.

## DOM (exact live classes)
```
<section aria-label="Terminal" class="flex h-full min-h-0 flex-col">
  <div class="shrink-0 border-white/10 border-b px-16 py-8 font-mono text-caption-10 text-white/40 uppercase tracking-wide">{title}</div>
  <div class="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-16 py-10 font-mono text-caption-10 leading-relaxed" data-lenis-prevent>
    …entries…
    <a aria-label="{cta.label}: get access" class="group block whitespace-pre-wrap break-words text-white/80 no-underline" href={cta.href}>
      <span class="select-none text-white/40">{ROOT_PROMPT} </span><span class="text-[#d6a878] group-hover:underline">{cta.label}</span><span class="select-none text-white/40">   # {cta.note}</span></a>
    <form class="flex items-center text-white/80"><span class="select-none text-white/40">{prompt}&nbsp;</span>
      <input type="text" aria-label="Terminal input" spellcheck="false" autocapitalize="off" autocorrect="off" autocomplete="off" placeholder={phase==="idle" && no entries yet ? placeholder : phase==="confirm" ? "y / N" : undefined}
        class="min-w-0 flex-1 bg-transparent font-mono text-caption-10 caret-current outline-none ring-0 placeholder:text-white/25 focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0"/></form>
```
- **Entry:** `<div class="whitespace-pre-wrap break-words">` containing:
  - the echo line `<div class="text-white/80"><span class="select-none text-white/40">{promptAtRun} </span>{input}</div>`
  - one `<div class="text-white/50">` per output line (an empty line renders as `" "`)
- **Spinner line** (while plop or rm is "working"): `<div class="flex items-center gap-8 text-white/50"><span aria-hidden="true" class="size-12 shrink-0 animate-spin rounded-full border border-white/20 border-t-white/70 motion-reduce:animate-none"/><span>{text}</span></div>`
- **Prompt:** `ROOT_PROMPT = "~/" + edition.tree.name + " >"`. The current prompt appends `"/" + cwd` when cwd is non-empty, and reads `"~ >"` in home. The pinned CTA line always uses ROOT_PROMPT.
- After every change, auto-scroll the body to the bottom. Clicking the body (without a text selection) focuses the input. Hide the form while a timed sequence runs.

## Engine semantics (`cwd`: `string | null`, where null = home `~`, "" = repo root; use `resolvePath`, `getNode`, `walkFiles` from `./model`)
- **help** →
  - `commands: help, ls, cd, tree, cat, open, grep, plop, history, pwd, whoami, echo, clear, git`
  - `tab completes paths, up/down recalls history`
- **pwd** → `/home/edo/{root}` + (`/cwd` if set). In home: `/home/edo`.
- **whoami** → `edo`
- **echo** → echoes the args joined by spaces (`echo` alone prints an empty line).
- **clear** → removes all entries; the pinned CTA line stays.
- **ls [p]:**
  - lists the folder's children in data order, folders suffixed with `/`, one per line
  - on a file, prints its name
  - when missing: `ls: {p}: No such file or directory` (so `ls -la` also prints that)
  - in home: `{root}/`
- **cd [p]:**
  - no arg → home
  - `..` at the repo root → home
  - in home, `cd {root}` → root
  - errors: `cd: {p}: No such file or directory` and `cd: {p}: Not a directory`
  - prints nothing on success
- **cat [p]:**
  - prints the file content split on `\n` (keeping the trailing empty line)
  - errors: `cat: {p}: Is a directory` (no arg → `cat: : Is a directory`) and `cat: {p}: No such file or directory`
- **open p:**
  - prints `opening {p}`, then calls `onOpenFile(path)`
  - errors: `open: {p}: Is a directory` and `open: {p}: No such file or directory`
- **tree [p]:**
  - header `.` (or `p` as typed), then box-drawing lines using `├── `, `└── `, `│   ` and 4 spaces; folders get `/`
  - then `" "` and `{D} directories, {F} files`, where the counts exclude the start folder
  - Next.js root totals: `94 directories, 373 files`
- **grep [pattern] [path]:**
  - no pattern → `usage: grep <pattern> [path]`
  - otherwise a case-insensitive substring search over every line of every file under the path (default cwd), printing `{relPath}:{lineNo}: {line.slice(0, 100)}`
  - no hits → `grep: no matches for "{pattern}"`
- **history** → every submitted command this session (not prompt answers), formatted `String(i).padStart(4) + "  " + cmd`
- **git** (and `git …` with any args):
  - `{branch} · {updatedLabel} · {totalCommits} commits`, then `" "`, then 7 chart rows, then `" "`, then `less ·░▒▓█ more   (last 26 weeks · commit volume, not contents)`
  - **Chart** (verified against the live output): take `weeks.slice(-26)` and `max = Math.max(...)`. For each week v:
    - `h = v === 0 ? 0 : Math.max(1, Math.round(v / max * 7))`
    - `glyph = "░▒▓█"[Math.ceil(v / max * 4) - 1]`
    - Row r (0 = top … 6 = bottom) shows `glyph` if `r >= 7 - h`, else `·`.
  - Expected Next.js output (exact, all 7 rows):
    ```
    ·············█············
    ·············█············
    ·············█········█···
    ·············█·▒▒▒·▓··█··▓
    ············▒█▒▒▒▒·▓▒▒█▒▒▓
    ············▒█▒▒▒▒·▓▒▒█▒▒▓
    ···········░▒█▒▒▒▒░▓▒▒█▒▒▓
    ```
- **plop:**
  1. Prints `? Name (section names will automatically be suffixed with 'Section'. eg. 'cta' -> 'ctaSection')`, and the prompt becomes `❯`.
  2. The answer entry echoes `❯ {name}`, then prints `? Running "Page Builder Section"` plus a spinner line "scaffolding".
  3. Then, each ~130ms apart (let `f = name ? name + "-section.tsx" : "section.tsx"`):
     - `✔  ++ /sanity/schemas/page-sections/{f}`
     - `✔  |- /sanity/schemas/page-sections/index.ts` (×2)
     - `✔  ++ /features/page-builder/sections/{f}`
     - `✔  |- /features/page-builder/page-sections.tsx` (×2)
  4. Then `✔  Generate types` (+770ms) and `✔  Format code` (+770ms). Remove the spinner.
  5. Call `onAddFile("features/page-builder/sections", { type: "file", name: f, content: "// " + Capitalized(name) + " section.\n" })`, then `onOpenFile(...)`.
- **rm -rf /** (also `sudo rm -rf /`):
  1. Prints `rm: it is dangerous to operate recursively on '/'`. The prompt becomes `are you sure? [y/N]` with placeholder `y / N`.
  2. Any answer except `y`/`yes` → `rm: aborted, the filesystem is intact.`
  3. On `y`, the entry `are you sure? [y/N] y` prints these lines at the given ms after the answer:
     - 149 removed '/bin/bash'
     - 228 removed '/bin/ls'
     - 334 removed '/boot/vmlinuz-6.8.0-edo'
     - 455 removed '/etc/passwd'
     - 516 removed '/etc/shadow'
     - 601 removed '/etc/fstab'
     - 710 removed '/usr/lib/x86_64-linux-gnu/libc.so.6'
     - 831 removed '/usr/bin/node'
     - 896 removed '/usr/bin/git'
     - 976 removed '/lib/systemd/systemd'
     - 1083 removed '/var/lib/dpkg/status'
     - 1202 removed '/var/log/syslog'
     - 1265 removed '/home/edo/.ssh/id_rsa'
     - 1359 removed '/home/edo/.bashrc'
     - 1469 removed '/sbin/init'
     - 1710 rm: cannot remove '/proc/1/exe': Operation not permitted
     - 1950 bash: /bin/bash: No such file or directory
     - 2189 [ 1234.882043] EXT4-fs error (device sda1): ext4_lookup: deleted inode referenced
     - 2429 [ 1235.014773] systemd[1]: Failed to execute /sbin/init, giving up
     - 2429 spinner "Syncing filesystem..." (removed at 4016)
     - 4016 [ 1235.330012] Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000100
     - 4391 [ 1235.330013] ---[ end Kernel panic - not syncing ]---
     - 5351 System halted. Rebooting...
     - 5963 (blank line)
     - 6988 → show `<CrashScreen />`
- **Unknown** → `command not found: {cmd}`
- **Empty** → an entry with just the echo line.
- **Keys:**
  - ArrowUp/ArrowDown walk the history (clamped at the oldest; Down past the newest clears the input).
  - Tab completes the last token against the resolved folder's entries. A unique match inserts the name plus `/` (folder) or a space (file); a common prefix inserts the prefix. Always preventDefault.
- **request:** when `request.id` changes, run `request.command` as if typed (echo included).

## CrashScreen (portal to body, fade in via opacity)
Copy verbatim:
```
<div role="alert" aria-label="System BIOS (easter egg). No real files were touched. Press any key to reboot the page." class="fixed inset-0 z-10000 flex flex-col bg-[#0000a8] font-mono text-[#c6c6c6] text-caption-10 selection:bg-[#d4d4d4] selection:text-[#0000a8] cursor-pointer">
 <div aria-hidden="true" class="pointer-events-none absolute inset-0" style="opacity:.06;background-image:repeating-linear-gradient(rgb(255,255,255) 0px,rgb(255,255,255) 1px,transparent 1px,transparent 3px)"/>
 <div class="relative flex shrink-0 items-center justify-between gap-12 bg-[#a8a8a8] px-16 py-4 font-semibold text-[#000080]"><span>AMIBIOS(C)2024 American Megatrends, Inc.</span><span class="hidden sm:inline">v1.0.B3</span></div>
 <div class="relative flex min-h-0 flex-1 flex-col overflow-auto px-16 py-16 sm:px-40 sm:py-24"><div class="wrap-break-word whitespace-pre-wrap">
  lines (div each; " " = blank):
   BIOS Date: 04/01/2024  22:09:51  Ver: 1.0.B3
   The Content Architecture Web Core(tm) CPU @ 3.40GHz [text-white]
   Speed: 3400 MHz
   " "
   Press DEL to run Setup,  F11 for Boot Menu [text-[#54fcfc]]
   Initializing USB Controllers ..  Done. [text-[#54fcfc]]
   65536MB OK [text-white]
   " "
   Auto-Detecting SATA drives ...
   "  SATA Port0 : None" … Port3
   " "
   Reboot and Select proper Boot device
   or Insert Boot Media in selected Boot device and press a key
 </div></div>
 <div class="relative flex shrink-0 items-center justify-between gap-12 bg-[#a8a8a8] px-16 py-4 text-[#000080]"><span class="flex items-center gap-8 font-semibold"><span>Press any key to reboot</span><span aria-hidden="true" class="inline-block h-14 w-8 align-middle bg-[#000080] animate-cursor-blink"/></span><span class="hidden font-semibold sm:inline">F1: Setup &nbsp; ESC: Boot Menu</span></div>
</div>
```
- Any keydown or pointerdown → `window.location.reload()`.
- While it is shown, lock scroll: `lenis.stop()` via `useLenis` from `lenis/react`.

## Verify
`npx tsc --noEmit` and `npx eslint` on the three files must pass. Sanity-check the engine in node (e.g. `npx tsx -e` or a throwaway script, not committed): `git` must reproduce the chart above for weeks `[…26 zeros…,0,0,0,0,0,0,0,0,0,0,0,2,10,22,8,11,11,11,4,13,9,10,17,9,10,14]`.
