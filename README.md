# 🌊 Ocean Chat - Ứng dụng Trò chuyện Thời gian Thực (Real-time Chat App)

Ocean Chat là ứng dụng nhắn tin thời gian thực được xây dựng bằng Flask (Python) và Flask-SocketIO (WebSockets).

## 🚀 Hướng dẫn Chạy ứng dụng trên Máy cục bộ (Local)

### 1. Cài đặt các thư viện cần thiết
Đảm bảo bạn đã cài đặt Python (phiên bản 3.8 trở lên). Chạy lệnh sau để cài đặt các package trong file `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 2. Chạy ứng dụng
Khởi chạy server Flask bằng lệnh:
```bash
python app.py
```
Sau đó, truy cập ứng dụng tại: [http://localhost:5000](http://localhost:5000) hoặc [http://127.0.0.1:5000](http://127.0.0.1:5000)

### 👥 Tài khoản thử nghiệm (Được tạo sẵn khi chạy lần đầu)
Hệ thống sẽ tự động tạo sẵn các tài khoản sau trong cơ sở dữ liệu SQLite (`instance/chat.db`):
*   **Tài khoản Admin (Quản trị):**
    *   Tên đăng nhập: `admin`
    *   Mật khẩu: `admin123`
*   **Tài khoản Người dùng 1 (Kiểm thử):**
    *   Tên đăng nhập: `user1`
    *   Mật khẩu: `user123`
*   **Tài khoản Người dùng 2 (Kiểm thử):**
    *   Tên đăng nhập: `user2`
    *   Mật khẩu: `user123`

---

## 🐙 Hướng dẫn Đưa mã nguồn lên GitHub

1. Mở terminal tại thư mục dự án và khởi tạo Git:
   ```bash
   git init
   ```
2. Thêm tất cả các file vào Git (ngoại trừ các file trong `.gitignore`):
   ```bash
   git add .
   ```
3. Commit mã nguồn:
   ```bash
   git commit -m "Initial commit: Ocean Chat Flask app ready"
   ```
4. Tạo một Repository mới trên GitHub của bạn.
5. Liên kết repository cục bộ với GitHub (thay URL bằng link GitHub repo của bạn):
   ```bash
   git remote add origin <URL_REPOSITORY_GITHUB_CUA_BAN>
   ```
6. Đổi tên nhánh chính thành `main` (nếu cần) và đẩy code lên:
   ```bash
   git branch -M main
   git push -u origin main
   ```

---

## 🌐 Hướng dẫn Triển khai (Deployment)

### 🌟 Triển khai lên Render.com hoặc Railway.app (Khuyên dùng - Dễ dàng & Miễn phí/Rất rẻ)
Các nền tảng PaaS này hỗ trợ kết nối trực tiếp với GitHub và tự động deploy ứng dụng Python Flask:

#### Triển khai trên Render:
1. Đăng nhập vào [Render.com](https://render.com/) bằng tài khoản GitHub của bạn.
2. Chọn **New** -> **Web Service**.
3. Kết nối với Repository GitHub của `Ocean_Chat`.
4. Điền các thông tin cấu hình:
   *   **Runtime:** `Python`
   *   **Build Command:** `pip install -r requirements.txt`
   *   **Start Command:** `gunicorn --worker-class eventlet -w 1 app:app` (sử dụng gunicorn với worker eventlet để hỗ trợ SocketIO WebSockets ổn định).
5. Click **Create Web Service** và đợi Render biên dịch và cung cấp đường dẫn truy cập miễn phí có HTTPS.
