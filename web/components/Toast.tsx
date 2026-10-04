"use client";
import { useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { cx } from "./ui";

export function Toast() {
  const toast = useStore((s) => s.toast);
  return toast ? <ToastMsg key={toast.id} msg={toast.msg} /> : null;
}

function ToastMsg({ msg }: { msg: string }) {
  const [show, setShow] = useState(true);
  useEffect(() => {
    const h = setTimeout(() => setShow(false), Math.max(2800, msg.length * 45));
    return () => clearTimeout(h);
  }, [msg]);
  return (
    <div role="status" className={cx(
      "pointer-events-none fixed bottom-6 left-1/2 z-50 max-w-[80vw] -translate-x-1/2 rounded-lg bg-ink px-4 py-2.5 text-[13.5px] text-white transition-all",
      show ? "translate-y-0 opacity-100" : "translate-y-5 opacity-0",
    )}>
      {msg}
    </div>
  );
}
