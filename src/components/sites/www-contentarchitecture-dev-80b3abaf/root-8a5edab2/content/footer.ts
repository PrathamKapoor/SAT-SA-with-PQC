import { decodeGlyphFieldModel } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/glyph-model";
import type { FooterContent } from "../SiteFooter";
import glyphPhrases from "../data/glyph-phrases.json";
import orbModel from "../data/orb-model.json";

const LIVE = "https://www.contentarchitecture.dev";

/** CA footer, verbatim from `dom/13-footer.html` ("Get access" rewritten to the in-page anchor). */
export const footerContent: FooterContent = {
  newsletter: {
    label: "Email",
    placeholder: "your@email.com",
    ctaText: "Stay",
    ctaRightText: "updated",
    successMessage: "You're on the list.",
    errorMessage: "Enter a valid email address.",
  },
  navLabel: "Footer",
  links: [
    { label: "Blog", href: `${LIVE}/blog`, external: true },
    { label: "Roadmap", href: `${LIVE}/roadmap`, external: true },
    { label: "Get access", href: "#pricing", pulse: true },
    { label: "Privacy Policy", href: `${LIVE}/legal/privacy-policy`, external: true },
    { label: "Terms Of Service", href: `${LIVE}/legal/terms-of-service`, external: true },
    { label: "Imprint", href: `${LIVE}/legal/imprint`, external: true },
  ],
  copyright: { year: "2026", owner: "The Content Architecture" },
  credit: { label: "Built by edoardolunardi.dev", href: "https://edoardolunardi.dev" },
  glyph: { model: decodeGlyphFieldModel(orbModel), phrase: glyphPhrases.phrases.faq },
};
