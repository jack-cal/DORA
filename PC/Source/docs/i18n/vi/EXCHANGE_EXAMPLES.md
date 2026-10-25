# SUMUWW · Kiểm chứng

SUMUWW PC 0.57.46 · Nút xác thực, lưu trữ, truyền và cung cấp dữ liệu chuỗi.

## Định dạng chữ ký

SDK mã nguồn tùy chọn tạo giao dịch và kiểm tra chữ ký được cung cấp mà không cần khóa hay mạng. Đây không phải chương trình ký hoặc lệnh của nút. Giới hạn thanh toán P2WPKH thuộc định dạng ví dụ, không phải nút. Ví cá nhân hiện có vẫn dùng được.

## Kiểm chứng

Cài các phụ thuộc rồi chạy python examples/node_contract.py từ mã nguồn. Khóa thử nghiệm công khai và regtest tạm thời kiểm tra gửi, từ chối, xác nhận, tái tổ chức và lưu giữ dữ liệu. Không dùng tiền thật, hồ sơ người dùng hoặc thiết bị ký phần cứng.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Tài liệu](README.html) · [Giao diện nút](EXCHANGE_INTEGRATION.html) · [API RPC và HTTP](RPC_API.html) · [Vận hành nút](NETWORK_RUNBOOK.html) · [Ghi chú phiên bản](RELEASE_NOTES.html)

[Tài liệu chi tiết tiếng Anh](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
