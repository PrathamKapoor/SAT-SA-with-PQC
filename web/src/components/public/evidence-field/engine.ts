/**
 * SAT-SA evidence field.
 *
 * One set of evidence records whose positions are governed by a single
 * measurable quantity, `order` in [0, 1] (chaos = 1 - order):
 *
 *   0.00  fragmented records, loose and spurious relationships
 *   0.25  related records begin to attract; noise links weaken
 *   0.50  correlated clusters form; noise moves to the periphery
 *   0.70  each cluster resolves into a finding with its evidence gap
 *   0.85  risk and attention marks appear on the findings that matter
 *   0.95  findings route to supervisory review
 *
 * Nothing is swapped or cross-faded: every record springs from a wandering
 * "chaos" position toward a structured one. Pointer activity raises the
 * global order and locally accelerates the records near the pointer.
 */

export type Kind = "alert" | "case" | "investigation" | "escalation" | "asset";

type Tone = "attention" | "info" | "critical";

interface ClusterDef {
  label: string;
  /** centre in normalized layout space (0..1) */
  cx: number;
  cy: number;
  tone: Tone;
  /** risk marks shown at high order: 1..3 */
  risk: number;
  annotation: string;
  /** hover text for the cluster key record */
  keyText: string;
}

interface Rec {
  kind: Kind;
  cluster: number; // -1 = noise
  /** structured offset in cluster radii */
  ox: number;
  oy: number;
  role: "member" | "key" | "outlier" | "deviant";
  /** chaos home, normalized 0..1 */
  hx: number;
  hy: number;
  phase: number;
  speed: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  boost: number;
  stagger: number;
}

interface Link {
  a: number;
  b: number;
  kind: "relation" | "noise";
}

export interface FieldPointer {
  x: number;
  y: number;
  inside: boolean;
}

export const STAGES = ["Evidence", "Relationships", "Analysis", "Finding", "Review"] as const;
export type Stage = (typeof STAGES)[number];

export function stageFor(order: number): Stage {
  if (order < 0.2) return "Evidence";
  if (order < 0.45) return "Relationships";
  if (order < 0.68) return "Analysis";
  if (order < 0.88) return "Finding";
  return "Review";
}

const C = {
  ink: "12, 18, 34",
  muted: "103, 111, 130",
  line: "196, 202, 214",
  brand: "82, 54, 201",
  info: "29, 89, 201",
  attention: "180, 83, 9",
  critical: "180, 35, 24",
};
const TONE_RGB: Record<Tone, string> = { attention: C.attention, info: C.info, critical: C.critical };

const CLUSTERS: ClusterDef[] = [
  { label: "EXECUTION GAP", cx: 0.3, cy: 0.3, tone: "attention", risk: 3, annotation: "NO ESCALATION", keyText: "closed, no escalation" },
  { label: "NEGATIVE SPACE", cx: 0.68, cy: 0.24, tone: "attention", risk: 2, annotation: "0 ALERTS", keyText: "critical, no alerts" },
  { label: "ANOMALY", cx: 0.32, cy: 0.72, tone: "info", risk: 2, annotation: "OUTLIER", keyText: "case" },
  { label: "PEER DEVIATION", cx: 0.68, cy: 0.7, tone: "info", risk: 1, annotation: "PEER MEDIAN", keyText: "peer" },
];
const REVIEW = { x: 0.94, y: 0.48 };

const clamp = (v: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const smooth = (lo: number, hi: number, v: number) => {
  const t = clamp((v - lo) / (hi - lo));
  return t * t * (3 - 2 * t);
};
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

function rng(seed: number) {
  let s = seed | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** The structured shape of each finding, in cluster radii. */
function clusterMembers(): Array<Omit<Rec, "hx" | "hy" | "phase" | "speed" | "x" | "y" | "vx" | "vy" | "boost" | "stagger">> {
  const m: ReturnType<typeof clusterMembers> = [];
  const add = (cluster: number, kind: Kind, ox: number, oy: number, role: Rec["role"] = "member") => m.push({ kind, cluster, ox, oy, role });
  // 0 execution gap: three critical alerts closed through one case, one thin investigation, no escalation
  add(0, "alert", -1.35, -0.75);
  add(0, "alert", -1.35, 0);
  add(0, "alert", -1.35, 0.75);
  add(0, "case", 0, 0, "key");
  add(0, "investigation", -0.2, 0.95);
  // 1 negative space: a critical asset with no alerts, beside monitored assets
  add(1, "asset", 0, 0, "key");
  add(1, "asset", -1.45, 0.55);
  add(1, "alert", -1.45, -0.45);
  add(1, "asset", 1.45, 0.55);
  add(1, "alert", 1.45, -0.45);
  // 2 anomaly: a tight run of cases and one far outlier
  for (let i = 0; i < 5; i++) add(2, "case", -1.2 + i * 0.5, 0.35);
  add(2, "case", 1.35, -0.85, "outlier");
  // 3 peer deviation: peers on a baseline, one entity well below it
  for (let i = 0; i < 5; i++) add(3, "alert", -1.2 + i * 0.6, -0.25);
  add(3, "alert", 0.4, 0.95, "deviant");
  add(3, "escalation", -0.9, 0.95);
  return m;
}

const NOISE_KINDS: Kind[] = ["alert", "alert", "case", "investigation", "escalation", "asset"];

export class EvidenceField {
  private recs: Rec[] = [];
  private links: Link[] = [];
  private w = 1;
  private h = 1;
  private r = 20;
  private time = 0;
  private hover = -1;
  /** right edge and vertical centre of each finding frame, updated while drawing */
  private frames: Array<{ right: number; cy: number }> = [];
  order = 0;
  target = 0;

  constructor(
    width: number,
    height: number,
    private density: "full" | "medium" | "compact" = "full",
    private seed = 26157,
  ) {
    this.resize(width, height);
    this.build();
  }

  resize(width: number, height: number) {
    this.w = Math.max(1, width);
    this.h = Math.max(1, height);
    this.r = Math.min(this.w, this.h) * (this.density === "compact" ? 0.058 : 0.072);
  }

  private build() {
    const rand = rng(this.seed);
    const noiseCount = this.density === "full" ? 46 : this.density === "medium" ? 30 : 18;
    const members = clusterMembers();
    const spread = () => ({ hx: 0.06 + rand() * 0.88, hy: 0.08 + rand() * 0.84 });
    for (const m of members) {
      const home = spread();
      this.recs.push({ ...m, ...home, phase: rand() * Math.PI * 2, speed: 0.25 + rand() * 0.35, x: 0, y: 0, vx: 0, vy: 0, boost: 0, stagger: rand() * 0.18 });
    }
    for (let i = 0; i < noiseCount; i++) {
      const home = spread();
      const angle = rand() * Math.PI * 2;
      this.recs.push({
        kind: NOISE_KINDS[Math.floor(rand() * NOISE_KINDS.length)],
        cluster: -1,
        ox: Math.cos(angle),
        oy: Math.sin(angle),
        role: "member",
        ...home,
        phase: rand() * Math.PI * 2,
        speed: 0.2 + rand() * 0.4,
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        boost: 0,
        stagger: 0.1 + rand() * 0.2,
      });
    }
    for (const r of this.recs) {
      r.x = r.hx * this.w;
      r.y = r.hy * this.h;
    }
    // real relationships inside each finding
    const byCluster = (c: number) => this.recs.map((r, i) => (r.cluster === c ? i : -1)).filter((i) => i >= 0);
    const [g0, g1, g2, g3] = [0, 1, 2, 3].map(byCluster);
    const key0 = g0.find((i) => this.recs[i].role === "key")!;
    for (const i of g0) if (i !== key0) this.links.push({ a: i, b: key0, kind: "relation" });
    const key1 = g1.find((i) => this.recs[i].role === "key")!;
    this.links.push({ a: g1[1], b: g1[2], kind: "relation" }, { a: g1[3], b: g1[4], kind: "relation" }, { a: g1[1], b: key1, kind: "relation" }, { a: key1, b: g1[3], kind: "relation" });
    for (let k = 0; k < 4; k++) this.links.push({ a: g2[k], b: g2[k + 1], kind: "relation" });
    this.links.push({ a: g2[2], b: g2[5], kind: "relation" });
    for (let k = 0; k < 4; k++) this.links.push({ a: g3[k], b: g3[k + 1], kind: "relation" });
    this.links.push({ a: g3[2], b: g3[5], kind: "relation" }, { a: g3[6], b: g3[0], kind: "relation" });
    // spurious relationships that analysis rejects
    const n = this.recs.length;
    // tentative links between records that merely start near each other
    let made = 0;
    for (let tries = 0; tries < n * 12 && made < Math.round(n * 0.6); tries++) {
      const a = Math.floor(rand() * n);
      const b = Math.floor(rand() * n);
      const A = this.recs[a];
      const B = this.recs[b];
      if (a !== b && Math.hypot(A.hx - B.hx, A.hy - B.hy) < 0.22) {
        this.links.push({ a, b, kind: "noise" });
        made++;
      }
    }
  }

  /** Compact layouts pull the two columns inward to leave room for review. */
  private layoutCenter(c: number) {
    const def = CLUSTERS[c];
    const cx = this.density === "compact" ? (def.cx < 0.5 ? 0.24 : 0.62) : def.cx;
    return { x: cx * this.w, y: def.cy * this.h };
  }

  private structured(r: Rec) {
    if (r.cluster >= 0) {
      const c = this.layoutCenter(r.cluster);
      return { x: c.x + r.ox * this.r, y: c.y + r.oy * this.r };
    }
    // noise settles on a quiet outer band
    const cx = this.w * 0.5;
    const cy = this.h * 0.5;
    return { x: cx + r.ox * this.w * 0.49, y: cy + r.oy * this.h * 0.47 };
  }

  private chaos(r: Rec) {
    const t = this.time * r.speed;
    const amp = Math.min(this.w, this.h) * 0.035;
    return { x: r.hx * this.w + Math.sin(t + r.phase) * amp, y: r.hy * this.h + Math.cos(t * 0.8 + r.phase * 1.3) * amp };
  }

  /** Effective order for one record: global order plus a local pull near the pointer. */
  private local(r: Rec) {
    return clamp((this.order - r.stagger * (1 - this.order)) / (1 - r.stagger * 0.5) + r.boost * 0.45);
  }

  step(dt: number, pointer: FieldPointer, reduced: boolean) {
    const d = Math.min(0.05, dt);
    this.time += reduced ? 0 : d;
    this.order += (this.target - this.order) * (reduced ? 1 : 1 - Math.exp(-d * 2.2));
    const sigma = Math.min(this.w, this.h) * 0.2;
    let nearest = -1;
    let best = 16 * 16;
    for (let i = 0; i < this.recs.length; i++) {
      const r = this.recs[i];
      const want = pointer.inside ? Math.exp(-((r.x - pointer.x) ** 2 + (r.y - pointer.y) ** 2) / (2 * sigma * sigma)) : 0;
      r.boost += (want - r.boost) * (1 - Math.exp(-d * (want > r.boost ? 5 : 1.2)));
      const e = smooth(0, 1, this.local(r));
      const a = this.chaos(r);
      const b = this.structured(r);
      const tx = lerp(a.x, b.x, e);
      const ty = lerp(a.y, b.y, e);
      if (reduced) {
        r.x = tx;
        r.y = ty;
      } else {
        // critically damped spring toward the target
        const k = 26;
        const damp = 2 * Math.sqrt(k) * 0.95;
        r.vx += ((tx - r.x) * k - r.vx * damp) * d;
        r.vy += ((ty - r.y) * k - r.vy * damp) * d;
        r.x += r.vx * d;
        r.y += r.vy * d;
      }
      if (pointer.inside) {
        const dd = (r.x - pointer.x) ** 2 + (r.y - pointer.y) ** 2;
        if (dd < best) {
          best = dd;
          nearest = i;
        }
      }
    }
    this.hover = nearest;
  }

  /** Human-readable description of the hovered record, or null. */
  hovered(): { x: number; y: number; text: string } | null {
    if (this.hover < 0) return null;
    const r = this.recs[this.hover];
    const kind = r.kind.toUpperCase();
    if (r.cluster < 0) return { x: r.x, y: r.y, text: this.order > 0.5 ? `${kind} · unrelated` : kind };
    const detail =
      this.order > 0.55
        ? r.role === "key"
          ? CLUSTERS[r.cluster].keyText
          : r.role === "outlier"
            ? "outlier"
            : r.role === "deviant"
              ? "below peers"
              : CLUSTERS[r.cluster].label.toLowerCase()
        : "";
    return { x: r.x, y: r.y, text: detail ? `${kind} · ${detail}` : kind };
  }

  draw(ctx: CanvasRenderingContext2D, reduced: boolean) {
    const o = this.order;
    ctx.clearRect(0, 0, this.w, this.h);
    const font = (size: number, weight = 500) => `${weight} ${size}px var(--font-geist-mono), ui-monospace, monospace`;

    // spurious links weaken; real ones strengthen
    for (const l of this.links) {
      const A = this.recs[l.a];
      const B = this.recs[l.b];
      let alpha: number;
      let rgb = C.line;
      let width = 1;
      if (l.kind === "noise") {
        alpha = 0.55 * (1 - smooth(0.05, 0.55, o));
        if (alpha < 0.01) continue;
      } else {
        const e = Math.min(this.local(A), this.local(B));
        alpha = 0.18 + 0.62 * smooth(0.1, 0.6, e);
        if (e > 0.55) {
          rgb = A.cluster >= 0 ? TONE_RGB[CLUSTERS[A.cluster].tone] : C.ink;
          width = 1.1;
        }
      }
      ctx.strokeStyle = `rgba(${rgb}, ${alpha})`;
      ctx.lineWidth = width;
      ctx.beginPath();
      ctx.moveTo(A.x, A.y);
      ctx.lineTo(B.x, B.y);
      ctx.stroke();
    }

    // finding frames and their evidence annotations
    const frameA = smooth(0.55, 0.78, o);
    for (let c = 0; c < CLUSTERS.length; c++) {
      if (frameA <= 0.01) break;
      const def = CLUSTERS[c];
      const members = this.recs.filter((r) => r.cluster === c);
      const pad = this.r * 0.7;
      let x0 = Infinity,
        y0 = Infinity,
        x1 = -Infinity,
        y1 = -Infinity;
      for (const m of members) {
        x0 = Math.min(x0, m.x);
        y0 = Math.min(y0, m.y);
        x1 = Math.max(x1, m.x);
        y1 = Math.max(y1, m.y);
      }
      x0 -= pad;
      y0 -= pad;
      x1 += pad;
      y1 += pad;
      this.frames[c] = { right: x1, cy: (y0 + y1) / 2 };
      const rgb = TONE_RGB[def.tone];
      // hairline frame with corner ticks, not a box
      ctx.strokeStyle = `rgba(${C.ink}, ${0.14 * frameA})`;
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 3]);
      ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
      ctx.setLineDash([]);
      ctx.strokeStyle = `rgba(${C.ink}, ${0.55 * frameA})`;
      const t = 6;
      for (const [cx, cy, sx, sy] of [
        [x0, y0, 1, 1],
        [x1, y0, -1, 1],
        [x0, y1, 1, -1],
        [x1, y1, -1, -1],
      ] as const) {
        ctx.beginPath();
        ctx.moveTo(cx + sx * t, cy);
        ctx.lineTo(cx, cy);
        ctx.lineTo(cx, cy + sy * t);
        ctx.stroke();
      }
      // label
      ctx.font = font(this.density === "compact" ? 9 : 10, 600);
      ctx.textBaseline = "bottom";
      ctx.fillStyle = `rgba(${C.ink}, ${0.85 * frameA})`;
      ctx.fillText(`FINDING · ${def.label}`, x0, y0 - 5);
      // risk marks
      const riskA = smooth(0.78, 0.9, o);
      if (riskA > 0.01) {
        const lw = ctx.measureText(`FINDING · ${def.label}`).width;
        for (let k = 0; k < 3; k++) {
          ctx.fillStyle = k < def.risk ? `rgba(${rgb}, ${riskA})` : `rgba(${C.line}, ${riskA})`;
          const bh = 4 + k * 2.5;
          ctx.fillRect(x0 + lw + 8 + k * 4, y0 - 6 - bh, 2.5, bh);
        }
      }
      this.drawAnnotation(ctx, c, members, frameA, rgb, font);
    }

    // records
    for (let i = 0; i < this.recs.length; i++) this.drawRec(ctx, this.recs[i], i === this.hover);

    // attention on the finding that matters most
    const attA = smooth(0.8, 0.92, o);
    if (attA > 0.01) {
      const key = this.recs.find((r) => r.cluster === 0 && r.role === "key")!;
      const pulse = reduced ? 0.5 : (Math.sin(this.time * 2.2) + 1) / 2;
      ctx.strokeStyle = `rgba(${C.attention}, ${attA * (0.55 - pulse * 0.35)})`;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(key.x, key.y, this.r * (0.55 + pulse * 0.35), 0, Math.PI * 2);
      ctx.stroke();
    }

    // supervisory review
    const revA = smooth(0.86, 0.98, o);
    if (revA > 0.01) {
      const rx = REVIEW.x * this.w;
      const ry = REVIEW.y * this.h;
      // each finding leaves its frame on the right, drops into the channel
      // between the two rows, and runs to review without crossing a frame
      for (let c = 0; c < CLUSTERS.length; c++) {
        const f = this.frames[c];
        if (!f) continue;
        const sx = f.right;
        const bend = Math.min(this.r * 1.1, 26);
        ctx.strokeStyle = `rgba(${C.brand}, ${0.4 * revA})`;
        ctx.setLineDash([3, 4]);
        ctx.lineDashOffset = reduced ? 0 : -this.time * 14;
        ctx.beginPath();
        ctx.moveTo(sx, f.cy);
        ctx.lineTo(sx + 8, f.cy);
        ctx.bezierCurveTo(sx + 8 + bend, f.cy, sx + 8 + bend, ry, sx + 8 + bend * 2, ry);
        ctx.lineTo(rx - 16, ry);
        ctx.stroke();
      }
      ctx.setLineDash([]);
      ctx.fillStyle = `rgba(255, 255, 255, ${revA})`;
      ctx.strokeStyle = `rgba(${C.brand}, ${revA})`;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.roundRect(rx - 16, ry - 16, 32, 32, 4);
      ctx.fill();
      ctx.stroke();
      ctx.strokeStyle = `rgba(${C.brand}, ${revA})`;
      ctx.lineWidth = 1.2;
      for (let k = 0; k < 3; k++) {
        ctx.beginPath();
        ctx.moveTo(rx - 8, ry - 6 + k * 6);
        ctx.lineTo(rx + (k === 2 ? 2 : 8), ry - 6 + k * 6);
        ctx.stroke();
      }
      ctx.font = font(10, 600);
      ctx.textAlign = "right";
      ctx.textBaseline = "top";
      this.text(ctx, "SUPERVISORY REVIEW", rx + 16, ry + 22, `rgba(${C.brand}, ${revA})`, revA);
      ctx.font = font(9.5, 500);
      this.text(ctx, "HUMAN DECIDES", rx + 16, ry + 36, `rgba(${C.muted}, ${revA})`, revA);
      ctx.textAlign = "left";
    }

    // hover annotation
    const h = this.hovered();
    if (h) {
      ctx.font = font(10, 600);
      const tw = ctx.measureText(h.text).width;
      const bx = Math.min(this.w - tw - 14, h.x + 10);
      const by = Math.max(4, h.y - 26);
      ctx.fillStyle = "rgba(255,255,255,0.92)";
      ctx.fillRect(bx - 5, by - 3, tw + 10, 17);
      ctx.strokeStyle = `rgba(${C.ink}, 0.2)`;
      ctx.strokeRect(bx - 5, by - 3, tw + 10, 17);
      ctx.fillStyle = `rgb(${C.ink})`;
      ctx.textBaseline = "top";
      ctx.fillText(h.text, bx, by + 1);
    }
  }

  /** Text with a white knockout so no line ever strikes through a label. */
  private text(ctx: CanvasRenderingContext2D, str: string, x: number, y: number, fill: string, alpha: number) {
    const w = ctx.measureText(str).width;
    const align = ctx.textAlign;
    const left = align === "center" ? x - w / 2 : align === "right" || align === "end" ? x - w : x;
    const base = ctx.textBaseline;
    const top = base === "top" ? y : base === "bottom" ? y - 11 : y - 6;
    ctx.fillStyle = `rgba(255, 255, 255, ${0.92 * alpha})`;
    ctx.fillRect(left - 3, top - 2, w + 6, 15);
    ctx.fillStyle = fill;
    ctx.fillText(str, x, y);
  }

  private drawAnnotation(
    ctx: CanvasRenderingContext2D,
    c: number,
    members: Rec[],
    a: number,
    rgb: string,
    font: (s: number, w?: number) => string,
  ) {
    const def = CLUSTERS[c];
    const key = members.find((m) => m.role === "key");
    ctx.font = font(this.density === "compact" ? 8.5 : 9.5, 600);
    ctx.textBaseline = "middle";
    if (c === 0 && key) {
      // the escalation that should exist, drawn where it is missing
      const x = key.x + this.r * 1.35;
      const y = key.y;
      ctx.strokeStyle = `rgba(${C.critical}, ${0.85 * a})`;
      ctx.setLineDash([2, 2]);
      ctx.beginPath();
      ctx.moveTo(key.x + 6, key.y);
      ctx.lineTo(x - 7, y);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x, y - 6);
      ctx.lineTo(x + 6, y + 5);
      ctx.lineTo(x - 6, y + 5);
      ctx.closePath();
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.textAlign = "center";
      this.text(ctx, def.annotation, x, y + 16, `rgba(${C.critical}, ${a})`, a);
      ctx.textAlign = "left";
    } else if (c === 1 && key) {
      // where alerts from the critical asset would be: none
      ctx.strokeStyle = `rgba(${rgb}, ${0.7 * a})`;
      ctx.setLineDash([2, 3]);
      ctx.beginPath();
      ctx.arc(key.x, key.y, this.r * 0.75, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.textAlign = "center";
      this.text(ctx, def.annotation, key.x, key.y + this.r * 1.2, `rgba(${rgb}, ${a})`, a);
      ctx.textAlign = "left";
    } else if (c === 2) {
      const out = members.find((m) => m.role === "outlier");
      if (out) {
        ctx.strokeStyle = `rgba(${rgb}, ${0.8 * a})`;
        ctx.beginPath();
        ctx.arc(out.x, out.y, 9, 0, Math.PI * 2);
        ctx.stroke();
        ctx.textAlign = "center";
        this.text(ctx, def.annotation, out.x, out.y - 17, `rgba(${rgb}, ${a})`, a);
        ctx.textAlign = "left";
      }
    } else if (c === 3) {
      const peers = members.filter((m) => m.role === "member" && m.kind === "alert");
      if (peers.length) {
        const y = peers.reduce((s, m) => s + m.y, 0) / peers.length;
        ctx.strokeStyle = `rgba(${rgb}, ${0.55 * a})`;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.moveTo(peers[0].x - 10, y);
        ctx.lineTo(peers[peers.length - 1].x + 10, y);
        ctx.stroke();
        ctx.setLineDash([]);
        this.text(ctx, def.annotation, peers[0].x - 8, y - 13, `rgba(${rgb}, ${a})`, a);
      }
    }
  }

  private drawRec(ctx: CanvasRenderingContext2D, r: Rec, hovered: boolean) {
    const o = this.order;
    const e = this.local(r);
    const noise = r.cluster < 0;
    const fade = noise ? 1 - 0.62 * smooth(0.3, 0.75, o) : 1;
    const settled = !noise && e > 0.6;
    const tone = r.cluster >= 0 ? TONE_RGB[CLUSTERS[r.cluster].tone] : C.muted;
    const important = settled && (r.role === "key" || r.role === "outlier" || r.role === "deviant");
    const rgb = important ? tone : noise ? C.muted : settled ? C.ink : r.kind === "alert" ? C.info : C.ink;
    const alpha = (noise ? 0.55 : 0.8) * fade * (hovered ? 1.25 : 1);
    const s = (r.role === "key" ? 5 : 3.6) * (hovered ? 1.4 : 1);
    ctx.fillStyle = `rgba(${rgb}, ${Math.min(1, alpha)})`;
    ctx.strokeStyle = `rgba(${rgb}, ${Math.min(1, alpha)})`;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    switch (r.kind) {
      case "alert":
        ctx.arc(r.x, r.y, s, 0, Math.PI * 2);
        ctx.fill();
        break;
      case "case":
        ctx.rect(r.x - s, r.y - s, s * 2, s * 2);
        ctx.fill();
        break;
      case "investigation":
        ctx.moveTo(r.x, r.y - s * 1.1);
        ctx.lineTo(r.x + s * 1.1, r.y);
        ctx.lineTo(r.x, r.y + s * 1.1);
        ctx.lineTo(r.x - s * 1.1, r.y);
        ctx.closePath();
        ctx.fill();
        break;
      case "escalation":
        ctx.moveTo(r.x, r.y - s * 1.15);
        ctx.lineTo(r.x + s * 1.1, r.y + s * 0.85);
        ctx.lineTo(r.x - s * 1.1, r.y + s * 0.85);
        ctx.closePath();
        ctx.stroke();
        break;
      case "asset":
        ctx.rect(r.x - s, r.y - s, s * 2, s * 2);
        ctx.stroke();
        break;
    }
  }
}
