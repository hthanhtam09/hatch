"use client";
import { memo, useEffect, useRef, useState } from "react";
import { api, isAbort } from "@/lib/api";
import { useStore } from "@/lib/store";
import { lite } from "@/lib/api";

const cache = new Map<string, string>();

/** 1 trang sach: chi tai svg khi trang hien tren man hinh. */
export const PageThumb = memo(function PageThumb({ n, cacheKey }: { n: number; cacheKey: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const ck = `${cacheKey}|${n}`;
  const [svg, setSvg] = useState(() => cache.get(ck) ?? "");
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { rootMargin: "300px" });
    if (ref.current) io.observe(ref.current);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const hit = cache.get(ck);
    if (hit) { setSvg(hit); return; }
    if (!visible) return;
    const ctrl = new AbortController();
    api.page(lite(useStore.getState().proj!), n, false, ctrl.signal)
      .then((r) => {
        if (cache.size > 400) cache.clear();
        cache.set(ck, r.svg);
        setSvg(r.svg);
      })
      .catch((e) => { if (!isAbort(e)) setSvg(""); });
    return () => ctrl.abort();
  }, [ck, n, visible]);

  return <div ref={ref} className="size-full [&_svg]:size-full" dangerouslySetInnerHTML={{ __html: svg }} />;
});
