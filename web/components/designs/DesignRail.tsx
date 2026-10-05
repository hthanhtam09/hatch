"use client";
import { useRef, useState } from "react";
import { uid, useStore } from "@/lib/store";
import { Button, cx } from "../ui";
import { useUpload } from "./useUploader";

export function DesignRail() {
  const designs = useStore((s) => s.proj!.designs);
  const cur = useStore((s) => s.cur);
  const { update, setCur } = useStore.getState();
  const upload = useUpload();
  const input = useRef<HTMLInputElement>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const anchor = useRef(cur);
  const live = new Set(designs.map((d) => d.uid));
  const sel = [...picked].filter((u) => live.has(u));   // bo uid da bi xoa/doi du an

  const toggle = (i: number, range: boolean) => {
    const next = new Set(sel);
    if (range) {
      const [a, b] = [Math.min(anchor.current, i), Math.max(anchor.current, i)];
      for (let k = a; k <= b; k++) next.add(designs[k].uid);
    } else {
      const u = designs[i].uid;
      if (next.has(u)) next.delete(u); else next.add(u);
      anchor.current = i;
    }
    setPicked(next);
  };

  const delMany = () => {
    if (!sel.length || !confirm(`Xoá ${sel.length} tranh khỏi sách?`)) return;
    const gone = new Set(sel);
    const curUid = designs[cur]?.uid;
    let next = -1;
    update((p) => {
      p.designs = p.designs.filter((d) => !gone.has(d.uid));
      next = Math.min(Math.max(p.designs.findIndex((d) => d.uid === curUid), 0), p.designs.length - 1);
    });
    setPicked(new Set());
    setCur(next);
  };

  const act = (i: number, a: "up" | "down" | "dup" | "del") => {
    let next = i;
    if (a === "del" && !confirm(`Xoá tranh “${designs[i].name}” khỏi sách?`)) return;
    update((p) => {
      const D = p.designs;
      if (a === "del") { D.splice(i, 1); next = Math.min(cur > i ? cur - 1 : cur, D.length - 1); }
      if (a === "up" && i > 0) { [D[i - 1], D[i]] = [D[i], D[i - 1]]; next = i - 1; }
      if (a === "down" && i < D.length - 1) { [D[i + 1], D[i]] = [D[i], D[i + 1]]; next = i + 1; }
      if (a === "dup") { D.splice(i + 1, 0, { ...structuredClone(D[i]), uid: uid(), name: `${D[i].name} (2)` }); next = i + 1; }
    });
    setCur(next);
  };

  return (
    <aside className="flex min-h-0 flex-col border-r border-line bg-white">
      <div className="border-b border-line p-3">
        <Button variant="primary" block onClick={() => input.current?.click()}>+ Thêm ảnh</Button>
        <input ref={input} type="file" accept=".png,.jpg,.jpeg,.webp" multiple hidden
          onChange={(e) => { if (e.target.files) upload(e.target.files); e.target.value = ""; }} />
      </div>
      {designs.length > 1 && (
        <div className="flex items-center gap-1.5 border-b border-line px-3 py-1.5 text-[12px]">
          {sel.length ? <>
            <span className="font-bold">Đã chọn {sel.length}</span>
            <span className="flex-1" />
            {sel.length < designs.length && <button className="text-muted hover:text-ink" onClick={() => setPicked(new Set(designs.map((d) => d.uid)))}>Tất cả</button>}
            <button className="text-muted hover:text-ink" onClick={() => setPicked(new Set())}>Bỏ chọn</button>
            <button className="font-bold text-red-600 hover:underline" onClick={delMany}>Xoá</button>
          </> : <>
            <span className="text-muted">⌘/Shift + bấm để chọn nhiều</span>
            <span className="flex-1" />
            <button className="text-muted hover:text-ink" onClick={() => setPicked(new Set(designs.map((d) => d.uid)))}>Chọn tất cả</button>
          </>}
        </div>
      )}
      <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-2.5">
        {!designs.length && (
          <div className="rounded-xl border-[1.5px] border-dashed border-line2 px-2.5 py-4 text-center text-[12.5px] text-muted">
            Kéo thả ảnh vào khung giữa, hoặc bấm “+ Thêm ảnh”.
          </div>
        )}
        {designs.map((d, i) => (
          <div
            key={d.uid} tabIndex={0}
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey) { toggle(i, false); return; }
              if (e.shiftKey) { toggle(i, true); return; }
              anchor.current = i; setCur(i);
            }}
            onKeyDown={(e) => e.key === "Enter" && setCur(i)}
            className={cx(
              "group relative grid cursor-pointer grid-cols-[52px_1fr] items-center gap-2.5 rounded-xl border-[1.5px] p-1.5",
              i === cur ? "border-ink bg-soft" : "border-transparent hover:bg-soft",
              picked.has(d.uid) && "bg-accent-soft ring-2 ring-accent",
            )}
          >
            <div className="grid aspect-[8.5/11] w-[52px] place-items-center overflow-hidden rounded-sm border border-line bg-white">
              {/* eslint-disable-next-line @next/next/no-img-element -- anh data: URL nho, khong can toi uu */}
              {d.thumb ? <img src={d.thumb} alt="" className="size-full object-contain" /> : <span className="text-xs text-muted">…</span>}
            </div>
            <div className="min-w-0">
              <div className="truncate text-[12.5px] font-bold">{i + 1}. {d.name || "Tranh"}</div>
              <div className="text-[11.5px] text-muted">
                {d.edits.length ? `${d.edits.length} sửa tay` : " "}{d.frame ? " · khung đen" : ""}
              </div>
            </div>
            <div className={cx("absolute right-1 top-1 gap-0.5", i === cur ? "flex" : "hidden group-hover:flex")}>
              {([["up", "↑", "Đưa lên trước"], ["down", "↓", "Đưa ra sau"], ["dup", "⧉", "Nhân bản để thử phương án khác"], ["del", "✕", "Xoá khỏi sách"]] as const).map(([a, ch, t]) => (
                <button key={a} title={t} aria-label={t}
                  onClick={(e) => { e.stopPropagation(); act(i, a); }}
                  className="size-[22px] rounded-md bg-white text-muted shadow-[0_0_0_1px_var(--color-line)] hover:text-ink">
                  {ch}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
