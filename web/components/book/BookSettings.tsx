"use client";
import { api } from "@/lib/api";
import { ENGINE_DEFAULTS, fmt } from "@/lib/defaults";
import { uid, useStore } from "@/lib/store";
import type { Settings, Style } from "@/lib/types";
import { Check, Hint, Section, Seg, Slider, TextField } from "../ui";

export function BookSettings() {
  const p = useStore((s) => s.proj!);
  const { update } = useStore.getState();
  const st = p.settings;
  const set = <K extends keyof Settings>(k: K) => (v: Settings[K]) => update((q) => { q.settings[k] = v; });
  const sty = <K extends keyof Style>(k: K) => ({
    value: p.style[k], onChange: (v: number) => update((q) => { q.style[k] = v; }),
  });
  const text = (k: "title" | "subtitle" | "author" | "publisher" | "isbn") => (v: string) => update((q) => { q[k] = v; });

  return (
    <aside className="min-h-0 overflow-y-auto border-r border-line bg-white">
      <Section title="Thông tin sách">
        <TextField label="Tên sách" value={p.title} onChange={text("title")} placeholder="Geometric Wild Animals" />
        <TextField label="Phụ đề" value={p.subtitle} onChange={text("subtitle")} placeholder="A hatching coloring book for adults" />
        <div className="grid grid-cols-2 gap-2">
          <TextField label="Tác giả" value={p.author} onChange={text("author")} />
          <TextField label="Năm" type="number" value={p.year} onChange={(v) => update((q) => { q.year = parseInt(v) || q.year; })} />
          <TextField label="Nhà xuất bản" value={p.publisher} onChange={text("publisher")} placeholder="(tuỳ chọn)" />
          <TextField label="ISBN" value={p.isbn} onChange={text("isbn")} placeholder="(tuỳ chọn)" />
        </div>
        <Hint>Chữ trong sách bằng tiếng Anh. Dùng ISBN miễn phí của KDP thì để trống ô ISBN cũng được.</Hint>
      </Section>
      <Section title="Trang đầu sách">
        <Check label="Trang tên sách" checked={st.title_page} onChange={set("title_page")} />
        <Check label="Trang bản quyền" checked={st.copyright_page} onChange={set("copyright_page")} />
        <Check label="Hướng dẫn cách tô" sub="Giải thích ký hiệu, mẹo chọn bút" checked={st.howto_page} onChange={set("howto_page")} />
        <Check label="Trang tập tô khởi động" checked={st.warmup_page} onChange={set("warmup_page")} />
        <Check label="Trang Training 1, 2" sub="Dùng ảnh riêng, không lấy từ các tranh trong sách" checked={st.training_pages} onChange={set("training_pages")} />
        {st.training_pages && <TrainingSlots />}
      </Section>
      <Section title="Trang tranh">
        <Check label="Trang trắng sau mỗi tranh" sub="In một mặt để mực không thấm sang tranh sau" checked={st.blank_back} onChange={set("blank_back")} />
        {st.blank_back && <FillerSlots />}
        <Check label="Đánh số trang" checked={st.page_numbers} onChange={set("page_numbers")} />
        <Check label="Đáp án cuối sách" checked={st.include_keys} onChange={set("include_keys")} />
        {st.include_keys && (
          <div className="my-2.5">
            <span className="mb-1 block text-[13px]">Số đáp án mỗi trang</span>
            <Seg value={st.keys_per_page} onChange={set("keys_per_page")} options={[1, 2, 4].map((v) => ({ value: v, label: v }))} />
          </div>
        )}
        <Check label="Bù trang trắng cho đủ 24 trang" sub="Mức tối thiểu của KDP" checked={st.pad_to_min} onChange={set("pad_to_min")} />
      </Section>
      <Section title="Khổ in và lề">
        <Check label="Có bleed (trang 8.625 × 11.25 in)" sub="Bắt buộc nếu dùng khung đen tràn lề" checked={st.bleed} onChange={set("bleed")} />
        <Slider label="Khoảng trắng quanh tranh" min={0} max={1} step={0.05} format={fmt.in} value={st.padding_in} onChange={set("padding_in")} />
        <Slider label="Nới thêm lề KDP" min={0} max={0.5} step={0.025} format={fmt.in} value={st.extra_margin_in} onChange={set("extra_margin_in")} />
      </Section>
      <Section title="Ký hiệu và nét">
        <Slider label="Độ đậm ký hiệu" min={0.3} max={0.8} step={0.01} format={fmt.ink} {...sty("guide_gray")}
          hint="Khoảng 35–50% mực là vừa: nhìn thấy rõ nhưng bị nét bút che đi. Nên đặt bản in thử để kiểm tra." />
        <Slider label="Độ dài ký hiệu" min={6} max={30} step={1} format={fmt.pt} {...sty("guide_len")} />
        <details className="group">
          <summary className="cursor-pointer list-none py-1 text-[13px] text-muted before:content-['▸_'] group-open:before:content-['▾_']">Độ dày nét, khoảng cách nét</summary>
          <Slider label="Viền mảng" min={0.3} max={1.5} step={0.05} format={fmt.pt} {...sty("outline_w")} />
          <Slider label="Viền ngoài con vật" min={0.5} max={3} step={0.1} format={fmt.pt} {...sty("silhouette_w")} />
          <Slider label="Thưa" min={3} max={12} step={0.1} format={fmt.pt} {...sty("sp1")} />
          <Slider label="Vừa" min={2} max={9} step={0.1} format={fmt.pt} {...sty("sp2")} />
          <Slider label="Dày" min={1.2} max={6} step={0.1} format={fmt.pt} {...sty("sp3")} />
          <Slider label="Gạch chéo (mỗi lớp)" min={1.5} max={8} step={0.1} format={fmt.pt} {...sty("sp4")} />
          <Hint>Khoảng cách nét quyết định độ dày ký hiệu và nét trong đáp án.</Hint>
        </details>
      </Section>
    </aside>
  );
}

/** 2 o nhap anh rieng cho Training 1, 2. Bam o de chon anh, bam lai de thay. */
function TrainingSlots() {
  const items = useStore((s) => s.proj!.training ?? []);
  const { update, notify } = useStore.getState();
  const pick = async (slot: number, file?: File) => {
    if (!file) return;
    try {
      const { image_id } = await api.upload(file);
      update((q) => {
        q.training = q.training ?? [];
        q.training[slot] = {
          uid: uid(), image_id, name: file.name.replace(/\.[^.]+$/, ""),
          engine: { ...ENGINE_DEFAULTS }, edits: [], frame: false, thumb: null,
        };
      });
    } catch (e) { notify((e as Error).message); }
  };
  return (
    <div className="my-2 space-y-1.5">
      {[0, 1].map((k) => (
        <label key={k} className="flex cursor-pointer items-center gap-2 rounded border border-line px-2 py-1.5 text-[13px] hover:bg-bg">
          <span className="flex-none font-medium">Training {k + 1}</span>
          <span className="min-w-0 flex-1 truncate text-muted">{items[k]?.name ?? "Chọn ảnh…"}</span>
          <input type="file" accept=".png,.jpg,.jpeg,.webp" className="hidden"
            onChange={(e) => { pick(k, e.target.files?.[0]); e.target.value = ""; }} />
        </label>
      ))}
      <Hint>Chưa chọn ảnh thì trang Training để trống. Ảnh dùng cài đặt tách mảng mặc định.</Hint>
    </div>
  );
}

/** Anh dien vao trang trai (mat sau moi tranh): 1 anh thi lap lai, nhieu anh thi xoay vong cho den het sach. */
function FillerSlots() {
  const items = useStore((s) => s.proj!.fillers ?? []);
  const { update, notify } = useStore.getState();
  const add = async (files: FileList | null) => {
    const list = [...(files ?? [])].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    for (const f of list) {
      try {
        const { image_id } = await api.upload(f);
        update((q) => {
          q.fillers = q.fillers ?? [];
          q.fillers.push({ uid: uid(), image_id, name: f.name.replace(/\.[^.]+$/, ""),
            engine: { ...ENGINE_DEFAULTS }, edits: [], frame: false, thumb: null });
        });
      } catch (e) { notify(`${f.name}: ${(e as Error).message}`); }
    }
  };
  return (
    <div className="my-2 space-y-1.5">
      <span className="block text-[13px]">Ảnh điền vào trang trái ({items.length})</span>
      {items.map((it, k) => (
        <div key={it.uid} className="flex items-center gap-2 rounded border border-line px-2 py-1 text-[13px]">
          <span className="flex-none text-muted">{k + 1}</span>
          <span className="min-w-0 flex-1 truncate">{it.name}</span>
          <button type="button" className="flex-none text-muted hover:text-ink" title="Xoá"
            onClick={() => update((q) => { q.fillers.splice(k, 1); })}>×</button>
        </div>
      ))}
      <label className="block cursor-pointer rounded border border-dashed border-line px-2 py-1.5 text-center text-[13px] text-muted hover:bg-bg">
        + Thêm ảnh
        <input type="file" multiple accept=".png,.jpg,.jpeg,.webp" className="hidden"
          onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
      </label>
      <Hint>Chưa thêm ảnh thì trang trái để trống. 1 ảnh sẽ lặp ở mọi trang trái; nhiều ảnh sẽ xoay vòng theo thứ tự cho đến hết sách.</Hint>
    </div>
  );
}
