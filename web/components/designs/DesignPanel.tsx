"use client";
import { useState } from "react";
import { download, lite } from "@/lib/api";
import { ENGINE_DEFAULTS, fmt } from "@/lib/defaults";
import { useCurrent, useStore } from "@/lib/store";
import type { Engine } from "@/lib/types";
import { Button, Check, Hint, Kbd, Section, Seg, Slider, TextField } from "../ui";

const PRESETS = [{ value: 160, label: "Ít mảng" }, { value: 260, label: "Vừa" }, { value: 420, label: "Nhiều mảng" }];

export function DesignPanel({ onEngineReset }: { onEngineReset: () => void }) {
  const item = useCurrent();
  const cur = useStore((s) => s.cur);
  const bleed = useStore((s) => s.proj!.settings.bleed);
  const { updateDesign, notify } = useStore.getState();
  // ban nhap de thanh truot muot; chi gui len may chu khi tha chuot
  const sig = `${item?.uid}|${JSON.stringify(item?.engine)}`;
  const [draft, setDraft] = useState<Engine>(() => ({ ...ENGINE_DEFAULTS, ...item?.engine }));
  const [draftFor, setDraftFor] = useState(sig);
  if (draftFor !== sig) {          // tranh hoac thong so doi tu ben ngoai -> nap lai ban nhap
    setDraftFor(sig);
    setDraft({ ...ENGINE_DEFAULTS, ...item?.engine });
  }

  if (!item) {
    return <aside className="border-l border-line bg-white"><Section><Hint className="mt-0">Chưa có tranh nào. Thêm ảnh ở cột trái.</Hint></Section></aside>;
  }

  const commit = <K extends keyof Engine>(k: K, v: Engine[K]) => {
    if (item.engine[k] === v) return;
    if (item.edits.length && !confirm(`Đổi thông số này sẽ chia lại mảng và xoá ${item.edits.length} chỉnh sửa tay của tranh. Tiếp tục?`)) {
      setDraft({ ...ENGINE_DEFAULTS, ...item.engine });
      return;
    }
    onEngineReset();
    updateDesign(cur, (d) => { d.engine[k] = v; d.edits = []; });
  };
  const slide = (k: keyof Engine) => ({
    value: draft[k] as number,
    onChange: (v: number) => setDraft((d) => ({ ...d, [k]: v })),
    onCommit: (v: number) => commit(k, v),
  });

  const exp = async (mode: "page" | "key", format: "pdf" | "svg") => {
    const p = lite(useStore.getState().proj!);
    try {
      const { name } = await download("/api/export/design", { project: p, item: p.designs[cur], index: cur, mode, format }, `design.${format}`);
      notify(`Đã tải ${name}`);
    } catch (e) { notify((e as Error).message); }
  };

  return (
    <aside className="min-h-0 overflow-y-auto border-l border-line bg-white">
      <Section title="Tranh này">
        <TextField label="Tên tranh" value={item.name} onChange={(v) => updateDesign(cur, (d) => { d.name = v; })} />
        <div className="my-2.5">
          <span className="mb-1 block text-[13px]">Mức chi tiết</span>
          <Seg value={PRESETS.find((p) => p.value === draft.facets)?.value ?? -1} options={PRESETS}
            onChange={(v) => { setDraft((d) => ({ ...d, facets: v })); commit("facets", v); }} />
        </div>
        <Slider label="Số mảng" min={60} max={700} step={10} {...slide("facets")} />
        <Slider label="Mảng để trắng" min={0} max={0.4} step={0.01} format={fmt.pct} {...slide("white")}
          hint="Nhiều mảng trắng thì tranh sáng, nhẹ tay hơn." />
        <Slider label="Mảng tô đen sẵn" min={0} max={0.15} step={0.005} format={fmt.pct} {...slide("black")} />
        <Slider label="Nét chi tiết từ ảnh" min={0} max={0.3} step={0.01} format={fmt.lineart} {...slide("lineart")}
          hint="Kéo về 0 nếu tranh bị rối." />
        <Check label="Tô đen sẵn mắt, mũi" sub="Vùng rất tối trong ảnh" checked={draft.accents} onChange={(v) => commit("accents", v)} />
        <Check label="Khung đen tràn lề" sub="Nền đen ra tới mép giấy (cần bật bleed)" checked={item.frame}
          onChange={(v) => {
            updateDesign(cur, (d) => { d.frame = v; });
            if (v && !bleed) notify("Khung đen tràn lề cần bật bleed ở bước 2. Khi chưa bật, khung chỉ nằm trong lề an toàn.");
          }} />
        <details className="group mt-1">
          <summary className="cursor-pointer list-none py-1 text-[13px] text-muted before:content-['▸_'] group-open:before:content-['▾_']">Nâng cao</summary>
          <Check label="Tự tách nền" sub="Cho ảnh chụp không có nền trong suốt" checked={draft.grabcut} onChange={(v) => commit("grabcut", v)} />
          <Slider label="Gộp tam giác thành tứ giác" min={0} max={1} step={0.05} format={fmt.pct} {...slide("merge")} />
          <Slider label="Hai mảng kề lệch hướng tối thiểu" min={0} max={60} step={5} format={fmt.deg} {...slide("min_angle_gap")} />
          <div className="flex items-end gap-2">
            <div className="flex-1"><Slider label="Cách chia mảng" min={1} max={999} step={1} {...slide("seed")} /></div>
            <Button size="sm" className="mb-3" onClick={() => { const v = 1 + Math.floor(Math.random() * 999); setDraft((d) => ({ ...d, seed: v })); commit("seed", v); }}>Xáo lại</Button>
          </div>
        </details>
      </Section>

      <Section title="Sửa tay">
        <p className="mb-2 text-xs text-muted">{item.edits.length ? `${item.edits.length} chỉnh sửa tay trên tranh này.` : "Chưa có chỉnh sửa."}</p>
        <Button size="sm" disabled={!item.edits.length}
          onClick={() => { if (confirm("Xoá mọi chỉnh sửa tay của tranh này?")) { onEngineReset(); updateDesign(cur, (d) => { d.edits = []; }); } }}>
          Xoá mọi chỉnh sửa
        </Button>
        <div className="mt-2.5 text-xs leading-7 text-muted">
          <Kbd>E</Kbd> bật/tắt sửa · <Kbd>0</Kbd>–<Kbd>5</Kbd> đổi mức · <Kbd>Q</Kbd>/<Kbd>W</Kbd> xoay<br />
          <Kbd>M</Kbd> gộp · <Kbd>S</Kbd> tách · <Kbd>⌘Z</Kbd> hoàn tác · <Kbd>Esc</Kbd> bỏ chọn
        </div>
      </Section>

      <Section title="Xuất riêng tranh này">
        <div className="grid grid-cols-2 gap-2">
          <Button size="sm" onClick={() => exp("page", "pdf")}>PDF trang tô</Button>
          <Button size="sm" onClick={() => exp("key", "pdf")}>PDF đáp án</Button>
          <Button size="sm" onClick={() => exp("page", "svg")}>SVG (Inkscape)</Button>
          <Button size="sm" onClick={() => exp("key", "svg")}>SVG đáp án</Button>
        </div>
        <Hint>SVG chia sẵn lớp: outlines, guides, fills, details để chỉnh trong Inkscape.</Hint>
      </Section>
    </aside>
  );
}
