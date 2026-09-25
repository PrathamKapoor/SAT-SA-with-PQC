import type { ReactNode } from "react";
import { PublicFooter, PublicNav } from "@/components/public/site-chrome";

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <a href="#content" className="skip-link">
        Skip to content
      </a>
      <PublicNav />
      <main id="content">{children}</main>
      <PublicFooter />
    </>
  );
}
