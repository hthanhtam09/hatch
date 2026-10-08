# Hatch Studio

Tool chạy trên máy để tạo trang tô kiểu "Hatch & Trace" (low-poly + ký hiệu gạch nét) cho sách tô màu bán trên Amazon KDP.

## Cài và chạy (macOS)

Cần Python 3.10+ và Node.js 20+.

```bash
cd /Users/sincosweb/Desktop/Sin/Code/hatch-studio
pnpm install     # lần đầu
pnpm run dev     # chế độ phát triển, sửa giao diện thấy ngay
pnpm start       # build rồi chạy bản tối ưu
```

`pnpm run dev` khởi động hai phần:

| Phần | Cổng | Thư mục |
|---|---|---|
| API Python (Flask): xử lý ảnh, vẽ SVG/PDF, lưu dự án | 5050 | `app.py`, `hatch/` |
| Giao diện Next.js + Tailwind CSS | 3000 | `web/` |

Lần đầu chạy, script tự tạo `.venv`. Mở http://127.0.0.1:3000 trên trình duyệt. Bấm `Ctrl + C` để tắt cả hai.

Giao diện gọi `/api/*` và `/fonts/*` trên chính cổng 3000. Next.js tự chuyển tiếp các request này sang Flask (xem `web/next.config.ts`), nên không cần cấu hình CORS. Nếu API chạy ở địa chỉ khác, đặt biến môi trường `HATCH_API=http://host:port` khi chạy giao diện.

Giao diện HTML cũ vẫn còn ở http://127.0.0.1:5050/legacy để dự phòng.

## Cách dùng

Giao diện chia 3 bước ở thanh trên. Dự án tự lưu vào `data/project.json` mỗi khi bạn thay đổi, mở lại là còn nguyên.

**1. Tranh**
- Bấm **+ Thêm ảnh** hoặc kéo thả nhiều ảnh cùng lúc. Mỗi ảnh tự thành một trang tô trong sách.
- Cột phải dùng để chỉnh mức chi tiết, tỉ lệ mảng trắng/đen, nét chi tiết và khung đen tràn lề.
- Bấm **✎ Sửa mảng** (phím `E`) rồi click vào mảng cần sửa:
  - `0`–`5`: đổi mức tô (trắng, thưa, vừa, dày, chéo, đen)
  - `Q`/`W`: xoay hướng nét 15°
  - `M` rồi click mảng kề bên: gộp hai mảng
  - `S`: tách đôi mảng
  - `⌘Z`: hoàn tác

  Chỉnh sửa tay gắn với thông số chia mảng hiện tại. Nếu đổi số mảng hay cách chia, tool sẽ hỏi trước khi xoá các chỉnh sửa này.
- Có thể xuất riêng từng tranh ra PDF hoặc SVG. File SVG chia sẵn các lớp outlines, guides, fills, details để chỉnh tiếp trong Inkscape.

**2. Ruột sách**
- Nhập tên sách, tác giả, rồi chọn các trang đầu sách: trang tên sách, trang bản quyền, hướng dẫn cách tô, trang khởi động.
- Cũng ở bước này chỉnh trang trắng phía sau, đánh số trang, đáp án cuối sách, bleed, lề, cùng độ đậm và khoảng cách ký hiệu.
- Bên phải hiện toàn bộ các trang theo cặp trang đôi. Bấm vào một trang để xem lớn kèm lề in.
- Mục "Kiểm tra" liệt kê những điểm cần xem lại trước khi nộp KDP. Bấm **Xuất ruột sách PDF** khi xong.

**3. Bìa**
- Chọn tranh đặt trên bìa, nền trắng hoặc đen, và viết đoạn giới thiệu cho bìa sau.
- Độ dày gáy tự tính theo số trang: giấy trắng 0.002252 in/trang, giấy kem 0.0025 in/trang.
- Chữ trên gáy chỉ được in khi sách có từ 80 trang trở lên.
- Ô mã vạch 2 × 1.2 in ở góc dưới phải bìa sau được để trống cho KDP.

Mọi file xuất ra đều có một bản sao trong `data/exports/`. PDF nhúng font Lato (giấy phép SIL OFL, file nằm trong `hatch/fonts/`) đúng yêu cầu KDP.

## Khổ trang và lề KDP

Khổ cắt cố định 8.5 × 11 in.

| | Không bleed | Có bleed |
|---|---|---|
| Kích thước trang PDF | 8.5 × 11 in | 8.625 × 11.25 in |
| Bleed | | 0.125 in ở cạnh ngoài, trên, dưới (cạnh gáy không có) |
| Lề ngoài, trên, dưới tối thiểu | 0.25 in | 0.375 in |

Lề gáy tự tính theo tổng số trang:

| Số trang | Lề gáy tối thiểu |
|---|---|
| 24–150 | 0.375 in |
| 151–300 | 0.5 in |
| 301–500 | 0.625 in |
| 501–700 | 0.75 in |
| 701–828 | 0.875 in |

Trên lề tối thiểu đó, tool cộng thêm:

- **Cộng thêm vào lề KDP**: nới rộng cả 4 lề nếu muốn an toàn hơn.
- **Padding quanh tranh**: khoảng trắng giữa lề an toàn và tranh.

Trang phải (lẻ) có gáy bên trái, trang trái (chẵn) có gáy bên phải. Khi xuất sách, tool tự đổi bên cho từng trang. Mỗi tranh nằm ở trang phải, phía sau là trang trắng để in một mặt. Tổng số trang được làm tròn chẵn và bù đủ 24 trang.

Quy định KDP có thể thay đổi. Hãy kiểm tra lại trang trợ giúp "Set Trim Size, Bleed, and Margins" của KDP, chạy Print Previewer khi tải lên và đặt một bản in thử trước khi phát hành.

## Cấu trúc mã

```
app.py              máy chủ Flask và các API
hatch/engine.py     ảnh -> mảng low-poly, mức sáng tối, hướng nét
hatch/edits.py      chỉnh tay: đổi mức, hướng, gộp, tách mảng
hatch/layout.py     hình học trang KDP: bleed, lề, gáy
hatch/render.py     vẽ ra SVG (xem trước, Inkscape) và PDF vector (nộp KDP)
hatch/pages.py      trang tên sách, bản quyền, hướng dẫn, khởi động, đáp án
hatch/book.py       ghép ruột sách
hatch/cover.py      file bìa theo số trang
hatch/project.py    cấu trúc và giá trị mặc định của dự án
hatch/fonts/        font Lato (OFL) để nhúng vào PDF
static/index.html   giao diện HTML cũ (dự phòng, /legacy)
web/                giao diện Next.js + Tailwind
  app/              layout, trang chính, theme Tailwind (globals.css)
  components/       designs/ (bước 1), book/ (bước 2), cover/ (bước 3), ui.tsx
  lib/              api.ts (gọi Flask), store.ts (zustand + tự lưu), types.ts
tests/              chạy: ./.venv/bin/python -m unittest discover tests
```

## Ghi chú chất lượng

Ảnh chụp thật nhiều chi tiết sẽ cho kết quả rối. Nên đưa vào line art sạch (con vật trên nền trắng hoặc trong suốt), rồi chỉnh tay thêm trong Inkscape hoặc Illustrator nếu cần. Chỉ dùng ảnh bạn có quyền sử dụng thương mại.
