"use client";
import { LEVELS } from "@/lib/defaults";
import { Button, cx } from "../ui";
import type { FacetInfo } from "./DesignsView";

export type EditActions = {
  level: (v: number) => void; rotate: (dl: number) => void; split: () => void; toggleMerge: () => void; undo: () => void;
  toggleKeep: () => void; keepSize: (d: number) => void;
};

export type KeepState = { on: boolean; frac: number };

export function LevelIcon({ lv }: { lv: number }) {
  const sp = ({ 1: 6, 2: 4, 3: 2.6, 4: 3.5 } as Record<number, number>)[lv];
  let d = "";
  if (sp) {
    for (let k = -24; k <= 24; k += sp) d += `M${3 + k} 21L${21 + k} 3`;
    if (lv === 4) for (let k = -24; k <= 24; k += sp) d += `M${3 + k} 3L${21 + k} 21`;
  }
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
      <clipPath id={`lvc${lv}`}><rect x="3" y="3" width="18" height="18" /></clipPath>
      <rect x="3" y="3" width="18" height="18" fill={lv === 5 ? "#000" : "#fff"} stroke="#000" strokeWidth="1.2" />
      {d && <path d={d} stroke="#000" strokeWidth=".8" clipPath={`url(#lvc${lv})`} />}
    </svg>
  );
}

export function EditBar({ info, merging, keep, canUndo, actions }: {
  info: FacetInfo; merging: boolean; keep: KeepState; canUndo: boolean; actions: EditActions;
}) {
  const msg = keep.on ? "Bấm vào mắt (hoặc chỗ cần giữ nguyên) để thêm vùng. Bấm vào vùng nét đứt để bỏ. Esc để thoát."
    : merging ? "Bấm vào mảng kề bên để gộp. Esc để huỷ."
    : info ? "Chọn mức tô, xoay hướng, hoặc gộp/tách." : "Bấm vào một mảng để chọn.";
  const hatched = info && info.lv > 0 && info.lv < 5;
  return (
    <div className="absolute bottom-4 left-1/2 z-10 flex max-w-[calc(100%-30px)] -translate-x-1/2 flex-wrap items-center gap-3 rounded-2xl bg-white px-3 py-2.5 shadow-[0_10px_30px_rgba(0,0,0,.3)]">
      <div className="flex gap-1">
        {LEVELS.map(({ lv, name }) => (
          <button
            key={lv} disabled={!info} title={`${name} (phím ${lv})`} aria-pressed={info?.lv === lv} onClick={() => actions.level(lv)}
            className={cx(
              "flex w-11 flex-col items-center gap-px rounded-lg border bg-white pb-0.5 pt-1 text-[10.5px] disabled:opacity-40",
              info?.lv === lv ? "border-accent bg-accent-soft shadow-[0_0_0_1px_var(--color-accent)]" : "border-line2 hover:border-ink",
            )}
          >
            <LevelIcon lv={lv} />{name}<kbd className="font-sans text-[10px] text-muted">{lv}</kbd>
          </button>
        ))}
      </div>
      <div className="w-px self-stretch bg-line" />
      <div className="flex items-center gap-1">
        <Button size="sm" disabled={!hatched} onClick={() => actions.rotate(-15)} title="Xoay hướng nét −15° (phím Q)">↺ 15°</Button>
        <span className="min-w-9 text-center text-[12.5px] tabular-nums">{hatched ? `${Math.round(info!.ang)}°` : "–"}</span>
        <Button size="sm" disabled={!hatched} onClick={() => actions.rotate(15)} title="Xoay hướng nét +15° (phím W)">↻ 15°</Button>
      </div>
      <div className="w-px self-stretch bg-line" />
      <div className="flex gap-1">
        <Button size="sm" variant={merging ? "accent" : "default"} disabled={!info} onClick={actions.toggleMerge} title="Gộp với mảng kề bên (phím M)">Gộp</Button>
        <Button size="sm" disabled={!info} onClick={actions.split} title="Tách đôi mảng (phím S)">Tách</Button>
      </div>
      <div className="w-px self-stretch bg-line" />
      <div className="flex items-center gap-1">
        <Button size="sm" variant={keep.on ? "accent" : "default"} onClick={actions.toggleKeep}
          title="Giữ nguyên vùng ảnh gốc (mắt...), chỉ đổi sang trắng đen (phím K)">◉ Giữ nguyên</Button>
        {keep.on && <>
          <Button size="sm" onClick={() => actions.keepSize(-1)} title="Thu nhỏ vùng (phím [)">−</Button>
          <span className="min-w-9 text-center text-[12.5px] tabular-nums">{(keep.frac * 100).toFixed(1)}%</span>
          <Button size="sm" onClick={() => actions.keepSize(1)} title="Phóng to vùng (phím ])">+</Button>
        </>}
      </div>
      <div className="w-px self-stretch bg-line" />
      <Button size="sm" disabled={!canUndo} onClick={actions.undo} title="Hoàn tác (⌘Z)">↶ Hoàn tác</Button>
      <span className="max-w-[260px] text-[12.5px] text-muted">{msg}</span>
    </div>
  );
}
