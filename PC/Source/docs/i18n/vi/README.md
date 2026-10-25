# SUMUWW · Tài liệu

SUMUWW PC 0.57.46 · Nút xác thực, lưu trữ, truyền và cung cấp dữ liệu chuỗi.

## Định dạng chữ ký

SDK mã nguồn tùy chọn tạo giao dịch và kiểm tra chữ ký được cung cấp mà không cần khóa hay mạng. Đây không phải chương trình ký hoặc lệnh của nút. Giới hạn thanh toán P2WPKH thuộc định dạng ví dụ, không phải nút. Ví cá nhân hiện có vẫn dùng được.

## API RPC và HTTP

validateaddress kiểm tra checksum và mạng đã chọn. decoded_only của decoderawtransaction chỉ nghĩa là giải mã, không xác nhận chữ ký hay giao dịch. OP_RETURN lưu dữ liệu cho chương trình ngoài. Nút có thêm truy vấn phí, kiểm tra trước khi gửi, trạng thái thay thế RBF và đọc dữ liệu theo thứ tự khối. Giao dịch thay thế được xác minh trước khi xóa giao dịch đang chờ. Đa chữ ký và đầu ra khóa đã được triển khai để thử kích hoạt trong môi trường riêng; chưa kích hoạt trên mạng công khai.

## Kiểm chứng

Cài các phụ thuộc rồi chạy python examples/node_contract.py từ mã nguồn. Khóa thử nghiệm công khai và regtest tạm thời kiểm tra gửi, từ chối, xác nhận, tái tổ chức và lưu giữ dữ liệu. Không dùng tiền thật, hồ sơ người dùng hoặc thiết bị ký phần cứng.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Giao diện nút](EXCHANGE_INTEGRATION.html) · [API RPC và HTTP](RPC_API.html) · [Vận hành nút](NETWORK_RUNBOOK.html) · [Ghi chú phiên bản](RELEASE_NOTES.html) · [Kiểm chứng](EXCHANGE_EXAMPLES.html)

[Tài liệu chi tiết tiếng Anh](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
