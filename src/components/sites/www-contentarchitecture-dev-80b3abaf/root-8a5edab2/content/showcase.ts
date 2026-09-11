import type { AsciiGrid } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/AsciiImage";
import { decodeGlyphFieldModel } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/glyph-model";
import type { ShowcaseContent } from "../ShowcaseSection";
import asciiGrids from "../data/ascii-grids.json";
import glyphPhrases from "../data/glyph-phrases.json";
import orbModel from "../data/orb-model.json";

const IMAGES = "/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/images";

function ascii(key: keyof typeof asciiGrids): AsciiGrid {
  const { cells, levels, cols, rows, aspect } = asciiGrids[key];
  return { cells, levels, cols, rows, aspect };
}

export const showcaseContent: ShowcaseContent = {
  title: "The work that gets remembered.",
  intro: [
    "Real sites, shipped on The Content Architecture. With the plumbing already handled, the effort goes where it shows. The work here has been recognized by ",
    { text: "Awwwards", href: "https://www.awwwards.com/" },
    ", ",
    { text: "FWA", href: "https://thefwa.com/" },
    ", and ",
    { text: "CSSDA", href: "https://www.cssdesignawards.com/" },
    ", and picked up across design directories.",
  ],
  items: [
    {
      label: "Good Fella",
      href: "https://good-fella.com/",
      ascii: ascii("good-fella"),
      image: { src: `${IMAGES}/showcase-good-fella.jpg`, alt: "Good Fella website built on The Content Architecture" },
    },
    {
      label: "House of Honey",
      href: "https://www.houseofhoney.com/",
      ascii: ascii("house-of-honey"),
      image: { src: `${IMAGES}/showcase-house-of-honey.jpg`, alt: "House of Honey website built on The Content Architecture" },
    },
    {
      label: "Aspen Search",
      href: "https://www.aspensearch.com/",
      ascii: ascii("aspen-search"),
      image: {
        src: `${IMAGES}/showcase-aspen-search.jpg`,
        alt: "Aspen website hero section describing recruiting for software and AI/ML roles",
      },
    },
    {
      label: "Anuc Home",
      href: "https://www.anuchome.com/",
      ascii: ascii("anuc-home"),
      image: { src: `${IMAGES}/showcase-anuc-home.jpg`, alt: "Anuc Home website built on The Content Architecture" },
    },
    {
      label: "Edoardo Lunardi",
      href: "https://www.edoardolunardi.dev/",
      ascii: ascii("edoardo-lunardi"),
      image: {
        src: `${IMAGES}/showcase-edoardo-lunardi.jpg`,
        alt: "Portfolio website homepage for Edoardo Lunardi with featured article, about, and work gallery",
      },
    },
    {
      label: "Serve Robotics",
      href: "https://www.serverobotics.com/",
      ascii: ascii("serve-robotics"),
      image: { src: `${IMAGES}/showcase-serve-robotics.jpg`, alt: "Serve Robotics website built on The Content Architecture" },
    },
    {
      label: "Prism",
      href: "https://prismscience.org/",
      ascii: ascii("prism"),
      image: { src: `${IMAGES}/showcase-prism.png`, alt: "Prism website homepage with headline “Unlocking Protein Dynamics”" },
    },
    {
      label: "Muralia",
      href: "https://www.muralia.at/",
      ascii: ascii("muralia"),
      image: { src: `${IMAGES}/showcase-muralia.jpg`, alt: "Muralia website built on The Content Architecture" },
    },
    {
      label: "blink",
      href: "https://www.blink.trade/",
      ascii: ascii("blink"),
      image: { src: `${IMAGES}/showcase-blink.jpg`, alt: "blink website built on The Content Architecture" },
    },
    {
      label: "Creative Lives in Progress",
      href: "https://creativelivesinprogress.com/",
      ascii: ascii("creative-lives-in-progress"),
      image: {
        src: `${IMAGES}/showcase-creative-lives.jpg`,
        alt: "Creative Lives in Progress website built on The Content Architecture",
      },
    },
    {
      label: "The Content Architecture",
      href: "https://www.contentarchitecture.dev/",
      ascii: ascii("the-content-architecture"),
      image: {
        src: `${IMAGES}/showcase-content-architecture.png`,
        alt: "Sanity landing page with headline “The Sanity setup agents don’t reinvent”",
      },
    },
  ],
  glyph: { model: decodeGlyphFieldModel(orbModel), phrase: glyphPhrases.phrases.showcase },
};
