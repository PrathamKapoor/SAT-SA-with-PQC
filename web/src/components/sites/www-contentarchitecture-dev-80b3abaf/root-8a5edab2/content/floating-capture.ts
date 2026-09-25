import type { FloatingCaptureContent } from "../FloatingCapture";

export const floatingCaptureContent: FloatingCaptureContent = {
  title: "Not buying today? Stay close.",
  text: "One short email when the repo changes or a discount goes live. Nothing else, unsubscribe anytime.",
  closeLabel: "Close",
  form: {
    label: "Email",
    placeholder: "your@email.com",
    ctaText: "Subscribe",
    successMessage: "You're on the list.",
    errorMessage: "Enter a valid email address.",
  },
  delaySeconds: 12,
  side: "left",
  exitIntent: false,
};
