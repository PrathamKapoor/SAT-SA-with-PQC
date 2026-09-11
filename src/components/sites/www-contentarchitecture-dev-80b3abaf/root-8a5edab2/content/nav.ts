import type { SiteNavContent } from "../SiteNav";

/** CA header nav, verbatim from `dom/00-header.html` (hrefs rewritten to in-page anchors). */
export const navContent: SiteNavContent = {
  navLabel: "Primary",
  homeHref: "/reference/contentarchitecture",
  logoLabel: "Home",
  links: [
    { label: "Features", href: "#features", sectionId: "features" },
    { label: "The repo", href: "#the-repo", sectionId: "the-repo" },
    { label: "Showcase", href: "#showcase", sectionId: "showcase" },
    { label: "Pricing", href: "#pricing", sectionId: "pricing", pulse: true },
    { label: "FAQ", href: "#faq", sectionId: "faq" },
    { label: "Blog", href: "https://www.contentarchitecture.dev/blog", external: true },
  ],
  marquee: "Now available with Astro",
  menuLabel: "Menu",
  openMenuLabel: "Open menu",
  closeMenuLabel: "Close menu",
};
