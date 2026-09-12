"use client";

import React from "react";
import {
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Clock,
  HelpCircle,
  ShieldAlert,
  ShieldCheck,
  Info,
} from "lucide-react";

export type StatusVariant =
  | "attention" // Amber: for attention required
  | "confirmed_concern" // Red: ONLY for confirmed serious concerns
  | "navigational" // Blue: for navigational context / pending samples
  | "verified" // Green: for verified PQC / compliant
  | "neutral"; // Grey: for baseline / informational

interface StatusBadgeProps {
  variant: StatusVariant;
  label: string;
  detail?: string;
  icon?: "alert-triangle" | "alert-circle" | "shield-alert" | "shield-check" | "check" | "clock" | "info" | "help";
  size?: "sm" | "md";
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  variant,
  label,
  detail,
  icon,
  size = "md",
  className = "",
}) => {
  const getIcon = () => {
    const iconClass = size === "sm" ? "size-3.5 shrink-0" : "size-4 shrink-0";
    if (icon === "alert-triangle") return <AlertTriangle className={iconClass} />;
    if (icon === "shield-alert") return <ShieldAlert className={iconClass} />;
    if (icon === "shield-check") return <ShieldCheck className={iconClass} />;
    if (icon === "check") return <CheckCircle2 className={iconClass} />;
    if (icon === "clock") return <Clock className={iconClass} />;
    if (icon === "info") return <Info className={iconClass} />;
    if (icon === "alert-circle") return <AlertCircle className={iconClass} />;
    if (icon === "help") return <HelpCircle className={iconClass} />;

    // Default icon per variant
    switch (variant) {
      case "attention":
        return <AlertTriangle className={iconClass} />;
      case "confirmed_concern":
        return <ShieldAlert className={iconClass} />;
      case "navigational":
        return <Info className={iconClass} />;
      case "verified":
        return <ShieldCheck className={iconClass} />;
      case "neutral":
      default:
        return <HelpCircle className={iconClass} />;
    }
  };

  const getVariantStyles = () => {
    switch (variant) {
      case "attention":
        return "bg-amber-500/10 text-amber-300 border-amber-500/30";
      case "confirmed_concern":
        return "bg-red-500/15 text-red-300 border-red-500/40 font-semibold";
      case "navigational":
        return "bg-blue-500/15 text-blue-300 border-blue-500/30";
      case "verified":
        return "bg-emerald-500/10 text-emerald-300 border-emerald-500/30";
      case "neutral":
      default:
        return "bg-slate-800/60 text-slate-300 border-slate-700/50";
    }
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono uppercase tracking-wider ${
        size === "sm" ? "text-[10px] leading-tight" : "text-xs leading-normal"
      } ${getVariantStyles()} ${className}`.trim()}
    >
      {getIcon()}
      <span>{label}</span>
      {detail && <span className="opacity-75 font-normal">· {detail}</span>}
    </span>
  );
};
