"use client";
import { useCallback, useEffect, useState } from "react";
import { useCurrent, useStore } from "@/lib/store";
import type { Edit } from "@/lib/types";
import { DesignRail } from "./DesignRail";
import { DesignPanel } from "./DesignPanel";
import { Stage, type View } from "./Stage";

export type FacetInfo = { lv: number; ang: number } | null;

export function DesignsView() {
  const item = useCurrent();
  const cur = useStore((s) => s.cur);
  const [view, setView] = useState<View>("page");
  const [edit, setEditRaw] = useState(false);
  const [sel, setSel] = useState<string | null>(null);
  const [merging, setMerging] = useState(false);
  const [info, setInfo] = useState<FacetInfo>(null);

  // doi tranh -> bo chon
  const [selFor, setSelFor] = useState(cur);
  if (selFor !== cur) { setSelFor(cur); setSel(null); setMerging(false); }

  const setEdit = useCallback((on: boolean) => {
    setEditRaw(on); setMerging(false);
    if (!on) setSel(null);
    if (on) setView((v) => (v === "key" ? "page" : v));
  }, []);

  const push = useCallback((op: Edit) => {
    const { cur, updateDesign } = useStore.getState();
    updateDesign(cur, (d) => { d.edits = [...d.edits, op]; });
  }, []);

  const actions = {
    level: (v: number) => { if (sel && info && info.lv !== v) push({ op: "level", id: sel, v }); },
    rotate: (dl: number) => { if (sel && info) push({ op: "angle", id: sel, v: (((info.ang + dl) % 180) + 180) % 180 }); },
    split: () => { if (sel) { push({ op: "split", id: sel }); setSel(sel + "a"); } },
    toggleMerge: () => { if (sel) setMerging((m) => !m); },
    undo: () => {
      const { cur, updateDesign } = useStore.getState();
      updateDesign(cur, (d) => { d.edits = d.edits.slice(0, -1); });
    },
  };

  const pick = (id: string) => {
    if (!edit) return;
    if (merging && sel && id !== sel) { setMerging(false); push({ op: "merge", a: sel, b: id }); return; }
    setMerging(false); setSel(id);
  };

  // phim tat
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.matches("input[type=text],input[type=number],textarea,select")) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") { e.preventDefault(); actions.undo(); return; }
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === "e") { if (item) setEdit(!edit); return; }
      if (!edit) return;
      if (k === "escape") { if (merging) setMerging(false); else setSel(null); }
      else if (/^[0-5]$/.test(k)) actions.level(+k);
      else if (k === "q") actions.rotate(-15);
      else if (k === "w") actions.rotate(15);
      else if (k === "m") actions.toggleMerge();
      else if (k === "s") actions.split();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="grid h-full grid-cols-[200px_1fr_300px] max-[1100px]:grid-cols-[170px_1fr_260px]">
      <DesignRail />
      <Stage
        view={view} setView={setView} edit={edit} setEdit={setEdit} sel={sel} merging={merging}
        onPick={pick} onInfo={setInfo} info={info} actions={actions}
      />
      <DesignPanel onEngineReset={() => setSel(null)} />
    </div>
  );
}
