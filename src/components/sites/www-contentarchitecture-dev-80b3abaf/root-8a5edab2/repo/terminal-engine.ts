/**
 * Pure interpreter behind RepoTerminal (no React). It implements the fake shell of the live site:
 * commands, the git commit chart, tree rendering, grep, tab completion, and the plop and
 * `rm -rf /` timelines.
 *
 * `cwd` is repo-relative ("" = repo root) or `null` for the home folder `~`, which sits one
 * level above the repo and contains only the repo folder.
 */

import {
  getNode,
  joinPath,
  resolvePath,
  walkFiles,
  type RepoFileNode,
  type RepoFolderNode,
  type RepoNode,
  type RepoStats,
} from "./model";

export type Cwd = string | null;

/** Shown for a blank output line (the live terminal renders `" "`). */
export const BLANK = " ";

export const HOME_USER = "edo";
export const PLOP_PROMPT = "❯";
export const CONFIRM_PROMPT = "are you sure? [y/N]";
export const CONFIRM_PLACEHOLDER = "y / N";
export const PLOP_QUESTION =
  "? Name (section names will automatically be suffixed with 'Section'. eg. 'cta' -> 'ctaSection')";
export const RM_WARNING = "rm: it is dangerous to operate recursively on '/'";
export const RM_ABORTED = "rm: aborted, the filesystem is intact.";

export const COMMANDS = [
  "help",
  "ls",
  "cd",
  "tree",
  "cat",
  "open",
  "grep",
  "plop",
  "history",
  "pwd",
  "whoami",
  "echo",
  "clear",
  "git",
] as const;

/** `~/<root> >`: the prompt at the repo root (and on the pinned CTA line). */
export function rootPrompt(rootName: string): string {
  return `~/${rootName} >`;
}

/** Prompt for `cwd`: `~ >` in home, `~/<root>/<cwd> >` inside the repo. */
export function promptFor(rootName: string, cwd: Cwd): string {
  if (cwd === null) return "~ >";
  return cwd ? `~/${rootName}/${cwd} >` : rootPrompt(rootName);
}

// ---------------------------------------------------------------------------------------------
// Path resolution (with the virtual home level)

type Target = { kind: "home" } | { kind: "repo"; path: string };

/** The home folder: a virtual folder whose only child is the repo. */
function homeFolder(tree: RepoFolderNode): RepoFolderNode {
  return { type: "folder", name: "", children: [tree] };
}

/**
 * Resolve a shell argument against `cwd`. Inside the repo this is `resolvePath`, except that
 * climbing one level above the root lands in home. From home, `<root>/…` enters the repo.
 * `~` and a leading `/` address the repo root (as in `resolvePath`). null = not found.
 */
function resolveTarget(cwd: Cwd, arg: string, rootName: string): Target | null {
  const trimmed = arg.replace(/\/+$/, "");
  if (trimmed === "~" || trimmed.startsWith("~/") || trimmed.startsWith("/")) {
    const path = resolvePath("", trimmed);
    return path === null ? null : { kind: "repo", path };
  }
  if (cwd !== null) {
    const path = resolvePath(cwd, trimmed);
    if (path !== null) return { kind: "repo", path };
  }
  let segments: string[] | null = cwd === null ? null : cwd.split("/").filter(Boolean);
  for (const segment of trimmed.split("/")) {
    if (segment === "" || segment === ".") continue;
    if (segment === "..") {
      if (segments === null) return null;
      if (segments.length === 0) segments = null;
      else segments.pop();
      continue;
    }
    if (segments === null) {
      if (segment !== rootName) return null;
      segments = [];
      continue;
    }
    segments.push(segment);
  }
  return segments === null ? { kind: "home" } : { kind: "repo", path: segments.join("/") };
}

function nodeAt(tree: RepoFolderNode, target: Target | null): RepoNode | null {
  if (!target) return null;
  return target.kind === "home" ? homeFolder(tree) : getNode(tree, target.path);
}

// ---------------------------------------------------------------------------------------------
// Output builders

/** `git`: header, the 7-row chart of the last 26 weeks, and the legend. */
export function gitLines(repo: RepoStats): string[] {
  return [
    `${repo.branch} · ${repo.updatedLabel} · ${repo.totalCommits} commits`,
    BLANK,
    ...gitChart(repo.weeks),
    BLANK,
    "less ·░▒▓█ more   (last 26 weeks · commit volume, not contents)",
  ];
}

const CHART_ROWS = 7;
const CHART_GLYPHS = "░▒▓█";

export function gitChart(weeks: number[]): string[] {
  const recent = weeks.slice(-26);
  const max = Math.max(0, ...recent);
  const columns = recent.map((v) => {
    if (v <= 0 || max <= 0) return { h: 0, glyph: "·" };
    const ratio = v / max;
    const h = Math.max(1, Math.round(ratio * CHART_ROWS));
    const glyph = CHART_GLYPHS[Math.min(CHART_GLYPHS.length, Math.ceil(ratio * CHART_GLYPHS.length)) - 1];
    return { h, glyph };
  });
  const rows: string[] = [];
  for (let r = 0; r < CHART_ROWS; r++) {
    rows.push(columns.map(({ h, glyph }) => (r >= CHART_ROWS - h ? glyph : "·")).join(""));
  }
  return rows;
}

/** `tree`: box-drawing listing of `folder`, then the directory/file totals (start excluded). */
export function treeLines(folder: RepoFolderNode, header: string): string[] {
  const out = [header];
  let directories = 0;
  let files = 0;
  const walk = (node: RepoFolderNode, prefix: string) => {
    node.children.forEach((child, i) => {
      const last = i === node.children.length - 1;
      const isFolder = child.type === "folder";
      out.push(`${prefix}${last ? "└── " : "├── "}${child.name}${isFolder ? "/" : ""}`);
      if (isFolder) {
        directories++;
        walk(child, prefix + (last ? "    " : "│   "));
      } else {
        files++;
      }
    });
  };
  walk(folder, "");
  out.push(BLANK, `${directories} directories, ${files} files`);
  return out;
}

function grepLines(root: RepoNode, base: string, pattern: string): string[] {
  const needle = pattern.toLowerCase();
  const files =
    root.type === "file" ? [{ path: base || root.name, node: root }] : walkFiles(root, base);
  const out: string[] = [];
  for (const { path, node } of files) {
    node.content.split("\n").forEach((line, i) => {
      if (line.toLowerCase().includes(needle)) out.push(`${path}:${i + 1}: ${line.slice(0, 100)}`);
    });
  }
  return out.length ? out : [`grep: no matches for "${pattern}"`];
}

function isRmRoot(input: string): boolean {
  return /^(sudo\s+)?rm\s+-(rf|fr|Rf|fR)\s+\/\*?$/.test(input);
}

// ---------------------------------------------------------------------------------------------
// Commands

export interface TerminalContext {
  tree: RepoFolderNode;
  repo: RepoStats;
  cwd: Cwd;
  /** Commands submitted before this one (oldest first). */
  history: string[];
}

export interface CommandResult {
  /** Output lines of the entry (not shown when `clear`). */
  lines: string[];
  /** New working directory, when it changes. */
  cwd?: Cwd;
  /** Remove every entry (`clear`). */
  clear?: boolean;
  /** Repo-relative file to open in the editor (`open`). */
  openPath?: string;
  /** Ask a follow-up question: plop's name prompt or the rm confirmation. */
  next?: "plop" | "confirm";
}

/** Run one command line (already trimmed). Pure: side effects are described in the result. */
export function runCommand(input: string, ctx: TerminalContext): CommandResult {
  const { tree, cwd } = ctx;
  if (input === "") return { lines: [] };
  if (isRmRoot(input)) return { lines: [RM_WARNING], next: "confirm" };

  const [cmd, ...args] = input.split(/\s+/);
  const arg = args[0] ?? "";
  const rootName = tree.name;

  switch (cmd) {
    case "help":
      return {
        lines: [`commands: ${COMMANDS.join(", ")}`, "tab completes paths, up/down recalls history"],
      };
    case "pwd":
      return {
        lines: [cwd === null ? `/home/${HOME_USER}` : `/home/${HOME_USER}/${joinPath(rootName, cwd)}`],
      };
    case "whoami":
      return { lines: [HOME_USER] };
    case "echo":
      return { lines: [args.join(" ")] };
    case "clear":
      return { lines: [], clear: true };
    case "history":
      return { lines: ctx.history.map((command, i) => `${String(i + 1).padStart(4)}  ${command}`) };
    case "git":
      return { lines: gitLines(ctx.repo) };
    case "plop":
      return { lines: [PLOP_QUESTION], next: "plop" };

    case "ls": {
      const node = nodeAt(tree, resolveTarget(cwd, arg, rootName));
      if (!node) return { lines: [`ls: ${arg}: No such file or directory`] };
      if (node.type === "file") return { lines: [node.name] };
      return { lines: node.children.map((c) => (c.type === "folder" ? `${c.name}/` : c.name)) };
    }

    case "cd": {
      if (!arg) return { lines: [], cwd: null };
      const target = resolveTarget(cwd, arg, rootName);
      const node = nodeAt(tree, target);
      if (!target || !node) return { lines: [`cd: ${arg}: No such file or directory`] };
      if (node.type === "file") return { lines: [`cd: ${arg}: Not a directory`] };
      return { lines: [], cwd: target.kind === "home" ? null : target.path };
    }

    case "cat": {
      const node = nodeAt(tree, resolveTarget(cwd, arg, rootName));
      if (!node) return { lines: [`cat: ${arg}: No such file or directory`] };
      if (node.type === "folder") return { lines: [`cat: ${arg}: Is a directory`] };
      return { lines: node.content.split("\n") };
    }

    case "open": {
      const target = resolveTarget(cwd, arg, rootName);
      const node = nodeAt(tree, target);
      if (!target || !node) return { lines: [`open: ${arg}: No such file or directory`] };
      if (node.type === "folder" || target.kind === "home") {
        return { lines: [`open: ${arg}: Is a directory`] };
      }
      return { lines: [`opening ${arg}`], openPath: target.path };
    }

    case "tree": {
      const node = nodeAt(tree, resolveTarget(cwd, arg, rootName));
      if (!node) return { lines: [`tree: ${arg}: No such file or directory`] };
      if (node.type === "file") return { lines: [`tree: ${arg}: Not a directory`] };
      return { lines: treeLines(node, arg || ".") };
    }

    case "grep": {
      const pattern = args[0];
      if (!pattern) return { lines: ["usage: grep <pattern> [path]"] };
      const pathArg = args[1] ?? "";
      const node = nodeAt(tree, resolveTarget(cwd, pathArg, rootName));
      if (!node) return { lines: [`grep: ${pathArg}: No such file or directory`] };
      const base = pathArg.replace(/\/+$/, "").replace(/^\.(\/|$)/, "");
      return { lines: grepLines(node, base, pattern) };
    }

    default:
      return { lines: [`command not found: ${cmd}`] };
  }
}

/** `rm -rf /` confirmation: only `y` / `yes` goes ahead. */
export function isConfirmed(answer: string): boolean {
  const a = answer.trim().toLowerCase();
  return a === "y" || a === "yes";
}

// ---------------------------------------------------------------------------------------------
// Tab completion

function commonPrefix(names: string[]): string {
  let prefix = names[0] ?? "";
  for (const name of names) {
    while (!name.startsWith(prefix)) prefix = prefix.slice(0, -1);
  }
  return prefix;
}

/**
 * Complete the last token of `input` against the entries of the folder it points into. A unique
 * match inserts the name plus "/" (folder) or " " (file); several matches insert their common
 * prefix. Returns null when nothing changes.
 */
export function completeInput(input: string, cwd: Cwd, tree: RepoFolderNode): string | null {
  const match = /^([\s\S]*?)(\S*)$/.exec(input);
  if (!match) return null;
  const [, before, token] = match;
  const slash = token.lastIndexOf("/");
  const dirPart = slash >= 0 ? token.slice(0, slash + 1) : "";
  const partial = token.slice(slash + 1);
  const folder = nodeAt(tree, resolveTarget(cwd, dirPart, tree.name));
  if (!folder || folder.type !== "folder") return null;

  const matches = folder.children.filter((child) => child.name.startsWith(partial));
  if (matches.length === 0) return null;
  if (matches.length === 1) {
    const [only] = matches;
    return `${before}${dirPart}${only.name}${only.type === "folder" ? "/" : " "}`;
  }
  const prefix = commonPrefix(matches.map((child) => child.name));
  return prefix.length > partial.length ? `${before}${dirPart}${prefix}` : null;
}

// ---------------------------------------------------------------------------------------------
// Timed sequences

/** One step of a timed sequence, `at` ms after the answer was submitted. */
export interface TimelineStep {
  at: number;
  /** Line appended to the entry. */
  line?: string;
  /** Set (string) or remove (null) the entry's spinner line. */
  spinner?: string | null;
}

export interface PlopPlan {
  /** Lines printed right away under the `❯ name` echo. */
  lines: string[];
  spinner: string;
  steps: TimelineStep[];
  /** When the sequence ends (the file is added and opened). */
  doneAt: number;
  folderPath: string;
  file: RepoFileNode;
  openPath: string;
}

const PLOP_STEP_MS = 130;
const PLOP_TASK_MS = 770;
export const PLOP_FOLDER = "features/page-builder/sections";

export function plopPlan(name: string): PlopPlan {
  const fileName = name ? `${name}-section.tsx` : "section.tsx";
  const writes = [
    `✔  ++ /sanity/schemas/page-sections/${fileName}`,
    "✔  |- /sanity/schemas/page-sections/index.ts",
    "✔  |- /sanity/schemas/page-sections/index.ts",
    `✔  ++ /${PLOP_FOLDER}/${fileName}`,
    "✔  |- /features/page-builder/page-sections.tsx",
    "✔  |- /features/page-builder/page-sections.tsx",
  ];
  const steps: TimelineStep[] = writes.map((line, i) => ({ at: (i + 1) * PLOP_STEP_MS, line }));
  const typesAt = writes.length * PLOP_STEP_MS + PLOP_TASK_MS;
  const formatAt = typesAt + PLOP_TASK_MS;
  steps.push({ at: typesAt, line: "✔  Generate types" }, { at: formatAt, line: "✔  Format code", spinner: null });
  const capitalized = name.charAt(0).toUpperCase() + name.slice(1);
  return {
    lines: ['? Running "Page Builder Section"'],
    spinner: "scaffolding",
    steps,
    doneAt: formatAt,
    folderPath: PLOP_FOLDER,
    file: { type: "file", name: fileName, content: `// ${capitalized} section.\n` },
    openPath: joinPath(PLOP_FOLDER, fileName),
  };
}

/** The `rm -rf /` meltdown after answering `y` (times verified against the live site). */
export const RM_STEPS: TimelineStep[] = [
  { at: 149, line: "removed '/bin/bash'" },
  { at: 228, line: "removed '/bin/ls'" },
  { at: 334, line: "removed '/boot/vmlinuz-6.8.0-edo'" },
  { at: 455, line: "removed '/etc/passwd'" },
  { at: 516, line: "removed '/etc/shadow'" },
  { at: 601, line: "removed '/etc/fstab'" },
  { at: 710, line: "removed '/usr/lib/x86_64-linux-gnu/libc.so.6'" },
  { at: 831, line: "removed '/usr/bin/node'" },
  { at: 896, line: "removed '/usr/bin/git'" },
  { at: 976, line: "removed '/lib/systemd/systemd'" },
  { at: 1083, line: "removed '/var/lib/dpkg/status'" },
  { at: 1202, line: "removed '/var/log/syslog'" },
  { at: 1265, line: "removed '/home/edo/.ssh/id_rsa'" },
  { at: 1359, line: "removed '/home/edo/.bashrc'" },
  { at: 1469, line: "removed '/sbin/init'" },
  { at: 1710, line: "rm: cannot remove '/proc/1/exe': Operation not permitted" },
  { at: 1950, line: "bash: /bin/bash: No such file or directory" },
  { at: 2189, line: "[ 1234.882043] EXT4-fs error (device sda1): ext4_lookup: deleted inode referenced" },
  { at: 2429, line: "[ 1235.014773] systemd[1]: Failed to execute /sbin/init, giving up", spinner: "Syncing filesystem..." },
  {
    at: 4016,
    line: "[ 1235.330012] Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000100",
    spinner: null,
  },
  { at: 4391, line: "[ 1235.330013] ---[ end Kernel panic - not syncing ]---" },
  { at: 5351, line: "System halted. Rebooting..." },
  { at: 5963, line: BLANK },
];

/** When the BIOS crash screen takes over. */
export const RM_CRASH_AT = 6988;
