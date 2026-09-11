import ide from "../data/ide.json";
import type { RepoContent } from "../RepoSection";
import type { RepoFolderNode } from "../repo/model";

interface EditionPrice {
  price: string;
  listPrice: string;
}

const prices: Record<string, EditionPrice | undefined> = ide.cta.prices;

/** Muted comment after the pinned `get-access` line, e.g. "€399 · was €549 · one-time". */
function ctaNote(editionId: string): string {
  const price = prices[editionId];
  return price ? `${price.price} · was ${price.listPrice} · one-time` : ide.cta.note;
}

export const repoContent: RepoContent = {
  id: "the-repo",
  title: ide.title,
  terminalTitle: "Terminal",
  terminalHint: ide.terminalHint,
  editions: ide.editions.map((edition) => ({
    id: edition.id,
    label: edition.label,
    ariaLabel: edition.ariaLabel,
    repo: edition.repo,
    tree: edition.tree as unknown as RepoFolderNode,
    cta: { label: ide.cta.label, note: ctaNote(edition.id), href: ide.cta.link.href },
  })),
  labels: {
    hideTerminal: "Hide terminal",
    showTerminal: "Show terminal",
    search: "Search files",
    searchPlaceholder: "Search project files...",
    resizeExplorer: "Resize file explorer",
    resizeTerminal: "Resize terminal",
    resizeBoth: "Resize file explorer and terminal",
    commitGraphTitle: "Show the commit graph",
    commitGraphLabel: "Show the commit graph in the terminal",
    commits: "commits",
  },
};
