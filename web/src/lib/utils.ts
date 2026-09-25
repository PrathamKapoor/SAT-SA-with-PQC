import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Register the custom font-size tokens so tailwind-merge does not treat
// `text-micro` / `text-display` as colours and drop a colour class.
const twMerge = extendTailwindMerge({
  extend: { theme: { text: ["micro", "display"] } },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
