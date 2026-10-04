"use client";
import { useEffect } from "react";
import { useStore, type Tab } from "@/lib/store";
import { cx } from "./ui";
import { Toast } from "./Toast";
import { DesignsView } from "./designs/DesignsView";
import { BookView } from "./book/BookView";
import { CoverView } from "./cover/CoverView";
import { useUploader } from "./designs/useUploader";

const STEPS: { tab: Tab; n: number; label: string }[] = [
  { tab: "designs", n: 1, label: "Tranh" },
  { tab: "book", n: 2, label: "Ruột sách" },
  { tab: "cover", n: 3, label: "Bìa" },
];

export function Studio() {
  const { proj, tab, setTab, saveState, load } = useStore();
  const { dragging } = useUploader();

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 flex-none items-center gap-4 border-b border-line bg-white px-4">
        <div className="flex items-center gap-2 whitespace-nowrap text-base font-bold">
          <svg width="24" height="24" viewBox="0 0 26 26" aria-hidden>
            <polygon points="2,24 13,2 24,24" fill="none" stroke="currentColor" strokeWidth="1.8" />
            <path d="M8 22l7-14M11 23l6-12M14 24l5-10" stroke="currentColor" />
          </svg>
          Hatch Studio
        </div>
        <nav className="ml-3 flex gap-1" role="tablist">
          {STEPS.map((s) => (
            <button
              key={s.tab} role="tab" aria-selected={tab === s.tab} onClick={() => setTab(s.tab)}
              className={cx(
                "flex items-center gap-2 rounded-lg px-3.5 py-2 font-bold",
                tab === s.tab ? "bg-soft text-ink" : "text-muted hover:text-ink",
              )}
            >
              <b className={cx(
                "grid size-[22px] place-items-center rounded-full border text-xs",
                tab === s.tab ? "border-ink bg-ink text-white" : "border-line2 bg-soft",
              )}>{s.n}</b>
              {s.label}
            </button>
          ))}
        </nav>
        <span className="ml-auto whitespace-nowrap text-[12.5px] text-muted">{saveState}</span>
      </header>

      <main className="relative min-h-0 flex-1">
        {!proj ? (
          <div className="grid h-full place-items-center text-muted">Đang kết nối máy chủ Python…</div>
        ) : tab === "designs" ? <DesignsView /> : tab === "book" ? <BookView /> : <CoverView />}
        {dragging && (
          <div className="pointer-events-none absolute inset-3 z-30 grid place-items-center rounded-2xl border-[3px] border-dashed border-white bg-black/30 text-xl font-bold text-white">
            Thả ảnh vào đây để thêm tranh
          </div>
        )}
      </main>
      <Toast />
    </div>
  );
}
