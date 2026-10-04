"use client";
import { fmt } from "@/lib/defaults";
import { useStore } from "@/lib/store";
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
      </Section>
      <Section title="Trang tranh">
        <Check label="Trang trắng sau mỗi tranh" sub="In một mặt để mực không thấm sang tranh sau" checked={st.blank_back} onChange={set("blank_back")} />
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
