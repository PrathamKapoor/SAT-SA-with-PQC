/**
 * Shared data model for the IDE section ("The repo"). Every Repo* component and the terminal
 * engine work on these types and path helpers.
 *
 * Paths are repo-relative, "/"-joined, without the root folder name: "" is the repo root,
 * "app/(web)/blog" a folder, "README.md" a file. The prompt shows `~/<root.name>/<path>`.
 */

export interface RepoFileNode {
  type: "file";
  name: string;
  content: string;
  /** The file open in the editor when the edition loads (CA: README.md). */
  active?: boolean;
}

export interface RepoFolderNode {
  type: "folder";
  name: string;
  /** Expanded when the edition loads. */
  open?: boolean;
  children: RepoNode[];
}

export type RepoNode = RepoFileNode | RepoFolderNode;

export interface RepoStats {
  branch: string;
  updatedLabel: string;
  isRecent: boolean;
  totalCommits: number;
  /** Weekly commit counts, oldest first (CA: 52 entries; the git chart uses the last 26). */
  weeks: number[];
}

export interface RepoEdition {
  id: string;
  /** Tab label (rendered uppercase). */
  label: string;
  /** aria-label of the tab button, e.g. "Open the Next.js repository". */
  ariaLabel: string;
  repo: RepoStats;
  tree: RepoFolderNode;
}

export interface RepoCta {
  /** Command shown in the pinned terminal line (CA: "get-access"). */
  label: string;
  /** Muted comment after it, e.g. "€399 · was €549 · one-time" (built by the section). */
  note: string;
  href: string;
}

export function joinPath(...parts: string[]): string {
  return parts.filter(Boolean).join("/");
}

export function parentPath(path: string): string {
  const i = path.lastIndexOf("/");
  return i < 0 ? "" : path.slice(0, i);
}

export function baseName(path: string): string {
  const i = path.lastIndexOf("/");
  return i < 0 ? path : path.slice(i + 1);
}

/** Node at `path` ("" = root), or null. */
export function getNode(root: RepoFolderNode, path: string): RepoNode | null {
  if (path === "") return root;
  let node: RepoNode = root;
  for (const segment of path.split("/")) {
    if (node.type !== "folder") return null;
    const next: RepoNode | undefined = node.children.find((child) => child.name === segment);
    if (!next) return null;
    node = next;
  }
  return node;
}

/**
 * Resolve a shell argument against `cwd`. Supports ".", "..", "./x", "~" / "~/x" (repo root) and a
 * trailing "/". Returns null when the result climbs above the repo root.
 */
export function resolvePath(cwd: string, arg: string): string | null {
  const trimmed = arg.replace(/\/+$/, "");
  const fromRoot = trimmed === "~" || trimmed.startsWith("~/") || trimmed.startsWith("/");
  const segments = fromRoot ? [] : cwd.split("/").filter(Boolean);
  const rest = trimmed.replace(/^~\/?/, "").replace(/^\/+/, "");
  for (const segment of rest.split("/")) {
    if (segment === "" || segment === ".") continue;
    if (segment === "..") {
      if (segments.length === 0) return null;
      segments.pop();
      continue;
    }
    segments.push(segment);
  }
  return segments.join("/");
}

/** Every file under `folder`, depth-first in tree order, with repo-relative paths. */
export function walkFiles(folder: RepoFolderNode, base = ""): { path: string; node: RepoFileNode }[] {
  const out: { path: string; node: RepoFileNode }[] = [];
  for (const child of folder.children) {
    const path = joinPath(base, child.name);
    if (child.type === "file") out.push({ path, node: child });
    else out.push(...walkFiles(child, path));
  }
  return out;
}

/** Folder paths flagged `open` in the data (the tree's initial expansion). */
export function defaultOpenPaths(folder: RepoFolderNode, base = ""): Set<string> {
  const out = new Set<string>();
  for (const child of folder.children) {
    if (child.type !== "folder") continue;
    const path = joinPath(base, child.name);
    if (child.open) out.add(path);
    for (const nested of defaultOpenPaths(child, path)) out.add(nested);
  }
  return out;
}

/** Path of the file flagged `active`, falling back to the first root-level file. */
export function defaultActivePath(root: RepoFolderNode): string {
  const active = walkFiles(root).find(({ node }) => node.active);
  if (active) return active.path;
  return root.children.find((child) => child.type === "file")?.name ?? "";
}

/** Immutable insert of a file into `folderPath` (appended; used by `plop`). */
export function addFile(root: RepoFolderNode, folderPath: string, file: RepoFileNode): RepoFolderNode {
  const insert = (folder: RepoFolderNode, segments: string[]): RepoFolderNode => {
    if (segments.length === 0) {
      return { ...folder, children: [...folder.children.filter((c) => c.name !== file.name), file] };
    }
    const [head, ...tail] = segments;
    return {
      ...folder,
      children: folder.children.map((child) =>
        child.type === "folder" && child.name === head ? insert(child, tail) : child,
      ),
    };
  };
  return insert(root, folderPath.split("/").filter(Boolean));
}

export type FileIconKind = "component" | "code" | "json" | "css" | "image" | "config" | "text" | "file";

/** Icon per file, matching the live tree (.tsx → component, .md → text, dotfiles → config …). */
export function fileIconKind(name: string): FileIconKind {
  const lower = name.toLowerCase();
  if (lower.endsWith(".tsx") || lower.endsWith(".jsx")) return "component";
  if (/\.(ts|mts|cts|js|mjs|cjs)$/.test(lower)) return "code";
  if (/\.(json|jsonc|hbs)$/.test(lower)) return "json";
  if (lower.endsWith(".css")) return "css";
  if (/\.(svg|png|jpe?g|gif|webp|avif|ico)$/.test(lower)) return "image";
  if (/\.(ya?ml|toml)$/.test(lower) || /^\.(env[^/]*|gitignore|npmrc|nvmrc)$/.test(lower)) return "config";
  if (/\.(md|mdx|txt)$/.test(lower)) return "text";
  return "file";
}

export type HighlightMode = "markdown" | "slash-comments" | "hash-comments" | "plain";

/** How the editor overlay highlights a file (see RepoEditor). */
export function highlightMode(name: string): HighlightMode {
  const lower = name.toLowerCase();
  if (/\.(md|mdx)$/.test(lower)) return "markdown";
  if (/\.(tsx?|jsx?|mjs|cjs|mts|cts|jsonc?|css|hbs)$/.test(lower)) return "slash-comments";
  if (/\.(ya?ml|toml|sh)$/.test(lower) || /^\.(gitignore|npmrc|nvmrc)$/.test(lower)) return "hash-comments";
  return "plain";
}
