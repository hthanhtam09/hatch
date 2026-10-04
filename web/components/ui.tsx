"use client";
import { useId, type ButtonHTMLAttributes, type ReactNode } from "react";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export { cx };

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "primary" | "ghost" | "danger" | "accent"; size?: "sm" | "md"; block?: boolean;
};
export function Button({ variant = "default", size = "md", block, className, ...rest }: BtnProps) {
  return (
    <button
      type="button"
      {...rest}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border font-bold transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        size === "sm" ? "px-2.5 py-1 text-[12.5px]" : "px-3 py-1.5",
        block && "w-full",
        variant === "primary" && "border-ink bg-ink text-white hover:bg-black",
        variant === "default" && "border-line2 bg-white text-ink hover:border-ink",
        variant === "ghost" && "border-transparent bg-transparent hover:bg-soft",
        variant === "danger" && "border-line2 bg-white text-bad hover:border-bad",
        variant === "accent" && "border-accent bg-accent text-white",
        className,
      )}
    />
  );
}

export function Section({ title, children, className }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={cx("border-b border-line px-4 py-3.5", className)}>
      {title && <h3 className="mb-2.5 text-xs font-bold uppercase tracking-wider text-muted">{title}</h3>}
      {children}
    </section>
  );
}

export function Hint({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cx("mt-1 text-xs text-muted", className)}>{children}</p>;
}

export function Slider({
  label, value, min, max, step, format, onChange, onCommit, hint,
}: {
  label: string; value: number; min: number; max: number; step: number; format?: (v: number) => string;
  onChange?: (v: number) => void; onCommit?: (v: number) => void; hint?: ReactNode;
}) {
  const id = useId();
  return (
    <div className="my-2.5">
      <label htmlFor={id} className="mb-1 flex items-baseline justify-between gap-2 text-[13px]">
        {label}
        <output className="text-[12.5px] tabular-nums text-muted">{format ? format(value) : value}</output>
      </label>
      <input
        id={id} type="range" className="w-full" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange?.(parseFloat(e.target.value))}
        onPointerUp={(e) => onCommit?.(parseFloat((e.target as HTMLInputElement).value))}
        onKeyUp={(e) => onCommit?.(parseFloat((e.target as HTMLInputElement).value))}
      />
      {hint && <Hint>{hint}</Hint>}
    </div>
  );
}

export function Check({
  label, sub, checked, onChange,
}: { label: ReactNode; sub?: ReactNode; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="my-2 flex cursor-pointer items-start gap-2.5 text-[13px]">
      <input type="checkbox" className="mt-0.5 size-4 flex-none" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        {label}
        {sub && <small className="block text-xs text-muted">{sub}</small>}
      </span>
    </label>
  );
}

export function Seg<T extends string | number>({
  options, value, onChange, className, dark,
}: { options: { value: T; label: ReactNode; title?: string }[]; value: T; onChange: (v: T) => void; className?: string; dark?: boolean }) {
  return (
    <div className={cx("flex overflow-hidden rounded-lg border border-line2 bg-white", className)} role="group">
      {options.map((o, i) => (
        <button
          key={String(o.value)} type="button" title={o.title} aria-pressed={o.value === value} onClick={() => onChange(o.value)}
          className={cx(
            "flex-1 whitespace-nowrap px-2.5 py-1.5 text-[12.5px] text-ink",
            i > 0 && "border-l border-line",
            o.value === value && "bg-ink text-white",
            dark && o.value !== value && "hover:bg-soft",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function TextField({
  label, value, onChange, placeholder, type = "text", multiline,
}: { label: string; value: string | number; onChange: (v: string) => void; placeholder?: string; type?: string; multiline?: boolean }) {
  const id = useId();
  const cls = "w-full rounded-md border border-line2 bg-white px-2.5 py-1.5 focus:border-ink focus:outline-none";
  return (
    <div className="my-2.5">
      <label htmlFor={id} className="mb-1 block text-[13px]">{label}</label>
      {multiline ? (
        <textarea id={id} rows={6} className={cx(cls, "resize-y")} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input id={id} type={type} className={cls} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
      )}
    </div>
  );
}

export function Legend({ items }: { items: [string, string][] }) {
  return (
    <div className="flex flex-wrap gap-3.5 text-xs text-white/85">
      {items.map(([color, text]) => (
        <span key={text} className="inline-flex items-center gap-1.5">
          <i className="inline-block w-3.5 border-t-2" style={{ borderColor: color }} />
          {text}
        </span>
      ))}
    </div>
  );
}

export function Kv({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px]">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted">{k}</dt>
          <dd className="text-right tabular-nums">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded border border-b-2 border-line2 bg-white px-1.5 font-sans text-[11px]">{children}</kbd>;
}
