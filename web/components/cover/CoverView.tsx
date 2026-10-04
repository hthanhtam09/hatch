"use client";
import { useEffect, useState } from "react";
import { api, download, isAbort, lite } from "@/lib/api";
import { useLiteKey, useStore } from "@/lib/store";
import type { Cover, CoverPreview } from "@/lib/types";
import { Button, Hint, Kv, Legend, Section, Seg, TextField } from "../ui";

export function CoverView() {
  const key = useLiteKey();
  const proj = useStore((s) => s.proj!);
  const { update, notify } = useStore.getState();
  const [prev, setPrev] = useState<CoverPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Cover>(k: K) => (v: Cover[K]) => update((p) => { p.cover[k] = v; });

  useEffect(() => {
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      api.coverPreview(lite(useStore.getState().proj!), ctrl.signal).then(setPrev).catch((e) => !isAbort(e) && notify(e.message));
    }, 300);
    return () => { clearTimeout(t); ctrl.abort(); };
  }, [key, notify]);

  const exportCover = async () => {
    setBusy(true);
    try { const { name } = await download("/api/cover", lite(proj), "cover.pdf"); notify(`Đã xuất ${name}`); }
    catch (e) { notify((e as Error).message); }
    setBusy(false);
  };

  return (
    <div className="grid h-full grid-cols-[330px_1fr]">
      <aside className="min-h-0 overflow-y-auto border-r border-line bg-white">
        <Section title="Bìa trước">
          <div className="my-2.5">
            <label htmlFor="c-front" className="mb-1 block text-[13px]">Tranh trên bìa</label>
            <select id="c-front" className="w-full rounded-md border border-line2 bg-white px-2.5 py-1.5"
              value={proj.designs.length ? Math.min(proj.cover.front, proj.designs.length - 1) : -1}
              onChange={(e) => set("front")(+e.target.value)}>
              {proj.designs.length
                ? proj.designs.map((d, i) => <option key={d.uid} value={i}>{i + 1}. {d.name}</option>)
                : <option value={-1}>(chưa có tranh)</option>}
            </select>
          </div>
          <div className="my-2.5"><span className="mb-1 block text-[13px]">Tranh hiển thị dạng</span>
            <Seg value={proj.cover.front_mode} onChange={set("front_mode")} options={[{ value: "key", label: "Đã tô xong" }, { value: "page", label: "Có ký hiệu" }]} /></div>
          <div className="my-2.5"><span className="mb-1 block text-[13px]">Nền</span>
            <Seg value={proj.cover.theme} onChange={set("theme")} options={[{ value: "light", label: "Trắng" }, { value: "dark", label: "Đen" }]} /></div>
          <Hint>Tên sách, phụ đề, tác giả lấy từ bước 2.</Hint>
        </Section>
        <Section title="Bìa sau">
          <TextField label="Đoạn giới thiệu" multiline value={proj.back_text} placeholder="Relax and unwind with 30 geometric animals..."
            onChange={(v) => update((p) => { p.back_text = v; })} />
          <Hint>KDP tự in mã vạch vào ô 2 × 1.2 in ở góc dưới phải. Tool để trống vùng đó.</Hint>
        </Section>
        <Section title="Giấy">
          <Seg value={proj.cover.paper} onChange={set("paper")} options={[{ value: "white", label: "Trắng" }, { value: "cream", label: "Kem" }]} />
          <Hint>Sách tô màu nên dùng giấy trắng. Độ dày gáy tính theo số trang ruột sách.</Hint>
        </Section>
        {prev && (
          <Section>
            <Kv rows={[
              ["Số trang ruột", prev.page_count], ["Độ dày gáy", `${prev.spine_in.toFixed(4)} in`],
              ["Khổ file bìa", `${prev.size_in.map((x) => x.toFixed(3)).join(" × ")} in`],
              ["Chữ trên gáy", prev.spine_text ? "Có" : "Không (cần từ 80 trang)"],
            ]} />
          </Section>
        )}
        <Section>
          <Button variant="primary" block disabled={busy} onClick={exportCover}>{busy ? "Đang xuất…" : "Xuất bìa PDF"}</Button>
          <Hint>Đối chiếu kích thước với công cụ Cover Calculator của KDP trước khi nộp.</Hint>
        </Section>
      </aside>
      <div className="flex min-h-0 flex-col gap-3.5 overflow-auto bg-stage px-7 pb-14 pt-6">
        <Legend items={[["#e0484d", "Đường cắt"], ["#1f8fc4", "Vùng an toàn chữ"], ["#7a5cc7", "Gáy"], ["#e6a23a", "Ô mã vạch"], ["transparent", "Bìa sau bên trái, bìa trước bên phải"]]} />
        <div className="w-full max-w-[1300px] bg-white shadow-[0_18px_40px_rgba(0,0,0,.3)] [&_svg]:block [&_svg]:h-auto [&_svg]:w-full"
          dangerouslySetInnerHTML={{ __html: prev?.svg ?? "" }} />
      </div>
    </div>
  );
}
