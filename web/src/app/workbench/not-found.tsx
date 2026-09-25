import { ButtonLink } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-[1400px] px-4 py-10 md:px-8">
      <EmptyState title="This record does not exist" action={<ButtonLink href="/workbench">Back to the workbench</ButtonLink>}>
        It may belong to a different assessment period, or the link is out of date.
      </EmptyState>
    </div>
  );
}
