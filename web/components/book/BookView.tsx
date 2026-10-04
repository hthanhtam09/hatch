"use client";
import { useEffect, useMemo, useState } from "react";
import { api, download, isAbort, lite } from "@/lib/api";
import { KIND_LABEL } from "@/lib/defaults";
import { useLiteKey, useStore } from "@/lib/store";
import type { BookPlan, PlanPage, Project } from "@/lib/types";
import { Button, Kv, Section } from "../ui";
import { BookSettings } from "./BookSettings";
import { PageDialog } from "./PageDialog";
import { PageThumb } from "./PageThumb";

export function BookView() {
  const key = useLiteKey();
  const proj = useStore((s) => s.proj!);
  const { notify } = useStore.getState();
  const [plan, setPlan] = useState<BookPlan | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      api.plan(lite(useStore.getState().proj!), ctrl.signal).then(setPlan).catch((e) => !isAbort(e) && notify(e.message));
    }, 300);
    return () => { clearTimeout(t); ctrl.abort(); };
  }, [key, notify]);

  // khoa cache anh trang: bo phan bia (khong anh huong ruot sach)
  const cacheKey = useMemo(() => {
    const { cover: _c, back_text: _b, ...rest } = JSON.parse(key || "{}");
    return JSON.stringify(rest) + (plan?.total_pages ?? "");
  }, [key, plan?.total_pages]);

  const spreads = useMemo(() => {
    if (!plan) return [];
    const P = plan.pages, out: [PlanPage | null, PlanPage | null][] = [[null, P[0]]];
    for (let i = 1; i < P.length; i += 2) out.push([P[i], P[i + 1] ?? null]);
    return out;
  }, [plan]);

  const exportBook = async () => {
    setExporting(true);
    try {
      const { name, headers } = await download("/api/book", lite(proj), "interior.pdf");
      const info = JSON.parse(headers.get("X-Book-Info") || "{}");
      notify(`Đã xuất ${name}: ${info.total_pages} trang, ${info.page_size_in?.join(" × ")} in. Bản sao nằm trong data/exports.`);
    } catch (e) { notify((e as Error).message); }
    setExporting(false);
  };

  const Page = ({ p }: { p: PlanPage | null }) => !p ? <div className="invisible w-[120px]" /> : (
    <button
      onClick={() => setOpen(p.n)} title={`Trang ${p.n}: ${KIND_LABEL[p.kind]}`}
      className="relative aspect-[8.5/11] w-[120px] cursor-zoom-in overflow-hidden bg-white shadow-[0_4px_12px_rgba(0,0,0,.25)] hover:outline-2 hover:outline-accent"
    >
      {p.kind !== "blank" && <PageThumb n={p.n} cacheKey={cacheKey} />}
      {p.kind !== "blank" && (
        <span className="absolute left-1 top-1 rounded bg-black/65 px-1.5 text-[10px] text-white">
          {KIND_LABEL[p.kind]}{p.kind === "design" ? ` ${p.i! + 1}` : ""}
        </span>
      )}
    </button>
  );

  return (
    <div className="grid h-full grid-cols-[330px_1fr]">
      <BookSettings />
      <div className="min-h-0 overflow-auto bg-stage px-7 pb-14 pt-6">
        <div className="mb-5 flex flex-wrap items-center gap-3.5 text-white">
          <h2 className="text-lg font-bold">Ruột sách</h2>
          <span className="text-[13px] text-white/80">{proj.designs.length} tranh · {plan?.total_pages ?? "…"} trang</span>
          <span className="flex-1" />
          <Button variant="primary" disabled={!proj.designs.length || exporting} onClick={exportBook}>
            {exporting ? "Đang xuất…" : "Xuất ruột sách PDF"}
          </Button>
        </div>
        <div className="grid grid-cols-[minmax(0,1fr)_270px] items-start gap-6">
          <div className="flex flex-wrap gap-x-7 gap-y-6">
            {spreads.map(([l, r], k) => (
              <div key={k} className="flex flex-col gap-1">
                <div className="flex"><Page p={l} /><Page p={r} /></div>
                <div className="flex justify-between px-1 text-[11px] text-white/80"><span>{l?.n}</span><span>{r?.n}</span></div>
              </div>
            ))}
          </div>
          {plan && <Checks proj={proj} plan={plan} />}
        </div>
      </div>
      {open && plan && <PageDialog n={open} total={plan.total_pages} plan={plan} onNav={setOpen} onClose={() => setOpen(null)} />}
    </div>
  );
}

function Checks({ proj, plan }: { proj: Project; plan: BookPlan }) {
  const st = proj.settings, n = proj.designs.length, out: ["" | "warn" | "bad", string][] = [];
  out.push(n ? ["", `${n} tranh trong sách`] : ["bad", "Sách chưa có tranh nào"]);
  out.push(proj.title ? ["", "Đã có tên sách"] : ["warn", "Chưa nhập tên sách (in trên trang đầu và bìa)"]);
  out.push(plan.total_pages >= 24 ? ["", `${plan.total_pages} trang, đủ tối thiểu 24 trang`] : ["bad", `Chỉ có ${plan.total_pages} trang, KDP cần ít nhất 24`]);
  if (plan.total_pages > 590) out.push(["bad", "Quá số trang tối đa cho khổ 8.5 × 11 in đen trắng"]);
  out.push(["", "Font Lato nhúng sẵn trong PDF"]);
  const framed = proj.designs.filter((d) => d.frame).length;
  if (framed && !st.bleed) out.push(["warn", `${framed} tranh có khung đen nhưng chưa bật bleed nên khung không tràn mép`]);
  if (!framed && st.bleed) out.push(["warn", "Đang bật bleed nhưng không trang nào tràn mép. Có thể tắt bleed."]);
  const g = proj.style.guide_gray;
  out.push(g > 0.7 ? ["warn", "Ký hiệu khá nhạt, có thể in mờ. Nên in thử."]
    : g < 0.45 ? ["warn", "Ký hiệu khá đậm, có thể lộ qua nét tô."] : ["", "Độ đậm ký hiệu trong khoảng an toàn"]);
  const busy = proj.designs.filter((d) => d.engine.lineart > 0.15).length;
  if (busy) out.push(["warn", `${busy} tranh có nhiều nét chi tiết, dễ rối`]);
  out.push(["warn", "Đặt một bản in thử (proof) trước khi phát hành"]);
  const icon = { "": ["✓", "text-ok"], warn: ["!", "text-warn"], bad: ["✕", "text-bad"] } as const;

  return (
    <div className="rounded-xl bg-white">
      <Section title="Kiểm tra trước khi nộp KDP">
        <ul className="text-[13px]">
          {out.map(([c, t]) => (
            <li key={t} className="flex gap-2 py-1"><b className={`w-3.5 flex-none ${icon[c][1]}`}>{icon[c][0]}</b>{t}</li>
          ))}
        </ul>
      </Section>
      <Section className="border-b-0">
        <Kv rows={[
          ["Khổ trang PDF", `${plan.page_size_in.join(" × ")} in`], ["Khổ cắt", "8.5 × 11 in"],
          ["Lề gáy", `${plan.gutter_in.toFixed(3)} in`], ["Lề ngoài/trên/dưới", `${plan.outside_in.toFixed(3)} in`],
          ["Tổng số trang", plan.total_pages],
        ]} />
      </Section>
    </div>
  );
}
