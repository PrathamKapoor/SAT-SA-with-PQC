import { SmoothScroll } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/SmoothScroll";
import { AgentsSection } from "./AgentsSection";
import { HeroSection } from "./HeroSection";
import { IdentitySection } from "./IdentitySection";
import { LimitationsSection } from "./LimitationsSection";
import { PipelineSection } from "./PipelineSection";
import { ScreenshotsSection } from "./ScreenshotsSection";
import { SiteFooter } from "./SiteFooter";
import { SiteNav } from "./SiteNav";
import { StatsSection } from "./StatsSection";
import { TrustSection } from "./TrustSection";
import { ValidationSection } from "./ValidationSection";
import { WalkthroughSection } from "./WalkthroughSection";
import { findingWalkthroughContent } from "./content/demo";
import { screenshotsContent } from "./content/screenshots";
import {
  agentsContent,
  footerContent,
  heroContent,
  identityContent,
  limitationsContent,
  navContent,
  pipelineContent,
  statsContent,
  trustContent,
  validationContent,
} from "./content/site";
import { walkthroughSectionContent } from "./content/walkthrough";

/**
 * SAT-SA landing page — real content from github.com/PrathamKapoor/SAT-SA-with-PQC, reusing the
 * contentarchitecture.dev shared design system (spacing, type scale, palette, primitives) with the
 * product's own signal-green (#34d399, hardcoded per use — redeclaring the shared --color-accent
 * theme variable outside @theme gets silently dropped by Tailwind's build) instead of CA's orange.
 * Background is a layered dark gradient plus a graph-paper texture (`.satsa-grid-texture` in
 * globals.css) rather than flat black, following the same "dense bordered panel" language for
 * charts and stat groups throughout instead of loosely-gapped floating cards.
 */
export function SatSaPage() {
  return (
    <SmoothScroll>
      <div data-theme="satsa-light" className="satsa-light flex min-h-svh flex-col bg-[#f7f9fc] text-slate-950">
        <SiteNav content={navContent} />
        <main className="flex-1">
          <HeroSection content={heroContent} />
          <IdentitySection content={identityContent} />
          <WalkthroughSection content={walkthroughSectionContent} finding={findingWalkthroughContent} />
          <StatsSection content={statsContent} />
          <PipelineSection content={pipelineContent} />
          <AgentsSection content={agentsContent} />
          <TrustSection content={trustContent} />
          <ScreenshotsSection content={screenshotsContent} />
          <ValidationSection content={validationContent} />
          <LimitationsSection content={limitationsContent} />
        </main>
        <SiteFooter content={footerContent} />
      </div>
    </SmoothScroll>
  );
}
