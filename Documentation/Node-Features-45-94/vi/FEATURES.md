# SUMUWW · 0.57.45 / 0.6.94

Nút có thêm truy vấn phí, kiểm tra trước khi gửi, trạng thái thay thế RBF và đọc dữ liệu theo thứ tự khối. Giao dịch thay thế được xác minh trước khi xóa giao dịch đang chờ. Đa chữ ký và đầu ra khóa đã được triển khai để thử kích hoạt trong môi trường riêng; chưa kích hoạt trên mạng công khai.

1 SMW = 100.000.000 yugeon. Phí tự động có ba mức dựa trên dữ liệu quan sát cục bộ, không bảo đảm thời gian xác nhận. Bạn có thể nhập mức phí yugeon/vB. Hãy kiểm tra phí cuối cùng và tổng số SMW trước khi gửi. Giao dịch bị từ chối không làm giảm số dư.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

Phí tự động dựa trên lượng dữ liệu đang chờ, dung lượng khối và mức ưu tiên của giao dịch. Không sử dụng phí từ các khối cũ. Khi hàng đợi ngắn, mức phí tối thiểu được giữ nguyên. Bản xem trước được cập nhật; bước xác nhận cuối cùng cố định phí. Dữ liệu phản ánh nút cục bộ đang kết nối, không phải mọi nút.

Lịch sử thay thế giao dịch do nút này ghi nhận được giữ lại sau khi khởi động lại ví. Giao dịch bị loại bỏ không ảnh hưởng đến số dư.

Trình khám phá hiển thị các điều kiện đa chữ ký và khóa đầu ra đã được công khai. Chưa có lịch kích hoạt trên mạng công khai.
