import { api, lite } from "@/lib/api";
import { useStore } from "@/lib/store";

const timers = new Map<string, ReturnType<typeof setTimeout>>();

/** Anh thu nho PNG cho cot danh sach. Goi tre (debounce) theo tung tranh. */
export function makeThumb(uid: string, delay = 900) {
  clearTimeout(timers.get(uid));
  timers.set(uid, setTimeout(async () => {
    const { proj, updateDesign } = useStore.getState();
    if (!proj) return;
    const i = proj.designs.findIndex((d) => d.uid === uid);
    if (i < 0) return;
    try {
      const p = lite(proj);
      const r = await api.render({ project: p, item: p.designs[i], index: i, views: ["page"], show_guides: false });
      const url = URL.createObjectURL(new Blob([r.page_svg!], { type: "image/svg+xml" }));
      const img = new Image();
      await new Promise((ok, bad) => { img.onload = ok; img.onerror = bad; img.src = url; });
      const c = document.createElement("canvas");
      c.width = 132;
      c.height = Math.round((132 * img.height) / img.width);
      const ctx = c.getContext("2d")!;
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, c.width, c.height);
      ctx.drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      const j = useStore.getState().proj!.designs.findIndex((d) => d.uid === uid);
      if (j >= 0) updateDesign(j, (d) => { d.thumb = c.toDataURL("image/png"); });
    } catch { /* anh thu nho khong quan trong */ }
  }, delay));
}
