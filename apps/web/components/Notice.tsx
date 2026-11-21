import type { ReactNode } from "react";

type Tone = "info" | "warn" | "error" | "success";

export default function Notice({
  tone = "info",
  title,
  children,
  role,
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
  role?: "alert" | "status";
}) {
  return (
    <div className={`notice notice-${tone}`} role={role}>
      {title && <p className="notice-title">{title}</p>}
      {children}
    </div>
  );
}
