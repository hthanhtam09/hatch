import type { Engine, Style } from "./types";

export const ENGINE_DEFAULTS: Engine = {
  facets: 260, merge: 0.5, lineart: 0.08, accents: true, grabcut: false,
  white: 0.14, black: 0.035, min_angle_gap: 30, seed: 7,
};

export const STYLE_DEFAULTS: Style = {
  guide_gray: 0.58, guide_len: 15, outline_w: 0.6, silhouette_w: 1.3, sp1: 6.5, sp2: 4.2, sp3: 2.7, sp4: 3.6,
};

export const LEVELS = [
  { lv: 0, name: "Trắng" }, { lv: 1, name: "Thưa" }, { lv: 2, name: "Vừa" },
  { lv: 3, name: "Dày" }, { lv: 4, name: "Chéo" }, { lv: 5, name: "Đen" },
] as const;

export const KIND_LABEL = {
  title: "Tên sách", copyright: "Bản quyền", howto: "Hướng dẫn", warmup: "Khởi động",
  design: "Tranh", keys: "Đáp án", blank: "Trắng",
} as const;

export const fmt = {
  pct: (v: number) => `${Math.round(v * 100)}%`,
  deg: (v: number) => `${v}°`,
  pt: (v: number) => `${(+v).toFixed(1)} pt`,
  in: (v: number) => `${(+v).toFixed(3).replace(/0+$/, "").replace(/\.$/, "")} in`,
  ink: (v: number) => `${Math.round((1 - v) * 100)}% mực`,
  lineart: (v: number) => (+v === 0 ? "tắt" : (+v).toFixed(2)),
  num: (v: number) => String(v),
};
