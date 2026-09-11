import { SiteHeader } from "@/components/sites/contentarchitecture-dev/root/SiteHeader";
import { HeroSection } from "@/components/sites/contentarchitecture-dev/root/HeroSection";
import { ProblemsSection } from "@/components/sites/contentarchitecture-dev/root/ProblemsSection";
import { FeaturesSection } from "@/components/sites/contentarchitecture-dev/root/FeaturesSection";
import { RepoSection } from "@/components/sites/contentarchitecture-dev/root/RepoSection";
import { ShowcaseSection } from "@/components/sites/contentarchitecture-dev/root/ShowcaseSection";
import { PricingSection } from "@/components/sites/contentarchitecture-dev/root/PricingSection";
import { FaqSection } from "@/components/sites/contentarchitecture-dev/root/FaqSection";
import { SiteFooter } from "@/components/sites/contentarchitecture-dev/root/SiteFooter";

export default function Home() {
  return (
    <>
      <SiteHeader />
      <main className="flex flex-col">
        <HeroSection />
        <ProblemsSection />
        <FeaturesSection />
        <RepoSection />
        <ShowcaseSection />
        <PricingSection />
        <FaqSection />
      </main>
      <SiteFooter />
    </>
  );
}
