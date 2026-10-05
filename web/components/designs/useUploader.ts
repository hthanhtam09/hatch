"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ENGINE_DEFAULTS } from "@/lib/defaults";
import { uid, useStore } from "@/lib/store";

const POOL = 4;   // so anh tai len song song

/** Tai nhieu anh len Flask song song; moi anh thanh 1 tranh moi, giu thu tu ten file, them mot lan. */
export function useUpload() {
  return useCallback(async (files: FileList | File[]) => {
    const { update, setCur, notify } = useStore.getState();
    const all = [...files];
    const list = all.filter((f) => /\.(png|jpe?g|webp)$/i.test(f.name))
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    if (!list.length) return notify("Chỉ nhận ảnh PNG, JPG hoặc WEBP.");
    const done: ({ image_id: string } | null)[] = list.map(() => null);
    const failed: string[] = [];
    let next = 0, finished = 0;
    const worker = async () => {
      while (next < list.length) {
        const i = next++;
        try { done[i] = await api.upload(list[i]); }
        catch (e) { failed.push(`${list[i].name}: ${(e as Error).message}`); }
        notify(`Đang tải ảnh… ${++finished}/${list.length}`);
      }
    };
    notify(`Đang tải ảnh… 0/${list.length}`);
    await Promise.all(Array.from({ length: Math.min(POOL, list.length) }, worker));
    const ok = list.flatMap((f, i) => (done[i] ? [{ f, id: done[i]!.image_id }] : []));
    if (ok.length) {
      const first = useStore.getState().proj!.designs.length;
      update((p) => {
        for (const { f, id } of ok) {
          p.designs.push({
            uid: uid(), image_id: id, name: f.name.replace(/\.[^.]+$/, ""),
            engine: { ...ENGINE_DEFAULTS }, edits: [], frame: false, thumb: null,
          });
        }
      });
      setCur(first);
    }
    const skipped = all.length - list.length;
    notify([
      ok.length ? `Đã thêm ${ok.length} tranh vào sách.` : "Không thêm được tranh nào.",
      failed.length && `${failed.length} ảnh lỗi (${failed[0]}${failed.length > 1 ? "…" : ""}).`,
      skipped && `Bỏ qua ${skipped} tệp không phải ảnh.`,
    ].filter(Boolean).join(" "));
  }, []);
}

/** Keo tha anh vao bat ky dau tren cua so. */
export function useUploader() {
  const upload = useUpload();
  const [dragging, setDragging] = useState(false);
  useEffect(() => {
    let n = 0;
    const hasFiles = (e: DragEvent) => e.dataTransfer?.types.includes("Files");
    const enter = (e: DragEvent) => { if (hasFiles(e)) { n++; setDragging(true); } };
    const leave = () => { if (--n <= 0) { n = 0; setDragging(false); } };
    const over = (e: DragEvent) => e.preventDefault();
    const drop = (e: DragEvent) => {
      e.preventDefault(); n = 0; setDragging(false);
      if (e.dataTransfer?.files.length) {
        useStore.getState().setTab("designs");
        upload(e.dataTransfer.files);
      }
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
    };
  }, [upload]);
  return { dragging };
}
