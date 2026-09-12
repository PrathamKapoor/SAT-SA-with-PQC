"use client";

import { PageShell } from "../shared/PageShell";
import { FaqSection } from "./FaqSection";
import { FeaturesSection } from "./FeaturesSection";
import { HeroSection } from "./HeroSection";
import { PricingSection } from "./PricingSection";
import { ProblemsSection } from "./ProblemsSection";
import { RepoSection } from "./RepoSection";
import { ShowcaseSection } from "./ShowcaseSection";
import { SiteNav } from "./SiteNav";
import { faqContent } from "./content/faq";
import { featuresContent } from "./content/features";
import { heroContent } from "./content/hero";
import { navContent } from "./content/nav";
import { pricingContent } from "./content/pricing";
import { problemsContent } from "./content/problems";
import { repoContent } from "./content/repo";
import { showcaseContent } from "./content/showcase";

/** contentarchitecture.dev, assembled from the section components and their CA content. */
export function ContentArchitecturePage() {
  return (
    <PageShell header={<SiteNav content={navContent} />}>
      <HeroSection content={heroContent} />
      <ProblemsSection content={problemsContent} />
      <FeaturesSection content={featuresContent} />
      <RepoSection content={repoContent} />
      <ShowcaseSection content={showcaseContent} />
      <PricingSection content={pricingContent} />
      <FaqSection content={faqContent} />
    </PageShell>
  );
}
