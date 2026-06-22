# CurioFeed Crawler 🕷️

Đây là thành phần cốt lõi của dự án CurioFeed. Crawler được viết bằng Python, sử dụng thư viện **Playwright** để giả lập trình duyệt và tự động hóa việc lấy dữ liệu (cào bài) từ các Fanpage/Group Facebook công khai.

## Yêu cầu hệ thống
- Python 3.10+
- Trình duyệt Chromium (được cài thông qua Playwright)

## Hướng dẫn cài đặt

1. Mở terminal và di chuyển vào thư mục `crawl`:
   ```bash
   cd crawl
   ```

2. Khởi tạo môi trường ảo (venv) để tránh xung đột thư viện:
   ```bash
   python -m venv venv
   ```

3. Kích hoạt môi trường ảo:
   - **Trên Windows (Command Prompt / PowerShell):**
     ```bash
     venv\Scripts\activate
     ```
   - **Trên Mac/Linux:**
     ```bash
     source venv/bin/activate
     ```

4. Cài đặt các thư viện Python:
   ```bash
   pip install -r requirements.txt
   ```

5. Cài đặt trình duyệt giả lập cho Playwright:
   ```bash
   playwright install chromium
   ```

## Hướng dẫn sử dụng

### 1. Chạy thử nghiệm (Test Mode - KHÔNG CẦN DATABASE)
Dùng lệnh này để kiểm tra xem Crawler lấy dữ liệu từ Facebook có chuẩn không. Chế độ này sẽ chỉ chạy 1 Fanpage đầu tiên, in nội dung và số lượt tương tác ra màn hình, và **không** lưu vào Database.

```bash
python crawler.py --test
```

### 2. Chạy thật (Production)
Chế độ này sẽ cào toàn bộ danh sách trong file `sources.json` và lưu vào MongoDB. 
**Yêu cầu:** Bạn phải sao chép file `.env.example` thành `.env` và điền `MONGODB_URI` vào.

```bash
python crawler.py
```

### 3. Tự động hóa cào dữ liệu (Cronjob)
Dùng script này nếu bạn muốn cắm máy chạy liên tục, nó sẽ tự động kích hoạt crawler cào 4 lần mỗi ngày.

```bash
python scheduler.py
```

## Cấu trúc file quan trọng
- `crawler.py`: Logic cào bài từ Facebook (cuộn trang, tránh bot, bóc tách HTML).
- `cleaner.py`: Logic làm sạch văn bản, bỏ emoji lỗi, mã băm (SHA256) tránh trùng lặp.
- `scheduler.py`: Đặt lịch chạy crawler.
- `sources.json`: Danh sách Fanpage/Group nguồn để cào.
