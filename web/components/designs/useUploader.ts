"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ENGINE_DEFAULTS } from "@/lib/defaults";
import { uid, useStore } from "@/lib/store";

/** Tai anh len Flask; moi anh thanh 1 tranh moi trong sach. */
export function useUpload() {
  return useCallback(async (files: FileList | File[]) => {
    const { update, setCur, notify } = useStore.getState();
    const list = [...files].filter((f) => /\.(png|jpe?g|webp)$/i.test(f.name));
    if (!list.length) return notify("Chỉ nhận ảnh PNG, JPG hoặc WEBP.");
    let added = 0;
    for (const f of list) {
      notify(`Đang tải ${f.name}…`);
      try {
        const d = await api.upload(f);
        update((p) => {
          p.designs.push({
            uid: uid(), image_id: d.image_id, name: f.name.replace(/\.[^.]+$/, ""),
            engine: { ...ENGINE_DEFAULTS }, edits: [], frame: false, thumb: null,
          });
        });
        setCur(useStore.getState().proj!.designs.length - 1);
        added++;
      } catch (e) {
        notify((e as Error).message);
      }
    }
    if (added) notify(added > 1 ? `Đã thêm ${added} tranh vào sách.` : "Đã thêm tranh vào sách.");
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
