"use client";
import { useRef } from "react";
import { uid, useStore } from "@/lib/store";
import { Button, cx } from "../ui";
import { useUpload } from "./useUploader";

export function DesignRail() {
  const designs = useStore((s) => s.proj!.designs);
  const cur = useStore((s) => s.cur);
  const { update, setCur } = useStore.getState();
  const upload = useUpload();
  const input = useRef<HTMLInputElement>(null);

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
      <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-2.5">
        {!designs.length && (
          <div className="rounded-xl border-[1.5px] border-dashed border-line2 px-2.5 py-4 text-center text-[12.5px] text-muted">
            Kéo thả ảnh vào khung giữa, hoặc bấm “+ Thêm ảnh”.
          </div>
        )}
        {designs.map((d, i) => (
          <div
            key={d.uid} tabIndex={0} onClick={() => setCur(i)} onKeyDown={(e) => e.key === "Enter" && setCur(i)}
            className={cx(
              "group relative grid cursor-pointer grid-cols-[52px_1fr] items-center gap-2.5 rounded-xl border-[1.5px] p-1.5",
              i === cur ? "border-ink bg-soft" : "border-transparent hover:bg-soft",
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
