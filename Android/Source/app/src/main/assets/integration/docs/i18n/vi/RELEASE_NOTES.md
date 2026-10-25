# SUMUWW Android 0.6.95 · Ghi chú phiên bản

SUMUWW Android 0.6.95 · Nút xác thực, lưu trữ, truyền và cung cấp dữ liệu chuỗi.

Đặc tả API mô tả lõi nút tích hợp. Ứng dụng Android không có màn hình cấu hình RPC.

## API RPC và HTTP

validateaddress kiểm tra checksum và mạng đã chọn. decoded_only của decoderawtransaction chỉ nghĩa là giải mã, không xác nhận chữ ký hay giao dịch. OP_RETURN lưu dữ liệu cho chương trình ngoài. Nút có thêm truy vấn phí, kiểm tra trước khi gửi, trạng thái thay thế RBF và đọc dữ liệu theo thứ tự khối. Giao dịch thay thế được xác minh trước khi xóa giao dịch đang chờ. Đa chữ ký và đầu ra khóa đã được triển khai để thử kích hoạt trong môi trường riêng; chưa kích hoạt trên mạng công khai.

[API_CONTRACT.json](../../../API_CONTRACT.json)
