export interface NumberedFeature {
  number: string;
  title: string;
  description: string;
}

export interface ProblemRow {
  number: string;
  title: string;
  time: string;
}

export interface ShowcaseItem {
  name: string;
  url: string;
  image: string;
  alt: string;
}

export interface Testimonial {
  quote: string;
  name: string;
  role: string;
  avatar: string;
}

export interface FaqItem {
  number: string;
  question: string;
  answer: string;
}

export interface PricingEdition {
  number: string;
  eyebrow: string;
  sub: string;
  price: string;
  oldPrice: string;
  ctaHref: string;
  code?: string;
}
