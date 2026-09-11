import { FEATURES, FEATURES_INTRO } from "@/components/sites/contentarchitecture-dev/root/content";

export function FeaturesSection() {
  return (
    <section id="features" className="bg-background px-6 py-24 lg:px-16 lg:py-32">
      <div className="mx-auto max-w-5xl">
        <div className="mb-16 grid grid-cols-1 gap-8 lg:grid-cols-12">
          <h2 className="text-balance text-3xl font-medium leading-tight lg:col-span-7 lg:text-5xl">
            Every decision already made. So you can skip to the actual work.
          </h2>
          <p className="max-w-md text-base leading-relaxed text-muted-foreground lg:col-span-5">
            {FEATURES_INTRO}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-x-8 gap-y-12 lg:grid-cols-2">
          {FEATURES.map((feature) => (
            <div key={feature.number} className="flex flex-col gap-3">
              <span className="font-mono text-xs uppercase tracking-widest text-tertiary">
                {feature.number} / {feature.title}
              </span>
              <p className="text-sm leading-relaxed text-muted-foreground lg:text-base">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
