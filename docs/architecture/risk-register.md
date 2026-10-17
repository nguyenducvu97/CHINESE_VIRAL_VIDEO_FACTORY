# SỔ TAY QUẢN TRỊ RỦI RO (RISK REGISTER) — CVVF

**Version:** 1.0.0  
**Project:** CHINESE_VIRAL_VIDEO_FACTORY  
**Approved by:** Principal System Architect & DevOps  

---

## 1. MA TRẬN ĐÁNH GIÁ RỦI RO (RISK MATRIX)

| Mã Rủi Ro | Hạng Mục | Rủi Ro Nhận Diện | Mức Độ | Biện Pháp Phòng Ngừa & Giảm Thiểu | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RSK-01** | Hạ tầng | Xung đột cổng mạng & container với dự án `MARKETING_AUTOMATION` hoặc `KIDS_VIDEO_FACTORY` | **CRITICAL** | Sử dụng Isolated Port Matrix (`5438`, `5685`, `3080`). Toàn bộ docker container có prefix `cvvf-`. Tuyệt đối không can thiệp cổng 5432, 80, 5679. | ĐÃ CÔ LẬP |
| **RSK-02** | Tài chính | Phát sinh chi phí API ngoài ý muốn (Gemini API, Veo, Cloud TTS, Cloud Translation) | **HIGH** | Mặc định 100% sử dụng công cụ cục bộ miễn phí (FFmpeg, Whisper, Heuristic scoring). Cơ chế Circuit Breaker tự ngắt khi chạm hạn mức ngày ($0 mặc định). | ĐÃ THIẾT KẾ |
| **RSK-03** | Pháp lý / Bản quyền | Thu thập hoặc xuất bản nội dung vi phạm bản quyền tác giả | **CRITICAL** | Trường `rights_status` bắt buộc. Mặc định `PENDING_VERIFICATION`. Khóa xuất bản tự động; chỉ xuất video khi người dùng duyệt thủ công. | ĐÃ THIẾT KẾ |
| **RSK-04** | Toàn vẹn dữ liệu | Ghi đè, làm biến dạng hoặc hỏng video gốc | **HIGH** | File gốc được gắn cờ `ORIGINAL_PRESERVED`, lưu trữ ở thư mục read-only sau khi tải về, kiểm tra hash SHA-256. Không dùng AI tạo lại hình ảnh trong luồng chuẩn. | ĐÃ THIẾT KẾ |
| **RSK-05** | Nguồn thu thập | Bị khóa IP / Rate limit khi lấy metadata video từ các nguồn công khai | **MEDIUM** | Token-bucket rate limiter, Exponential backoff + jitter ngẫu nhiên. Chế độ Dry-run & Fixture fallback. Không vượt rào cản bảo vệ. | ĐÃ THIẾT KẾ |
| **RSK-06** | Tính trung thực số liệu | Bịa đặt hoặc gán nhầm lượt xem, tương tác khi nguồn không có dữ liệu | **MEDIUM** | Tách bạch rõ `measured_metrics` và `inferred_potential_score`. Gán nhãn `INSUFFICIENT_DATA` khi thiếu dữ liệu, nghiêm cấm sinh số liệu giả. | ĐÃ THIẾT KẾ |
| **RSK-07** | Chất lượng âm thanh | Lồng tiếng bị méo, lệch khẩu hình hoặc lấn át nhạc nền gốc | **MEDIUM** | Thuật toán Tempo Alignment (FFmpeg atempo trong ngưỡng an toàn 0.85x - 1.25x), Audio Ducking hạ BGM xuống 20% khi có thoại, kiểm tra clipping. | ĐÃ THIẾT KẾ |
| **RSK-08** | Phiên bản mã nguồn | Thay đổi code vào các Package đã đóng băng (Frozen Packages) | **HIGH** | Quy chế Frozen Gate: Khi Package chuyển trạng thái `PASS` và `FROZEN`, cấm sửa đổi trực tiếp. Mọi thay đổi phải lập migration proposal. | ĐÃ THIẾT KẾ |

---

## 2. KẾ HOẠCH HÀNH ĐỘNG KHI GẶP SỰ CỐ (INCIDENT RESPONSE PLAN)

1. **Nếu phát hiện xung đột cổng:** Ngay lập tức dừng tiến trình CVVF, không restart dịch vụ khác, kiểm tra lại bằng `Get-NetTCPConnection` và tái cấp phát cổng mới.
2. **Nếu API ngoài báo lỗi hạn mức hoặc tính phí:** Chuyển ngay adapter sang chế độ `OFFLINE_LOCAL` hoặc `MOCK_FIXTURE`, thông báo lên dashboard và ghi log cảnh báo.
3. **Nếu nguồn phát hiện bot/block:** Tạm ngưng thu thập từ nguồn đó trong 60 phút, chuyển sang nguồn dự phòng hoặc xử lý video từ tệp nhập thủ công.
