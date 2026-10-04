import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hatch Studio",
  description: "Tạo sách tô màu low-poly kiểu gạch nét cho Amazon KDP",
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: extension trinh duyet (Grammarly, dich, dark mode...) hay chen thuoc tinh
    // vao <html>/<body> truoc khi React chay. Chi bo qua thuoc tinh cua dung 2 the nay, khong anh huong ben trong.
    <html lang="vi" className="h-full antialiased" suppressHydrationWarning>
      <body className="h-full overflow-hidden font-sans text-sm" suppressHydrationWarning>{children}</body>
    </html>
  );
}
