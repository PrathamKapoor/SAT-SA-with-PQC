/**
 * SAT-SA hero evidence engine. One set of evidence particles whose spring targets move continuously
 * from a loose orbital field (analysis = 0) into finding clusters, prioritised review and the human
 * examiner (analysis = 1). Nothing is swapped or cross-faded: the same objects reorganise.
 */

export type Category = "alert" | "case" | "investigation" | "escalation" | "asset";
export type Phase = "raw" | "analysing" | "prioritising" | "ready";

interface Pt {
  x: number;
  y: number;
}

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

type FindingKind = "gap" | "negative" | "anomaly" | "peer";

interface FindingDef {
  kind: FindingKind;
  label: string;
  short: string;
  attention: boolean;
}

export const FINDINGS: FindingDef[] = [
  { kind: "gap", label: "EXECUTION GAP", short: "EXEC GAP", attention: true },
  { kind: "negative", label: "NEGATIVE SPACE", short: "NEG SPACE", attention: true },
  { kind: "anomaly", label: "ANOMALY", short: "ANOMALY", attention: true },
  { kind: "peer", label: "PEER DEVIATION", short: "PEER DEV", attention: false },
];

const CATEGORIES: Category[] = ["alert", "case", "investigation", "escalation", "asset"];
const CATEGORY_LABEL: Record<Category, string> = {
  alert: "ALERT",
  case: "CASE",
  investigation: "INVESTIGATION",
  escalation: "ESCALATION",
  asset: "ASSET",
};

const INK = "15, 23, 42";
const PURPLE = "124, 58, 237";
const ORANGE = "234, 88, 12";
const BLUE = "37, 99, 235";
const CATEGORY_RGB: Record<Category, string> = {
  alert: "37, 99, 235",
  case: "71, 85, 105",
  investigation: "59, 130, 246",
  escalation: "29, 78, 216",
  asset: "100, 116, 139",
};

type Role = "member" | "gapAlert" | "gapClosed" | "outlier" | "peerOffset" | "negCenter";

interface Particle {
  cat: Category;
  depth: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  angle: number;
  orbit: number;
  speed: number;
  phase: number;
  finding: number;
  slot: number;
  role: Role;
  w: number;
  sx: number;
  sy: number;
  alpha: number;
}

interface Link {
  a: number;
  b: number;
  style: "solid" | "weak" | "duplicate" | "broken";
}

interface Layout {
  mobile: boolean;
  width: number;
  height: number;
  core: Pt;
  evidence: Pt;
  colGap: number;
  rowGap: number;
  findings: Pt[];
  clusterScale: number;
  review: Pt;
  examiner: Pt;
  chaos: Pt;
  rx: number;
  ry: number;
  safe: Rect | null;
  font: number;
}

export interface PointerState {
  x: number;
  y: number;
  inside: boolean;
  down: boolean;
  dx: number;
  dy: number;
}

function mulberry32(seed: number) {
  let s = seed;
  return () => {
    s |= 0;
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const clamp = (v: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const smooth = (lo: number, hi: number, v: number) => {
  const t = clamp((v - lo) / (hi - lo));
  return t * t * (3 - 2 * t);
};
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export class EvidenceEngine {
  private particles: Particle[] = [];
  private links: Link[] = [];
  private layout: Layout;
  private rng = mulberry32(26157);
  private time = 0;
  private pulses: number[] = [];
  private pulsed: boolean[] = [];
  private chaosLabels: { index: number; born: number }[] = [];
  private nextLabelAt = 1.2;
  private monoFont = "ui-monospace, monospace";
  private parallax = { x: 0, y: 0 };
  private evidenceRows = 1;

  analysis = 0;
  target = 0;
  speed = 1;

  constructor(width: number, height: number, safe: Rect | null) {
    this.layout = this.computeLayout(width, height, safe);
    this.pulsed = FINDINGS.map(() => false);
    this.pulses = FINDINGS.map(() => -1);
    this.build();
  }

  setFont(family: string) {
    if (family.trim()) this.monoFont = family;
  }

  resize(width: number, height: number, safe: Rect | null) {
    const wasMobile = this.layout.mobile;
    this.layout = this.computeLayout(width, height, safe);
    if (wasMobile !== this.layout.mobile) this.build();
  }

  get phase(): Phase {
    if (this.analysis < 0.2) return "raw";
    if (this.analysis < 0.6) return "analysing";
    if (this.analysis < 0.9) return "prioritising";
    return "ready";
  }

  private computeLayout(width: number, height: number, safe: Rect | null): Layout {
    const mobile = width < 1024;
    if (!mobile) {
      return {
        mobile,
        width,
        height,
        evidence: { x: width * 0.555, y: height * 0.5 },
        colGap: 18,
        rowGap: 15,
        core: { x: width * 0.655, y: height * 0.5 },
        findings: [0.22, 0.41, 0.6, 0.79].map((fy) => ({ x: width * 0.775, y: height * fy })),
        clusterScale: clamp(height / 820, 0.8, 1.15) * 1.45,
        review: { x: width * 0.905, y: height * 0.4 },
        examiner: { x: width * 0.905, y: height * 0.66 },
        chaos: { x: width * 0.67, y: height * 0.5 },
        rx: width * 0.42,
        ry: height * 0.45,
        safe,
        font: 10.5,
      };
    }
    const top = safe ? Math.min(height - 360, safe.y + safe.h + 28) : height * 0.5;
    const regionH = height - top - 24;
    const y = (f: number) => top + regionH * f;
    return {
      mobile,
      width,
      height,
      evidence: { x: width * 0.5, y: y(0.1) },
      colGap: 12,
      rowGap: 13,
      core: { x: width * 0.5, y: y(0.34) },
      findings: [0.15, 0.38, 0.62, 0.85].map((fx) => ({ x: width * fx, y: y(0.6) })),
      clusterScale: 0.8,
      review: { x: width * 0.3, y: y(0.9) },
      examiner: { x: width * 0.7, y: y(0.9) },
      chaos: { x: width * 0.5, y: height * 0.55 },
      rx: width * 0.62,
      ry: height * 0.5,
      safe,
      font: 9,
    };
  }

  private build() {
    const r = this.rng;
    const mobile = this.layout.mobile;
    const findingSizes = mobile ? [3, 5, 4, 5] : [5, 6, 7, 7];
    const total = mobile ? 32 : 84;
    const particles: Particle[] = [];

    const make = (cat: Category, finding: number, slot: number, role: Role): Particle => {
      const depth = r() > 0.78 ? 3 : r() > 0.4 ? 2 : 1;
      const angle = r() * Math.PI * 2;
      const orbit = 0.1 + Math.sqrt(r()) * 0.9;
      const p: Particle = {
        cat,
        depth,
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        angle,
        orbit,
        speed: (0.0006 + r() * 0.0014) * (r() > 0.5 ? 1 : -1) * (4 - depth) * 0.6,
        phase: r() * Math.PI * 2,
        finding,
        slot,
        role,
        w: 0,
        sx: 0,
        sy: 0,
        alpha: 0,
      };
      const c = this.chaosPosition(p);
      p.x = c.x;
      p.y = c.y;
      return p;
    };

    findingSizes.forEach((size, f) => {
      const kind = FINDINGS[f].kind;
      for (let s = 0; s < size; s++) {
        let role: Role = "member";
        let cat: Category = CATEGORIES[Math.floor(r() * CATEGORIES.length)];
        if (kind === "gap" && s === 0) {
          role = "gapAlert";
          cat = "alert";
        } else if (kind === "gap" && s === 1) {
          role = "gapClosed";
          cat = "case";
        } else if (kind === "negative" && s === 0) {
          role = "negCenter";
          cat = "asset";
        } else if (kind === "anomaly" && s === size - 1) {
          role = "outlier";
        } else if (kind === "peer" && s === size - 1) {
          role = "peerOffset";
        }
        particles.push(make(cat, f, s, role));
      }
    });

    const evidenceCount = total - particles.length;
    for (let i = 0; i < evidenceCount; i++) {
      particles.push(make(CATEGORIES[i % CATEGORIES.length], -1, i, "member"));
    }

    const order = particles.map((_, i) => i).sort(() => r() - 0.5);
    const links: Link[] = [];
    let i = 0;
    while (i < order.length) {
      const len = 2 + Math.floor(r() * 3);
      const lead = particles[order[i]];
      for (let k = 0; k < len && i + k < order.length; k++) {
        const member = particles[order[i + k]];
        if (k > 0) {
          member.angle = lead.angle + (r() - 0.5) * 0.5;
          member.orbit = clamp(lead.orbit + (r() - 0.5) * 0.12, 0.1, 0.95);
          member.speed = lead.speed * (0.8 + r() * 0.4);
          const c = this.chaosPosition(member);
          member.x = c.x;
          member.y = c.y;
          const roll = r();
          links.push({
            a: order[i + k - 1],
            b: order[i + k],
            style: roll < 0.5 ? "solid" : roll < 0.75 ? "weak" : roll < 0.87 ? "duplicate" : "broken",
          });
        }
      }
      i += len;
    }

    this.particles = particles;
    this.links = links;
    this.evidenceRows = Math.ceil(evidenceCount / CATEGORIES.length);
    this.chaosLabels = [];
  }

  private chaosPosition(p: Particle): Pt {
    const L = this.layout;
    const t = this.time;
    const wobble = 5 + p.depth * 4;
    return {
      x: L.chaos.x + Math.cos(p.angle) * p.orbit * L.rx + Math.sin(t * 0.55 + p.phase) * wobble,
      y: L.chaos.y + Math.sin(p.angle) * p.orbit * L.ry + Math.cos(t * 0.47 + p.phase * 1.3) * wobble,
    };
  }

  private findingCenter(f: number): Pt {
    return this.layout.findings[f];
  }

  private slotOffset(p: Particle): Pt {
    const s = this.layout.clusterScale;
    const kind = FINDINGS[p.finding].kind;
    const mobile = this.layout.mobile;
    switch (kind) {
      case "gap": {
        if (p.role === "gapAlert") return { x: -30 * s, y: -2 * s };
        if (p.role === "gapClosed") return { x: 26 * s, y: 14 * s };
        const k = p.slot - 2;
        return { x: (-14 + k * 12) * s, y: 30 * s };
      }
      case "negative": {
        if (p.role === "negCenter") return { x: 0, y: 0 };
        const slots = mobile ? 5 : 6;
        const empty = mobile ? 1 : 2;
        const idx = p.slot - 1 >= empty ? p.slot : p.slot - 1;
        const a = -Math.PI / 2 + (idx * Math.PI * 2) / slots;
        return { x: Math.cos(a) * 26 * s, y: Math.sin(a) * 22 * s };
      }
      case "anomaly": {
        if (p.role === "outlier") return { x: 34 * s, y: -22 * s };
        const offsets = [
          [-8, -4],
          [4, -9],
          [10, 3],
          [-2, 8],
          [-12, 7],
          [7, 12],
        ];
        const o = offsets[p.slot % offsets.length];
        return { x: o[0] * s * 1.3, y: o[1] * s * 1.3 };
      }
      case "peer": {
        if (p.role === "peerOffset") return { x: 6 * s, y: -20 * s };
        const count = mobile ? 4 : 6;
        return { x: (-((count - 1) * 15) / 2 + p.slot * 15) * s, y: 6 * s };
      }
    }
  }

  private negativeEmptySlot(f: number): Pt {
    const s = this.layout.clusterScale;
    const mobile = this.layout.mobile;
    const slots = mobile ? 5 : 6;
    const empty = mobile ? 1 : 2;
    const a = -Math.PI / 2 + (empty * Math.PI * 2) / slots;
    const c = this.findingCenter(f);
    return { x: c.x + Math.cos(a) * 26 * s, y: c.y + Math.sin(a) * 22 * s };
  }

  private structuredPosition(p: Particle): Pt {
    const L = this.layout;
    const breathe = Math.sin(this.time * 0.9 + p.phase) * 1.1;
    if (p.finding >= 0) {
      const c = this.findingCenter(p.finding);
      const o = this.slotOffset(p);
      return { x: c.x + o.x + breathe, y: c.y + o.y + breathe * 0.6 };
    }
    const col = CATEGORIES.indexOf(p.cat);
    const row = Math.floor(p.slot / CATEGORIES.length);
    const rows = this.evidenceRows;
    if (L.mobile) {
      return {
        x: L.evidence.x + (col - 2) * L.colGap * 1.8,
        y: L.evidence.y + (row - (rows - 1) / 2) * L.rowGap,
      };
    }
    return {
      x: L.evidence.x + (col - 2) * L.colGap,
      y: L.evidence.y + (row - (rows - 1) / 2) * L.rowGap + breathe * 0.4,
    };
  }

  private weightFor(p: Particle, local: number): number {
    const a = Math.max(this.analysis, local);
    if (p.finding < 0) return smooth(0.08, 0.5, a);
    const lo = 0.22 + p.finding * 0.07;
    return smooth(lo, lo + 0.42, a);
  }

  private findingAlpha(f: number) {
    const lo = 0.42 + f * 0.07;
    return smooth(lo, lo + 0.22, this.analysis);
  }

  step(dtMs: number, pointer: PointerState, reduced: boolean) {
    const f = reduced ? 1 : Math.min(dtMs / 16.67, 2.5);
    const L = this.layout;

    if (reduced) {
      this.analysis = this.target;
    } else {
      this.time += 0.016 * f;
      const rate = (this.target > this.analysis ? 0.011 : 0.016) * this.speed;
      this.analysis += (this.target - this.analysis) * (1 - Math.pow(1 - rate, f));
      if (Math.abs(this.target - this.analysis) < 0.002) this.analysis = this.target;
      const nx = pointer.inside ? pointer.x / L.width - 0.5 : 0;
      const ny = pointer.inside ? pointer.y / L.height - 0.5 : 0;
      this.parallax.x += (nx - this.parallax.x) * 0.05 * f;
      this.parallax.y += (ny - this.parallax.y) * 0.05 * f;
    }

    const radius = L.mobile ? 120 : 190;
    for (const p of this.particles) {
      if (!reduced) p.angle += p.speed * f * (1 - 0.85 * p.w);
      const dist = Math.hypot(p.x - pointer.x, p.y - pointer.y);
      const falloff = pointer.inside && !reduced ? clamp(1 - dist / radius) : 0;
      const local = falloff * (pointer.down ? 0.95 : 0.62);
      p.w = this.weightFor(p, local);

      const chaos = this.chaosPosition(p);
      const structured = this.structuredPosition(p);
      let tx = lerp(chaos.x, structured.x, p.w);
      let ty = lerp(chaos.y, structured.y, p.w);

      if (reduced) {
        p.x = tx;
        p.y = ty;
        p.vx = 0;
        p.vy = 0;
      } else {
        if (falloff > 0 && p.w < 0.6) {
          tx += (pointer.x - p.x) * 0.08 * falloff * (1 - p.w);
          ty += (pointer.y - p.y) * 0.08 * falloff * (1 - p.w);
        }
        if (pointer.down && falloff > 0) {
          p.vx += pointer.dx * 0.1 * falloff;
          p.vy += pointer.dy * 0.1 * falloff;
        }
        const k = (0.016 + 0.034 * p.w) * (0.7 + 0.3 * this.speed) * f;
        const damping = Math.pow(0.88, f);
        p.vx = (p.vx + (tx - p.x) * k) * damping;
        p.vy = (p.vy + (ty - p.y) * k) * damping;
        p.x += p.vx * f;
        p.y += p.vy * f;
      }

      const par = (reduced ? 0 : 1) * p.depth * 5 * (1 - 0.7 * p.w);
      p.sx = p.x + this.parallax.x * par * 2;
      p.sy = p.y + this.parallax.y * par * 2;
      p.alpha = (0.34 + p.depth * 0.18) * this.safeFade(p.sx, p.sy);
    }

    FINDINGS.forEach((_, i) => {
      const fa = this.findingAlpha(i);
      if (fa > 0.92 && !this.pulsed[i]) {
        this.pulsed[i] = true;
        this.pulses[i] = reduced ? -1 : this.time;
      } else if (fa < 0.3) {
        this.pulsed[i] = false;
      }
    });

    if (!reduced && this.time > this.nextLabelAt) {
      this.nextLabelAt = this.time + 1.1 + this.rng() * 0.8;
      const candidates = this.particles
        .map((p, i) => ({ p, i }))
        .filter(({ p }) => p.w < 0.2 && this.safeFade(p.sx, p.sy) > 0.9 && p.sx > 40 && p.sx < L.width - 110 && p.sy > 30 && p.sy < L.height - 30);
      const free = candidates.filter(({ p }) =>
        this.chaosLabels.every((cl) => Math.hypot(this.particles[cl.index].sx - p.sx, this.particles[cl.index].sy - p.sy) > 140),
      );
      if (free.length) {
        const pick = free[Math.floor(this.rng() * free.length)];
        this.chaosLabels.push({ index: pick.i, born: this.time });
        if (this.chaosLabels.length > 3) this.chaosLabels.shift();
      }
    }
  }

  private safeFade(x: number, y: number) {
    const s = this.layout.safe;
    if (!s) return 1;
    const pad = 28;
    const dx = Math.max(s.x - x, 0, x - (s.x + s.w));
    const dy = Math.max(s.y - y, 0, y - (s.y + s.h));
    const d = Math.hypot(dx, dy);
    return 0.16 + 0.84 * clamp(d / pad);
  }

  nearestFinding(x: number, y: number): number {
    const reach = 46 * this.layout.clusterScale + 18;
    let best = -1;
    let bestD = Infinity;
    this.layout.findings.forEach((c, i) => {
      const d = Math.hypot(c.x - x, c.y - y);
      if (d < reach && d < bestD && this.findingAlpha(i) > 0.5) {
        best = i;
        bestD = d;
      }
    });
    return best;
  }

  private nearestParticle(x: number, y: number): number {
    let best = -1;
    let bestD = 34;
    this.particles.forEach((p, i) => {
      const d = Math.hypot(p.sx - x, p.sy - y);
      if (d < bestD) {
        best = i;
        bestD = d;
      }
    });
    return best;
  }

  draw(ctx: CanvasRenderingContext2D, pointer: PointerState, reduced: boolean) {
    const L = this.layout;
    const a = this.analysis;
    const P = this.particles;
    ctx.clearRect(0, 0, L.width, L.height);

    const hoverFinding = pointer.inside ? this.nearestFinding(pointer.x, pointer.y) : -1;
    const hoverParticle = pointer.inside && hoverFinding < 0 ? this.nearestParticle(pointer.x, pointer.y) : -1;
    const chainGroup = new Set<number>();
    if (hoverParticle >= 0) {
      chainGroup.add(hoverParticle);
      for (let pass = 0; pass < 3; pass++) {
        for (const l of this.links) {
          if (chainGroup.has(l.a) || chainGroup.has(l.b)) {
            chainGroup.add(l.a);
            chainGroup.add(l.b);
          }
        }
      }
    }
    const focus = (i: number) => {
      if (hoverFinding >= 0) return P[i].finding === hoverFinding && P[i].w > 0.5 ? 1.5 : 0.45;
      if (hoverParticle >= 0) return chainGroup.has(i) ? 1.7 : 0.55;
      return 1;
    };

    this.drawOrbits(ctx, a);

    // Raw evidence: proximity relationships and imperfect workflow chains.
    const rawAlpha = Math.pow(1 - a, 1.4);
    if (rawAlpha > 0.02) {
      const maxD = L.mobile ? 78 : 104;
      ctx.lineWidth = 0.6;
      for (let i = 0; i < P.length; i++) {
        for (let j = i + 1; j < P.length; j++) {
          const d = Math.hypot(P[i].sx - P[j].sx, P[i].sy - P[j].sy);
          if (d < maxD) {
            const al = 0.16 * (1 - d / maxD) * rawAlpha * Math.min(P[i].alpha, P[j].alpha) * 1.6;
            ctx.strokeStyle = `rgba(${INK}, ${al})`;
            ctx.beginPath();
            ctx.moveTo(P[i].sx, P[i].sy);
            ctx.lineTo(P[j].sx, P[j].sy);
            ctx.stroke();
          }
        }
      }
      for (const l of this.links) {
        const p = P[l.a];
        const q = P[l.b];
        const span = Math.hypot(p.sx - q.sx, p.sy - q.sy);
        const fade = Math.max(1 - Math.max(p.w, q.w) * 1.4, 0) * clamp(1 - (span - 140) / 120);
        const al = 0.42 * rawAlpha * fade * Math.min(p.alpha, q.alpha) * Math.min(focus(l.a), focus(l.b));
        if (al < 0.01) continue;
        ctx.strokeStyle = `rgba(${BLUE}, ${al})`;
        ctx.lineWidth = 0.8;
        ctx.setLineDash(l.style === "weak" ? [2, 4] : []);
        ctx.beginPath();
        if (l.style === "broken") {
          ctx.moveTo(p.sx, p.sy);
          ctx.lineTo(lerp(p.sx, q.sx, 0.42), lerp(p.sy, q.sy, 0.42));
          ctx.moveTo(lerp(p.sx, q.sx, 0.64), lerp(p.sy, q.sy, 0.64));
          ctx.lineTo(q.sx, q.sy);
        } else {
          ctx.moveTo(p.sx, p.sy);
          ctx.lineTo(q.sx, q.sy);
          if (l.style === "duplicate") {
            const nx = -(q.sy - p.sy);
            const ny = q.sx - p.sx;
            const n = Math.hypot(nx, ny) || 1;
            ctx.moveTo(p.sx + (nx / n) * 3, p.sy + (ny / n) * 3);
            ctx.lineTo(q.sx + (nx / n) * 3, q.sy + (ny / n) * 3);
          }
        }
        ctx.stroke();
      }
      ctx.setLineDash([]);
    }

    this.drawStructure(ctx, a, reduced, hoverFinding);

    // Evidence particles (the same objects in every state).
    for (let i = 0; i < P.length; i++) {
      const p = P[i];
      const al = clamp(p.alpha * focus(i) * (0.85 + p.w * 0.35), 0, 1);
      this.drawParticle(ctx, p, al);
    }

    this.drawFindingMarks(ctx, a, reduced, hoverFinding);
    this.drawCore(ctx, a);
    this.drawOutputs(ctx, a);

    // A handful of category labels while evidence is still raw.
    ctx.font = `500 ${L.font}px ${this.monoFont}`;
    this.setSpacing(ctx, 1.2);
    if (hoverParticle >= 0 && P[hoverParticle].w < 0.5) {
      const p = P[hoverParticle];
      this.label(ctx, CATEGORY_LABEL[p.cat], p.sx + 9, p.sy - 8, `rgba(${INK}, 0.85)`, "left");
    } else if (!reduced) {
      for (const cl of this.chaosLabels) {
        const p = P[cl.index];
        const age = this.time - cl.born;
        const al = Math.min(age / 0.4, 1) * clamp((3.2 - age) / 0.6) * (1 - p.w * 3) * 0.6;
        if (al > 0.02) this.label(ctx, CATEGORY_LABEL[p.cat], p.sx + 8, p.sy - 7, `rgba(${INK}, ${al})`, "left");
      }
    }
    this.setSpacing(ctx, 0);
  }

  private setSpacing(ctx: CanvasRenderingContext2D, px: number) {
    if ("letterSpacing" in ctx) (ctx as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = `${px}px`;
  }

  private label(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, color: string, align: CanvasTextAlign) {
    ctx.textAlign = align;
    ctx.textBaseline = "middle";
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);
  }

  private drawOrbits(ctx: CanvasRenderingContext2D, a: number) {
    const L = this.layout;
    const rings = L.mobile ? [0.34, 0.62] : [0.24, 0.46, 0.7];
    ctx.lineWidth = 1;
    rings.forEach((r, idx) => {
      const al = (0.05 + idx * 0.015) * (1 - a * 0.7);
      ctx.strokeStyle = `rgba(${INK}, ${al})`;
      ctx.beginPath();
      ctx.ellipse(
        L.chaos.x + this.parallax.x * (idx + 1) * 14,
        L.chaos.y + this.parallax.y * (idx + 1) * 10,
        L.rx * r * 1.25,
        L.ry * r,
        -0.08,
        0,
        Math.PI * 2,
      );
      ctx.stroke();
    });
  }

  private signal(ctx: CanvasRenderingContext2D, from: Pt, to: Pt, alpha: number, reduced: boolean, rgb: string, speed: number, offset: number) {
    if (alpha < 0.02) return;
    ctx.strokeStyle = `rgba(${rgb}, ${0.22 * alpha})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();
    if (reduced) return;
    const t = (this.time * speed + offset) % 1;
    ctx.fillStyle = `rgba(${rgb}, ${0.85 * alpha})`;
    ctx.beginPath();
    ctx.arc(lerp(from.x, to.x, t), lerp(from.y, to.y, t), 1.9, 0, Math.PI * 2);
    ctx.fill();
  }

  private drawStructure(ctx: CanvasRenderingContext2D, a: number, reduced: boolean, hoverFinding: number) {
    const L = this.layout;
    const P = this.particles;

    // Evidence streams converge on SAT-SA.
    const intake = smooth(0.18, 0.5, a);
    const evidenceEdge = L.mobile
      ? { x: L.evidence.x, y: L.evidence.y + L.rowGap * 2.2 }
      : { x: L.evidence.x + L.colGap * 2.6, y: L.evidence.y };
    for (let k = 0; k < 3; k++) {
      const from = L.mobile
        ? { x: evidenceEdge.x + (k - 1) * 22, y: evidenceEdge.y }
        : { x: evidenceEdge.x, y: evidenceEdge.y + (k - 1) * 16 };
      this.signal(ctx, from, { x: L.core.x - (L.mobile ? 0 : 44), y: L.core.y - (L.mobile ? 18 : 0) }, intake, reduced, PURPLE, 0.35, k * 0.33);
    }

    // Spokes from each evidence record to the finding it supports.
    ctx.lineWidth = 0.7;
    for (const p of P) {
      if (p.finding < 0 || p.w < 0.35) continue;
      const c = this.findingCenter(p.finding);
      const dim = hoverFinding >= 0 && hoverFinding !== p.finding ? 0.4 : 1;
      ctx.strokeStyle = `rgba(${PURPLE}, ${0.16 * smooth(0.35, 0.9, p.w) * dim})`;
      ctx.beginPath();
      ctx.moveTo(c.x, c.y);
      ctx.lineTo(p.sx, p.sy);
      ctx.stroke();
    }

    // SAT-SA correlates evidence into findings.
    FINDINGS.forEach((def, i) => {
      const fa = this.findingAlpha(i);
      const c = this.findingCenter(i);
      const dim = hoverFinding >= 0 && hoverFinding !== i ? 0.4 : 1;
      const start = L.mobile ? { x: L.core.x, y: L.core.y + 18 } : { x: L.core.x + 44, y: L.core.y };
      const end = L.mobile ? { x: c.x, y: c.y - 30 * L.clusterScale } : { x: c.x - 48 * L.clusterScale, y: c.y };
      this.signal(ctx, start, end, fa * dim, reduced, PURPLE, 0.28, i * 0.21);
    });

    // Prioritised review, then the human examiner.
    const pri = smooth(0.7, 0.9, a);
    FINDINGS.forEach((def, i) => {
      const c = this.findingCenter(i);
      const weight = 1 - i * 0.2;
      const dim = hoverFinding >= 0 && hoverFinding !== i ? 0.4 : 1;
      const start = L.mobile ? { x: c.x, y: c.y + 44 * L.clusterScale + 18 } : { x: c.x + 52 * L.clusterScale, y: c.y };
      const end = L.mobile ? { x: L.review.x, y: L.review.y - 14 } : { x: L.review.x - 20, y: L.review.y };
      this.signal(ctx, start, end, pri * weight * dim, reduced, PURPLE, 0.22, 0.1 + i * 0.17);
    });
    const exam = smooth(0.84, 0.97, a);
    const rs = L.mobile ? { x: L.review.x + 18, y: L.review.y } : { x: L.review.x, y: L.review.y + 20 };
    const re = L.mobile ? { x: L.examiner.x - 16, y: L.examiner.y } : { x: L.examiner.x, y: L.examiner.y - 18 };
    this.signal(ctx, rs, re, exam, reduced, PURPLE, 0.18, 0);
  }

  private drawParticle(ctx: CanvasRenderingContext2D, p: Particle, alpha: number) {
    const r = (1.5 + p.depth * 0.55) * (this.layout.mobile ? 0.9 : 1) * (1 + p.w * 0.15);
    const rgb = CATEGORY_RGB[p.cat];
    const badge = r * 1.95;
    ctx.fillStyle = `rgba(255, 255, 255, ${Math.min(1, alpha * 1.6)})`;
    ctx.strokeStyle = `rgba(${rgb}, ${alpha * 0.7})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(p.sx, p.sy, badge, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = `rgba(${rgb}, ${alpha})`;
    ctx.strokeStyle = `rgba(${rgb}, ${alpha})`;
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    switch (p.cat) {
      case "alert":
        ctx.arc(p.sx, p.sy, r, 0, Math.PI * 2);
        ctx.fill();
        break;
      case "case":
        ctx.rect(p.sx - r * 0.9, p.sy - r * 0.9, r * 1.8, r * 1.8);
        ctx.fill();
        break;
      case "investigation":
        ctx.arc(p.sx, p.sy, r * 1.05, 0, Math.PI * 2);
        ctx.stroke();
        break;
      case "escalation":
        ctx.moveTo(p.sx, p.sy - r * 1.3);
        ctx.lineTo(p.sx + r * 1.3, p.sy);
        ctx.lineTo(p.sx, p.sy + r * 1.3);
        ctx.lineTo(p.sx - r * 1.3, p.sy);
        ctx.closePath();
        ctx.fill();
        break;
      case "asset":
        ctx.moveTo(p.sx, p.sy - r * 1.2);
        ctx.lineTo(p.sx + r * 1.15, p.sy + r * 0.9);
        ctx.lineTo(p.sx - r * 1.15, p.sy + r * 0.9);
        ctx.closePath();
        ctx.stroke();
        break;
    }
  }

  private drawFindingMarks(ctx: CanvasRenderingContext2D, a: number, reduced: boolean, hoverFinding: number) {
    const L = this.layout;
    const P = this.particles;
    const s = L.clusterScale;
    ctx.font = `600 ${L.font}px ${this.monoFont}`;

    FINDINGS.forEach((def, i) => {
      const fa = this.findingAlpha(i);
      if (fa < 0.02) return;
      const c = this.findingCenter(i);
      const accent = def.attention ? ORANGE : BLUE;
      const emphasis = hoverFinding === i ? 1 : hoverFinding >= 0 ? 0.5 : 0.85;

      if (def.kind === "gap") {
        const alertP = P.find((p) => p.finding === i && p.role === "gapAlert");
        const closedP = P.find((p) => p.finding === i && p.role === "gapClosed");
        if (alertP && closedP) {
          const inv = { x: c.x - 4 * s, y: c.y - 20 * s };
          const esc = { x: c.x + 24 * s, y: c.y - 16 * s };
          ctx.setLineDash([2, 3]);
          ctx.strokeStyle = `rgba(${INK}, ${0.35 * fa})`;
          ctx.lineWidth = 0.9;
          ctx.beginPath();
          ctx.moveTo(alertP.sx, alertP.sy);
          ctx.lineTo(inv.x, inv.y);
          ctx.lineTo(esc.x, esc.y);
          ctx.stroke();
          [inv, esc].forEach((g) => {
            ctx.beginPath();
            ctx.arc(g.x, g.y, 4 * s + 1, 0, Math.PI * 2);
            ctx.stroke();
          });
          ctx.setLineDash([]);
          ctx.strokeStyle = `rgba(${ORANGE}, ${0.9 * fa})`;
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(alertP.sx, alertP.sy);
          ctx.quadraticCurveTo(c.x - 2 * s, c.y + 14 * s, closedP.sx, closedP.sy);
          ctx.stroke();
          if (!L.mobile) {
            ctx.font = `500 ${L.font - 2}px ${this.monoFont}`;
            this.setSpacing(ctx, 1);
            this.label(ctx, "CLOSED", closedP.sx + 8, closedP.sy + 1, `rgba(${ORANGE}, ${0.85 * fa})`, "left");
            ctx.font = `600 ${L.font}px ${this.monoFont}`;
          }
        }
      }

      if (def.kind === "negative") {
        const ghost = this.negativeEmptySlot(i);
        ctx.strokeStyle = `rgba(${INK}, ${0.28 * fa})`;
        ctx.lineWidth = 0.9;
        const slots = L.mobile ? 5 : 6;
        const emptyAngle = -Math.PI / 2 + ((L.mobile ? 1 : 2) * Math.PI * 2) / slots;
        const gapHalf = 0.34;
        ctx.beginPath();
        ctx.ellipse(c.x, c.y, 26 * s, 22 * s, 0, emptyAngle + gapHalf, emptyAngle - gapHalf + Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([2, 2.5]);
        ctx.strokeStyle = `rgba(${ORANGE}, ${0.75 * fa})`;
        ctx.beginPath();
        ctx.arc(ghost.x, ghost.y, 4.2 * s + 1, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = `rgba(${ORANGE}, ${0.95 * fa})`;
        ctx.beginPath();
        ctx.arc(ghost.x, ghost.y, 1.4, 0, Math.PI * 2);
        ctx.fill();
      }

      if (def.kind === "anomaly") {
        const o = P.find((p) => p.finding === i && p.role === "outlier");
        if (o) {
          ctx.strokeStyle = `rgba(${ORANGE}, ${0.85 * fa})`;
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(o.sx, o.sy, 6.5 * s + 1, 0, Math.PI * 2);
          ctx.stroke();
          ctx.setLineDash([2, 3]);
          ctx.strokeStyle = `rgba(${INK}, ${0.22 * fa})`;
          ctx.lineWidth = 0.9;
          ctx.beginPath();
          ctx.arc(c.x, c.y, 16 * s, 0, Math.PI * 2);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }

      if (def.kind === "peer") {
        const o = P.find((p) => p.finding === i && p.role === "peerOffset");
        if (o) {
          const count = L.mobile ? 4 : 6;
          const half = ((count - 1) * 15 * s) / 2 + 6 * s;
          ctx.strokeStyle = `rgba(${BLUE}, ${0.4 * fa})`;
          ctx.lineWidth = 0.9;
          ctx.beginPath();
          ctx.moveTo(c.x - half, c.y + 6 * s);
          ctx.lineTo(c.x + half, c.y + 6 * s);
          ctx.stroke();
          ctx.setLineDash([2, 2]);
          ctx.beginPath();
          ctx.moveTo(o.sx, o.sy + 4);
          ctx.lineTo(o.sx, c.y + 6 * s);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.strokeStyle = `rgba(${BLUE}, ${0.85 * fa})`;
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(o.sx, o.sy, 6 * s + 1, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      if (this.pulses[i] >= 0 && !reduced) {
        const t = (this.time - this.pulses[i]) / 1.1;
        if (t >= 0 && t <= 1) {
          ctx.strokeStyle = `rgba(${accent}, ${0.45 * (1 - t)})`;
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(c.x, c.y, (38 + t * 34) * s, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      this.setSpacing(ctx, 1.4);
      const text = L.mobile ? def.short : def.label;
      const ly = L.mobile ? c.y + 44 * s + 8 : c.y + 50 * s;
      this.label(ctx, text, c.x, ly, `rgba(${accent}, ${fa * emphasis})`, "center");
      this.setSpacing(ctx, 0);
    });
  }

  private drawCore(ctx: CanvasRenderingContext2D, a: number) {
    const L = this.layout;
    const c = L.core;
    const w = L.mobile ? 74 : 88;
    const h = L.mobile ? 34 : 40;
    const active = smooth(0.12, 0.3, a) * (1 - smooth(0.88, 0.97, a));
    const ready = smooth(0.88, 0.97, a);

    if (active > 0.02) {
      ctx.strokeStyle = `rgba(${PURPLE}, ${0.35 * active})`;
      ctx.lineWidth = 1.2;
      const start = this.time * 1.6;
      ctx.beginPath();
      ctx.ellipse(c.x, c.y, w * 0.72, h * 0.95, 0, start, start + Math.PI * 0.7);
      ctx.stroke();
    }

    ctx.fillStyle = "rgba(255, 255, 255, 0.94)";
    ctx.strokeStyle = `rgba(${lerpRgb(a)}, ${0.22 + 0.4 * smooth(0.2, 0.9, a)})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    roundRect(ctx, c.x - w / 2, c.y - h / 2, w, h, 6);
    ctx.fill();
    ctx.stroke();

    ctx.font = `700 ${L.font + 2}px ${this.monoFont}`;
    this.setSpacing(ctx, 2);
    const textY = active > 0.02 || ready > 0.02 ? c.y - 5 : c.y;
    this.label(ctx, "SAT·SA", c.x, textY, `rgba(${INK}, 0.92)`, "center");
    this.setSpacing(ctx, 0);

    if (active > 0.02) {
      for (let k = 0; k < 3; k++) {
        const on = (Math.floor(this.time * 3) % 3) === k ? 1 : 0.3;
        ctx.fillStyle = `rgba(${PURPLE}, ${active * on})`;
        ctx.beginPath();
        ctx.arc(c.x - 8 + k * 8, c.y + 10, 1.7, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    if (ready > 0.02) {
      ctx.font = `600 ${L.font - 2.5}px ${this.monoFont}`;
      this.setSpacing(ctx, 1);
      this.label(ctx, "FINDINGS READY", c.x, c.y + 10, `rgba(${PURPLE}, ${ready})`, "center");
      this.setSpacing(ctx, 0);
    }
  }

  private drawOutputs(ctx: CanvasRenderingContext2D, a: number) {
    const L = this.layout;
    const pri = smooth(0.72, 0.9, a);
    const exam = smooth(0.86, 0.98, a);
    const evid = smooth(0.3, 0.6, a);
    ctx.font = `600 ${L.font}px ${this.monoFont}`;
    this.setSpacing(ctx, 1.4);

    if (evid > 0.02) {
      const ly = L.evidence.y - (this.evidenceRows / 2) * L.rowGap - 16;
      this.label(ctx, "EVIDENCE", L.evidence.x, ly, `rgba(${INK}, ${0.55 * evid})`, "center");
    }

    if (pri > 0.02) {
      const r = L.review;
      const size = L.mobile ? 26 : 32;
      ctx.fillStyle = `rgba(255, 255, 255, ${0.95 * pri})`;
      ctx.strokeStyle = `rgba(${PURPLE}, ${0.75 * pri})`;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      roundRect(ctx, r.x - size / 2, r.y - size / 2, size, size, 5);
      ctx.fill();
      ctx.stroke();
      [1, 0.75, 0.52, 0.34].forEach((len, k) => {
        ctx.fillStyle = `rgba(${PURPLE}, ${(0.9 - k * 0.18) * pri})`;
        const bw = (size - 12) * len;
        ctx.fillRect(r.x - (size - 12) / 2, r.y - size / 2 + 7 + k * ((size - 14) / 4), bw, 2);
      });
      const text = L.mobile ? "REVIEW" : "PRIORITISED REVIEW";
      const ly = L.mobile ? r.y + size / 2 + 12 : r.y - size / 2 - 14;
      this.label(ctx, text, r.x, ly, `rgba(${PURPLE}, ${pri})`, "center");
    }

    if (exam > 0.02) {
      const e = L.examiner;
      const rad = L.mobile ? 15 : 18;
      ctx.fillStyle = `rgba(255, 255, 255, ${0.96 * exam})`;
      ctx.strokeStyle = `rgba(${INK}, ${0.85 * exam})`;
      ctx.lineWidth = 1.3;
      ctx.beginPath();
      ctx.arc(e.x, e.y, rad, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(e.x, e.y - rad * 0.22, rad * 0.26, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(e.x, e.y + rad * 0.62, rad * 0.46, Math.PI * 1.08, Math.PI * 1.92);
      ctx.stroke();
      const settle = smooth(0.95, 1, a);
      if (settle > 0) {
        ctx.strokeStyle = `rgba(${PURPLE}, ${0.25 * settle})`;
        ctx.beginPath();
        ctx.arc(e.x, e.y, rad + 6, 0, Math.PI * 2);
        ctx.stroke();
      }
      const ly = e.y + rad + 14;
      this.label(ctx, L.mobile ? "EXAMINER" : "HUMAN EXAMINER", e.x, ly, `rgba(${INK}, ${0.9 * exam})`, "center");
      if (!L.mobile) {
        ctx.font = `500 ${L.font - 1.5}px ${this.monoFont}`;
        this.label(ctx, "DECIDES", e.x, ly + 14, `rgba(${INK}, ${0.5 * exam})`, "center");
      }
    }
    this.setSpacing(ctx, 0);
  }
}

function lerpRgb(a: number) {
  return a > 0.5 ? PURPLE : INK;
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
