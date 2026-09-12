import React from "react";
import { WorkbenchProvider } from "@/components/sites/sat-sa-with-pqc/workbench/state/WorkbenchContext";
import { WorkbenchLayout } from "@/components/sites/sat-sa-with-pqc/workbench/ui/WorkbenchLayout";

export const metadata = {
  title: "NCIIPC Supervisory Workbench | SAT-SA",
  description: "Offline, evidence-backed supervisory analytics for NCIIPC examiners.",
};

export default function RootWorkbenchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <WorkbenchProvider>
      <WorkbenchLayout>{children}</WorkbenchLayout>
    </WorkbenchProvider>
  );
}
