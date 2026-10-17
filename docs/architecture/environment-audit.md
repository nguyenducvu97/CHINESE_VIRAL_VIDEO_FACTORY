# P0 — ENVIRONMENT AUDIT & SAFETY REPORT

**Date:** 2026-10-17  
**Project:** CHINESE_VIRAL_VIDEO_FACTORY (`cvvf`)  
**Workspace:** `d:\KINH KOANH\CHINESE_VIRAL_VIDEO_FACTORY`  
**Auditor:** Principal Software & DevOps Engineer  
**Audit Status:** PASS (Isolation boundaries fully verified)

---

## 1. Mục Đích & Phạm Vi Khảo Sát

Báo cáo này ghi nhận hiện trạng hệ thống hạ tầng, phần cứng, công cụ phát triển, container và mạng trên máy chủ làm việc trước khi triển khai bất kỳ thành phần mã nguồn nào của dự án `CHINESE_VIRAL_VIDEO_FACTORY`.

**Nguyên tắc cốt lõi:**
- Khảo sát hoàn toàn chỉ đọc (read-only).
- Không can thiệp, không dừng, không restart bất kỳ container, database hay service nào hiện hữu.
- Thiết lập ranh giới cách ly (namespace, ports, volumes, directory) tuyệt đối độc lập.

---

## 2. Kết Quả Khảo Sát Hệ Thống & Runtime

### 2.1. Hệ Điều Hành & Phần Cứng
- **Hệ điều hành:** Microsoft Windows 11 Pro 64-bit (`Microsoft Windows NT 10.0.26100.0`).
- **Shell môi trường:** PowerShell / Windows Terminal.
- **Tình trạng phân vùng ổ đĩa `D:\`:** Đầy đủ dung lượng trống để lưu trữ và xử lý video.

### 2.2. Ngôn Ngữ & Runtime Đã Cài Đặt
| Runtime / Công cụ | Phiên bản | Tình trạng | Khả năng sử dụng cho CVVF |
| :--- | :--- | :--- | :--- |
| **Python** | `3.11.9` | Sẵn sàng (pip 24.0, pytest 9.1.1, SQLAlchemy 2.0.54, requests 2.34.2) | Ngôn ngữ backend chính cho Worker, Adapter, ASR & FFmpeg wrapper |
| **Node.js** | `v24.19.0` | Sẵn sàng (npm 11.17.0) | Có thể dùng cho Control Center UI hoặc scraper adapter nếu cần |
| **FFmpeg** | `9.0.2-full_build` | Hoàn hảo (Hỗ trợ x264, x265, libass, libwhisper, libmp3lame, libopus, vulkan, cuda-llvm, v.v.) | Xử lý video, audio, ghép phụ đề SRT và render MP4 nội bộ miễn phí 100% |
| **Git** | `2.55.0.windows.4` | Đã khởi tạo branch `main` độc lập trong thư mục dự án | Quản lý phiên bản mã nguồn cô lập |
| **Docker Engine** | `29.7.2` (Docker Desktop 4.86.0) | Đang chạy | Dùng cho isolated database/queue khi cần |

---

## 3. Khảo Sát Hạ Tầng Đang Chạy (Running Containers & Ports)

### 3.1. Các Container Đang Chạy (TUYỆT ĐỐI KHÔNG CAN THIỆP)
Hệ thống hiện có cụm dịch vụ thuộc dự án `MARKETING_AUTOMATION` đang hoạt động:
1. `marketing_automation-affiliate-postgres-1` (Image: `postgres:17-alpine`)
   - Cổng bind: `0.0.0.0:5432->5432/tcp` (Đang chiếm port 5432 chuẩn)
   - Status: Up (healthy)
2. `marketing_automation-affiliate-nginx-1` (Image: `nginx:alpine`)
   - Cổng bind: `0.0.0.0:80->80/tcp` (Đang chiếm port 80 chuẩn)
   - Status: Up
3. `marketing_automation-affiliate-n8n-1` (Image: `docker.n8n.io/n8nio/n8n:1.60.1`)
   - Cổng bind: `0.0.0.0:5679->5678/tcp` (Đang chiếm port host 5679)
   - Status: Up
4. `marketing_automation-affiliate-redis-1` (Image: `redis:7-alpine`)
   - Cổng: `6379/tcp` (Nội bộ network `marketing_automation_default`)
   - Status: Up (healthy)
5. `marketing_automation-affiliate-control-center-1`
   - Cổng bind: port `3000/tcp`
   - Status: Up

### 3.2. Các Container Đã Dừng (Dự án khác)
- `kvf-n8n`, `kvf-redis`, `kvf-postgres`, `kvf-minio` (thuộc dự án `KIDS_VIDEO_FACTORY`).
- `safekey-runtime2a`, `itims-*`, `it-srm-*`.

### 3.3. Các Volume & Network Hiện Hữu
- **Volumes hiện hữu:** `marketing_automation_*`, `kids_video_factory_*`, `itims_*`, `it-srm_*`, `safekey-*`.
- **Networks hiện hữu:** `marketing_automation_default`, `kids_video_factory_default`, `itims_itims-network`, `it-srm_default`.

---

## 4. Bảng Phân Bổ Tài Nguyên Cách Ly Cho CVVF (Isolation Matrix)

Để đảm bảo 0% nguy cơ xung đột với các hệ thống đang chạy, mọi tài nguyên của `CHINESE_VIRAL_VIDEO_FACTORY` (`cvvf`) được quy hoạch nghiêm ngặt như sau:

| Loại tài nguyên | Tài nguyên cũ đang chiếm | Tài nguyên được cấp riêng cho CVVF | Quy tắc bảo vệ |
| :--- | :--- | :--- | :--- |
| **Directory** | `d:\KINH KOANH\MARKETING_AUTOMATION` etc. | `d:\KINH KOANH\CHINESE_VIRAL_VIDEO_FACTORY` | Chỉ đọc/ghi trong thư mục riêng |
| **Git Repo** | Riêng từng folder | `D:\KINH KOANH\CHINESE_VIRAL_VIDEO_FACTORY\.git` | Không merge/rebase chéo repo khác |
| **PostgreSQL Port** | `5432` (active), `55436` | `5438` (nếu dùng docker) / SQLite dev | Cấm kết nối hoặc migrate vào port 5432 |
| **Redis Port** | `6379` (active) | `6385` (nếu dùng docker) / InMemory dev | Không can thiệp network marketing_automation |
| **n8n Port** | `5679` (active), `5678` | `5685` (nếu tạo instance n8n riêng) | Tuyệt đối không chỉnh sửa workflow n8n cũ |
| **Web UI Port** | `3000` (active), `80` (active) | `3080` hoặc `8085` | Không dùng port 80 hoặc 3000 |
| **Docker Prefix** | `marketing_automation-*`, `kvf-*` | `cvvf-*` | Namespace riêng, network riêng `cvvf_net` |
| **Volume Prefix** | `marketing_automation_*` | `cvvf_*` | Tuyệt đối không mount đè volume cũ |
| **Virtualenv** | Global Python | `.venv` tại thư mục gốc CVVF | Cô lập hoàn toàn thư viện Python |

---

## 5. Kết Luận Audit P0

- **Môi trường:** Đầy đủ công cụ cao cấp (Python 3.11, Node 24, FFmpeg 9.0.2 full, Docker Engine 29.7).
- **Rủi ro xung đột:** ĐÃ ĐƯỢC KHOANH VÙNG VÀ CÔ LẬP HOÀN TOÀN.
- **Đánh giá Gate:** **PASS**. Đủ điều kiện triển khai kiến trúc và tiếp tục sang P1.
