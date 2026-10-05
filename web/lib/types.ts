export type Engine = {
  facets: number; merge: number; lineart: number; accents: boolean; grabcut: boolean;
  white: number; black: number; min_angle_gap: number; seed: number;
};

export type Style = {
  guide_gray: number; guide_len: number; outline_w: number; silhouette_w: number;
  sp1: number; sp2: number; sp3: number; sp4: number;
};

export type Edit =
  | { op: "level"; id: string; v: number }
  | { op: "angle"; id: string; v: number }
  | { op: "merge"; a: string; b: string }
  | { op: "split"; id: string }
  | { op: "keep_add"; x: number; y: number; r: number }
  | { op: "keep_del"; id: string };

export type DesignItem = {
  uid: string; image_id: string; name: string; engine: Engine; edits: Edit[]; frame: boolean;
  thumb?: string | null;
};

export type Settings = {
  bleed: boolean; padding_in: number; extra_margin_in: number; page_numbers: boolean; blank_back: boolean;
  title_page: boolean; copyright_page: boolean; howto_page: boolean; warmup_page: boolean;
  include_keys: boolean; keys_per_page: number; pad_to_min: boolean;
};

export type Cover = { front: number; theme: "light" | "dark"; paper: "white" | "cream"; front_mode: "key" | "page" };

export type Project = {
  title: string; subtitle: string; author: string; publisher: string; isbn: string; year: number;
  back_text: string; settings: Settings; style: Style; cover: Cover; designs: DesignItem[];
};

export type Stats = {
  facets: number; levels: Record<string, number>; image_px: [number, number];
  edits?: number; edits_skipped?: number; keeps?: number;
};

export type RenderResult = { page_svg?: string; key_svg?: string; stats: Stats; ms: number };

export type PageKind = "title" | "copyright" | "howto" | "warmup" | "design" | "keys" | "blank";
export type PlanPage = { n: number; side: "left" | "right"; kind: PageKind; i?: number; items?: number[] };
export type BookPlan = {
  total_pages: number; gutter_in: number; min_gutter_in: number; outside_in: number;
  page_size_in: [number, number]; pages: PlanPage[];
};

export type CoverPreview = { svg: string; page_count: number; spine_in: number; size_in: [number, number]; spine_text: boolean };
