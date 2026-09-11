import type { PricingContent } from "../PricingSection";

const AVATARS = "/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/avatars";

export const pricingContent: PricingContent = {
  title: "Two editions.\nOne architecture.\nLifetime updates.",
  trusted: {
    // DOM order (z-index 5 → 1).
    avatars: [
      { src: `${AVATARS}/trusted-goodfellastudio.png` },
      { src: `${AVATARS}/trusted-elliottmangham.png` },
      { src: `${AVATARS}/trusted-studioboldest.png` },
      { src: `${AVATARS}/trusted-malikkotb.png` },
      { src: `${AVATARS}/trusted-minhchanh6.png` },
    ],
    label: "trusted by 40+ engineers",
  },
  editions: [
    {
      tag: "Next.js",
      status: "Available now",
      price: { currency: "€", amount: "399" },
      compareAt: { currency: "€", amount: "549" },
      specs: ["THE NEXT.JS 16 + SANITY V6 REPO", "FOR NEXT.JS + SANITY ENGINEERS, NOT NO-CODE"],
      cta: {
        leftText: "Get",
        rightText: "access",
        href: "https://www.contentarchitecture.dev/checkout?plan=next&code=ASTROLAUNCH",
      },
    },
    {
      tag: "Astro",
      status: "Available now",
      price: { currency: "€", amount: "399" },
      compareAt: { currency: "€", amount: "549" },
      specs: ["THE ASTRO 7 + SANITY V6 REPO", "FOR ASTRO + SANITY ENGINEERS, NOT NO-CODE"],
      cta: {
        leftText: "Get",
        rightText: "access",
        href: "https://www.contentarchitecture.dev/checkout?plan=astro&code=ASTROLAUNCH",
      },
    },
  ],
  includes: {
    title: "Every edition includes",
    items: [
      "ONE-TIME FEE, NO SUBSCRIPTION",
      "PERPETUAL LICENSE, UNLIMITED PROJECTS",
      "COMMERCIAL USE, NO ATTRIBUTION",
      "LIFETIME UPDATES, INCLUDED",
      "AGENT-READY: SKILLS, MCP, LLMS.TXT",
      "PRIVATE GITHUB DISCUSSIONS",
      "DIRECT LINE TO THE MAINTAINER",
      "FULL SOURCE ON PURCHASE, SALES FINAL",
      "ALL PRICES IN EUR",
    ],
    notes: [
      [
        "Already own one edition? The second one is not full price. ",
        { text: "Email me", href: "mailto:hello@edoardolunardi.dev" },
        " and I will send you a code.",
      ],
    ],
  },
};
