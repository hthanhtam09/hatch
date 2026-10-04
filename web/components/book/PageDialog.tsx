"use client";
import { useEffect, useRef, useState } from "react";
import { api, isAbort, lite } from "@/lib/api";
import { KIND_LABEL } from "@/lib/defaults";
import { useStore } from "@/lib/store";
import type { BookPlan } from "@/lib/types";
import { Button } from "../ui";

export function PageDialog({ n, total, plan, onNav, onClose }: {
  n: number; total: number; plan: BookPlan; onNav: (n: number) => void; onClose: () => void;
}) {
  const dlg = useRef<HTMLDialogElement>(null);
  const [shot, setShot] = useState<{ k: string; svg: string }>({ k: "", svg: "" });
  const [guides, setGuides] = useState(true);
  const p = plan.pages[n - 1];
  const name = p.kind === "design" ? useStore.getState().proj!.designs[p.i!]?.name : "";

  useEffect(() => { dlg.current?.showModal(); }, []);
  useEffect(() => {
    const ctrl = new AbortController();
    api.page(lite(useStore.getState().proj!), n, guides, ctrl.signal).then((r) => setShot({ k: `${n}|${guides}`, svg: r.svg }))
      .catch((e) => !isAbort(e) && useStore.getState().notify(e.message));
    return () => ctrl.abort();
  }, [n, guides]);

  return (
    <dialog
      ref={dlg} onClose={onClose}
      onKeyDown={(e) => { if (e.key === "ArrowLeft" && n > 1) onNav(n - 1); if (e.key === "ArrowRight" && n < total) onNav(n + 1); }}
      className="m-auto max-h-[94vh] max-w-[94vw] rounded-xl p-0 shadow-2xl backdrop:bg-black/55"
    >
      <div className="flex items-center justify-between gap-3 border-b border-line px-3.5 py-2.5">
        <b>Trang {n} / {total} · {KIND_LABEL[p.kind]}{p.kind === "design" ? ` ${p.i! + 1}: ${name}` : ""} · {p.side === "right" ? "trang phải" : "trang trái"}</b>
        <span className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-[13px]"><input type="checkbox" checked={guides} onChange={(e) => setGuides(e.target.checked)} /> Hiện lề in</label>
          <Button size="sm" disabled={n <= 1} onClick={() => onNav(n - 1)}>‹</Button>
          <Button size="sm" disabled={n >= total} onClick={() => onNav(n + 1)}>›</Button>
          <Button size="sm" onClick={() => dlg.current?.close()}>Đóng</Button>
        </span>
      </div>
      <div className="max-h-[calc(94vh-52px)] overflow-auto bg-stage p-4">
        <div className="mx-auto aspect-[8.625/11.25] w-[min(560px,80vw)] bg-white [&_svg]:h-auto [&_svg]:w-full" dangerouslySetInnerHTML={{ __html: shot.k === `${n}|${guides}` ? shot.svg : "" }} />
      </div>
    </dialog>
  );
}
