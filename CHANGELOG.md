# Changelog

Theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/) và [SemVer](https://semver.org/lang/vi/).

## [0.2.0] - 2026-11-23

### Thêm

- Tuỳ chọn `--env KHOA=GIA_TRI` truyền biến môi trường cho ứng dụng (cả khi chạy lẫn khi cài tác vụ).
- Đánh dấu `py.typed` (PEP 561): dự án khác dùng thư viện sẽ nhận được thông tin kiểu.

### Cải thiện

- CI kiểm tra kiểu tĩnh bằng mypy ở chế độ strict.
- CI đo độ phủ test (branch coverage), fail nếu dưới 80%.
- GitHub Actions nâng lên bản mới (checkout v7, setup-python v7).

## [0.1.0] - 2026-11-23

### Thêm

- Bản phát hành đầu tiên. Giám sát tiến trình với backoff và giới hạn vòng chết, log xoay vòng, kiểm tra sức khoẻ HTTP, cài tác vụ Task Scheduler.
