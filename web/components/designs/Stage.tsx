"use client";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api, isAbort, lite } from "@/lib/api";
import { useCurrent, useLiteKey, useStore } from "@/lib/store";
import type { RenderResult } from "@/lib/types";
import { Button, Legend, Seg, cx } from "../ui";
import { EditBar, type EditActions } from "./EditBar";
import type { FacetInfo } from "./DesignsView";
import { makeThumb } from "./thumb";

export type View = "page" | "key" | "both";

export const PAGE_LEGEND: [string, string][] = [
  ["#e0484d", "Đường cắt"], ["#1f8fc4", "Lề an toàn KDP"], ["#2f9e5b", "Vùng đặt tranh"], ["#7a5cc7", "Gáy sách"],
];

type Props = {
  view: View; setView: (v: View) => void; edit: boolean; setEdit: (on: boolean) => void;
  sel: string | null; merging: boolean; onPick: (id: string) => void;
  info: FacetInfo; onInfo: (i: FacetInfo) => void; actions: EditActions;
};

export function Stage({ view, setView, edit, setEdit, sel, merging, onPick, info, onInfo, actions }: Props) {
  const item = useCurrent();
  const cur = useStore((s) => s.cur);
  const key = useLiteKey();
  const [guides, setGuides] = useState(true);
  const [zoom, setZoom] = useState(620);
  const [res, setRes] = useState<RenderResult | null>(null);
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  // ve lai khi tranh / du an doi (anh thu nho khong nam trong key nen khong gay vong lap)
  useEffect(() => {
    const { proj, notify } = useStore.getState();
    if (!proj || !item) return;
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        const r = await api.render({
          project: lite(proj), item: lite(proj).designs[cur], index: cur, interactive: true,
          views: view === "both" ? ["page", "key"] : [view], show_guides: guides,
        }, ctrl.signal);
        setRes(r);
        if (r.stats.edits_skipped) notify(`${r.stats.edits_skipped} chỉnh sửa không áp dụng được (mảng không còn hoặc không kề nhau).`);
        makeThumb(item.uid);
      } catch (e) {
        if (!isAbort(e)) notify((e as Error).message);
      } finally {
        if (!ctrl.signal.aborted) setBusy(false);
      }
    }, 80);
    return () => { clearTimeout(t); ctrl.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, cur, view, guides, item?.uid]);

  // to mau mang dang chon + doc muc/huong cua no tu svg
  useLayoutEffect(() => {
    const root = box.current;
    if (!root) return;
    root.querySelectorAll(".hit.sel").forEach((p) => p.classList.remove("sel"));
    let next: FacetInfo = null;
    if (sel) {
      root.querySelectorAll<SVGElement>(`.hit[data-id="${CSS.escape(sel)}"]`).forEach((p) => {
        p.classList.add("sel");
        next = { lv: +p.dataset.level!, ang: +p.dataset.angle! };
      });
    }
    onInfo(next);
  }, [sel, res, onInfo]);

  const lv = res?.stats.levels;
  const sheets = res ? ([
    view !== "key" && res.page_svg && ["Trang tô", res.page_svg],
    view !== "page" && res.key_svg && ["Đáp án (khi tô xong)", res.key_svg],
  ].filter(Boolean) as [string, string][]) : [];

  return (
    <div className="relative flex min-h-0 min-w-0 flex-col bg-stage">
      <div className="flex flex-wrap items-center gap-2.5 px-3.5 py-2.5 text-white/90">
        <Seg<View>
          value={view} onChange={setView}
          options={[{ value: "page", label: "Trang tô" }, { value: "key", label: "Đáp án" }, { value: "both", label: "Cả hai" }]}
        />
        <Button variant={edit ? "accent" : "default"} disabled={!item} onClick={() => setEdit(!edit)}
          title="Bấm vào mảng để đổi mức tô, hướng nét, gộp hoặc tách (phím E)">✎ Sửa mảng</Button>
        {lv && (
          <span className="text-[12.5px] tabular-nums text-white/80">
            {res!.stats.facets} mảng · {lv[0]} trắng · {lv[1]} thưa · {lv[2]} vừa · {lv[3]} dày · {lv[4]} chéo · {lv[5]} đen
            {busy && " · đang vẽ…"}
          </span>
        )}
        <span className="flex-1" />
        <label className="flex items-center gap-1.5 text-[12.5px]">
          <input type="checkbox" className="size-[15px] accent-accent" checked={guides} onChange={(e) => setGuides(e.target.checked)} /> Lề in
        </label>
        <label className="flex items-center gap-1.5 text-[12.5px]">
          Thu phóng
          <input type="range" className="w-[110px] accent-white" min={300} max={1400} step={10} value={zoom} onChange={(e) => setZoom(+e.target.value)} />
        </label>
      </div>
      {guides && item && <div className="px-3.5 pb-2"><Legend items={PAGE_LEGEND} /></div>}

      <div
        ref={box}
        className={cx("flex flex-1 items-start justify-center gap-7 overflow-auto px-7 pb-32 pt-6", edit && "editing", busy && "[&_.sheet]:opacity-60")}
        onClick={(e) => {
          const hit = (e.target as Element).closest<SVGElement>(".hit");
          if (hit) onPick(hit.dataset.id!);
        }}
      >
        {!item ? <Empty /> : sheets.map(([cap, svg]) => (
          <figure key={cap} className="sheet m-0 flex-none transition-opacity" style={{ width: view === "both" ? Math.round(zoom * 0.75) : zoom }}>
            <figcaption className="mb-1.5 text-[12.5px] font-bold text-white">{cap}</figcaption>
            <div className="bg-white shadow-[0_18px_40px_rgba(0,0,0,.3),0_2px_6px_rgba(0,0,0,.2)]" dangerouslySetInnerHTML={{ __html: svg }} />
          </figure>
        ))}
      </div>

      {edit && item && <EditBar info={info} merging={merging} canUndo={item.edits.length > 0} actions={actions} />}
    </div>
  );
}

function Empty() {
  return (
    <div className="mx-auto mt-[10vh] max-w-[460px] text-center text-white/90">
      <h2 className="mb-2.5 text-[26px] font-bold text-white">Bắt đầu một cuốn sách</h2>
      <p>Bấm <b>+ Thêm ảnh</b> hoặc kéo thả ảnh con vật vào đây. Mỗi ảnh thành một trang tô trong sách.</p>
      <ol className="mx-auto mt-4 inline-block list-decimal pl-5 text-left leading-8">
        <li>Dùng line art PNG nền trong suốt cho kết quả sạch nhất.</li>
        <li>Chỉnh số mảng, độ đậm nhạt ở cột phải.</li>
        <li>Bấm <b>✎ Sửa mảng</b> để sửa từng mảng bằng tay.</li>
        <li>Sang bước <b>2 Ruột sách</b> để kiểm tra và xuất PDF.</li>
      </ol>
    </div>
  );
}
