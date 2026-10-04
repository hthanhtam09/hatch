"use client";
import { create } from "zustand";
import { api, lite } from "./api";
import { ENGINE_DEFAULTS, STYLE_DEFAULTS } from "./defaults";
import type { DesignItem, Project } from "./types";

export type Tab = "designs" | "book" | "cover";

type State = {
  proj: Project | null;
  cur: number;
  tab: Tab;
  saveState: string;
  toast: { msg: string; id: number } | null;
  load: () => Promise<void>;
  /** Sua du an theo kieu "ban nhap": recipe duoc phep doi truc tiep tren ban sao. */
  update: (recipe: (p: Project) => void, opts?: { save?: boolean }) => void;
  updateDesign: (i: number, recipe: (d: DesignItem) => void, opts?: { save?: boolean }) => void;
  setCur: (i: number) => void;
  setTab: (t: Tab) => void;
  notify: (msg: string) => void;
};

let saveTimer: ReturnType<typeof setTimeout> | undefined;
export const uid = () => Math.random().toString(36).slice(2, 10);

export const useStore = create<State>((set, get) => {
  const scheduleSave = () => {
    set({ saveState: "Đang lưu…" });
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      const p = get().proj;
      if (!p) return;
      try {
        const d = await api.saveProject(p);
        set({ saveState: `Đã lưu lúc ${d.saved_at}` });
      } catch (e) {
        set({ saveState: `Chưa lưu được: ${(e as Error).message}` });
      }
    }, 700);
  };

  return {
    proj: null,
    cur: -1,
    tab: "designs",
    saveState: "Đang mở dự án…",
    toast: null,

    async load() {
      try {
        const p = await api.loadProject();
        p.style = { ...STYLE_DEFAULTS, ...p.style };
        p.designs = p.designs.map((d) => ({
          ...d, uid: d.uid ?? uid(), engine: { ...ENGINE_DEFAULTS, ...d.engine }, edits: d.edits ?? [], frame: !!d.frame,
        }));
        set({
          proj: p, cur: p.designs.length ? 0 : -1,
          saveState: p.designs.length ? "Đã mở dự án đã lưu" : "Dự án mới · tự lưu khi thay đổi",
        });
      } catch (e) {
        set({ saveState: "Mất kết nối máy chủ" });
        get().notify((e as Error).message);
      }
    },

    update(recipe, opts) {
      const p = get().proj;
      if (!p) return;
      const next = structuredClone(p);
      recipe(next);
      set({ proj: next });
      if (opts?.save !== false) scheduleSave();
    },

    updateDesign(i, recipe, opts) {
      get().update((p) => { if (p.designs[i]) recipe(p.designs[i]); }, opts);
    },

    setCur: (i) => set({ cur: i }),
    setTab: (t) => set({ tab: t }),
    notify: (msg) => set({ toast: { msg, id: Date.now() } }),
  };
});

export const useCurrent = () => useStore((s) => (s.proj && s.cur >= 0 ? s.proj.designs[s.cur] ?? null : null));

/** Khoa (string) dai dien phan du an anh huong toi hinh ve -> dung lam dependency cho effect. */
export const useLiteKey = () => useStore((s) => (s.proj ? JSON.stringify(lite(s.proj)) : ""));
