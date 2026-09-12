"use client";

import { PageShell } from "../shared/PageShell";
import { BannerSection } from "./BannerSection";
import { FaqSection } from "./FaqSection";
import { FeaturesSection } from "./FeaturesSection";
import { HeroSection } from "./HeroSection";
import { PricingSection } from "./PricingSection";
import { ProblemsSection } from "./ProblemsSection";
import { RepoSection } from "./RepoSection";
import { ReviewsSection } from "./ReviewsSection";
import { ShowcaseSection } from "./ShowcaseSection";
import { SiteFooter } from "./SiteFooter";
import { SiteNav } from "./SiteNav";
import { bannerContent } from "./content/banner";
import { faqContent } from "./content/faq";
import { featuresContent } from "./content/features";
import { footerContent } from "./content/footer";
import { heroContent } from "./content/hero";
import { navContent } from "./content/nav";
import { pricingContent } from "./content/pricing";
import { problemsContent } from "./content/problems";
import { repoContent } from "./content/repo";
import { reviewsContent } from "./content/reviews";
import { showcaseContent } from "./content/showcase";

/** contentarchitecture.dev, assembled from the section components and their CA content. */
export function ContentArchitecturePage() {
  return (
    <PageShell header={<SiteNav content={navContent} />} footer={<SiteFooter content={footerContent} />}>
      <HeroSection content={heroContent} />
      <ProblemsSection content={problemsContent} />
      <FeaturesSection content={featuresContent} />
      <RepoSection content={repoContent} />
      <ShowcaseSection content={showcaseContent} />
      <ReviewsSection content={reviewsContent} />
      <PricingSection content={pricingContent} />
      <FaqSection content={faqContent} />
      <BannerSection content={bannerContent} />
    </PageShell>
  );
}
