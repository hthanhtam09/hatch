import type { BookPlan, CoverPreview, DesignItem, Project, RenderResult } from "./types";

export class ApiError extends Error {}

async function post<T>(url: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const r = await fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal,
  });
  const d = await r.json().catch(() => ({ error: `Máy chủ Python trả về lỗi ${r.status}. Flask đã chạy chưa?` }));
  if (!r.ok) throw new ApiError(d.error || "Có lỗi xảy ra.");
  return d as T;
}

/** Du an gui len may chu khong kem anh thu nho cho nhe. */
export function lite(p: Project): Project {
  return { ...p, designs: p.designs.map(({ thumb: _thumb, ...d }) => d as DesignItem) };
}

// gioi han so request ve trang sach chay cung luc
let running = 0;
const queue: (() => void)[] = [];
async function limited<T>(fn: () => Promise<T>, max = 3): Promise<T> {
  if (running >= max) await new Promise<void>((ok) => queue.push(ok));
  running++;
  try { return await fn(); } finally { running--; queue.shift()?.(); }
}

export const api = {
  async loadProject(): Promise<Project> {
    const r = await fetch("/api/project");
    if (!r.ok) throw new ApiError("Không kết nối được máy chủ Python (cổng 5050).");
    return r.json();
  },
  saveProject: (p: Project) => post<{ saved_at: string }>("/api/project", p),

  async upload(file: File) {
    const fd = new FormData();
    fd.append("image", file);
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    const d = await r.json().catch(() => ({ error: "Tải ảnh thất bại." }));
    if (!r.ok) throw new ApiError(d.error);
    return d as { image_id: string; name: string };
  },

  render: (body: {
    project: Project; item: DesignItem; index: number; views: ("page" | "key")[];
    interactive?: boolean; show_guides?: boolean;
  }, signal?: AbortSignal) => post<RenderResult>("/api/render", body, signal),

  plan: (p: Project, signal?: AbortSignal) => post<BookPlan>("/api/book/plan", p, signal),
  page: (p: Project, n: number, show_guides = false, signal?: AbortSignal) =>
    limited(() => post<{ svg: string }>("/api/book/page", { project: p, n, show_guides }, signal)),
  coverPreview: (p: Project, signal?: AbortSignal) => post<CoverPreview>("/api/cover/preview", p, signal),
};

/** Goi API tra ve file roi cho trinh duyet tai xuong. */
export async function download(url: string, body: unknown, fallback: string) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new ApiError(d.error || "Xuất file thất bại.");
  }
  const blob = await r.blob();
  const name = (r.headers.get("Content-Disposition") || "").match(/filename="?([^"]+)"?/)?.[1] || fallback;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  return { name, headers: r.headers };
}

export function isAbort(e: unknown) {
  return e instanceof DOMException && e.name === "AbortError";
}
