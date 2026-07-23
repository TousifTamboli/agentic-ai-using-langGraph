import * as React from "react";

import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "icon";
};

export function Button({ className, variant = "primary", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900 disabled:pointer-events-none disabled:opacity-50",
        variant === "primary" && "bg-zinc-950 text-white hover:bg-zinc-800",
        variant === "secondary" && "border border-zinc-200 bg-white text-zinc-950 hover:bg-zinc-100",
        variant === "ghost" && "text-zinc-700 hover:bg-zinc-100 hover:text-zinc-950",
        variant === "icon" && "h-9 w-9 rounded-md p-0 text-zinc-700 hover:bg-zinc-100",
        className,
      )}
      {...props}
    />
  );
}
