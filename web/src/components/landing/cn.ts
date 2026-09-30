import { clsx, type ClassValue } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

// The CA design system defines custom font-size tokens (text-caption-10, text-body-20, …). Without
// registering them, tailwind-merge treats `text-caption-10` as a text *color* and drops `text-white`.
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: ["ui", "caption-10", "caption-20", "body-10", "body-20", "body-30", "headline-10", "headline-20"],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
