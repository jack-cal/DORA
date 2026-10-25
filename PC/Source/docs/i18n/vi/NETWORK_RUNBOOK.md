# SUMUWW · Vận hành nút

SUMUWW PC 0.57.46 · Nút xác thực, lưu trữ, truyền và cung cấp dữ liệu chuỗi.

## Mạng và địa chỉ

Mạng công khai là `sumuww`, bí danh nội bộ là `dora`. Kiểm tra hash khối khởi nguyên bên dưới. Địa chỉ gốc dùng witness v0 P2WPKH và HASH160 của khóa công khai secp256k1 nén. Không bắt buộc memo hay tag. Từ chối sai mạng và checksum không hợp lệ. Ghi lại nhánh HD nhận/tiền thừa và chỉ số; không giả định đường dẫn suy dẫn của Bitcoin.

## Xác thực và giới hạn

Chủ động bật RPC tại loopback dạng số `127.0.0.1:18443` với Bearer token riêng tư. Không cung cấp mở khóa ví hay ký từ xa. Dùng dịch vụ cục bộ hoặc đường hầm có xác thực; yêu cầu trình duyệt Origin/Referer bị từ chối. JSON-RPC dùng POST `/rpc`, `params` dạng đối tượng/mảng và `id`; thông báo trả HTTP 204. Giới hạn: thân 8004096 byte, header 8192, lô 16, yêu cầu đồng thời 16, hạn 10 giây; limit 1–1000, offset 0–1000000. Có 28 phương thức và 11 tuyến REST.

## Tra cứu giao dịch và khối

`getrawtransaction` tìm trong chuỗi hoạt động và mempool, không tìm giao dịch chỉ còn ở nhánh bị loại. Đầu vào chỉ ra đầu ra trước đó, không phải một địa chỉ người gửi duy nhất. `getblock` nhận `verbose` Boolean; khối lưu nhưng không hoạt động có `active=false`, `confirmations=-1`. Vẫn lấy được giao dịch thô qua hash khối. `findspendingtransaction` chỉ tìm khoản chi đã xác nhận trong chuỗi hoạt động; null không chứng minh khả dụng. Kiểm tra `gettxout` với `include_mempool=true`. Số xác nhận và trạng thái hoạt động có thể đổi sau tái tổ chức.

## Kiểm chứng

Cài các phụ thuộc rồi chạy python examples/node_contract.py từ mã nguồn. Khóa thử nghiệm công khai và regtest tạm thời kiểm tra gửi, từ chối, xác nhận, tái tổ chức và lưu giữ dữ liệu. Không dùng tiền thật, hồ sơ người dùng hoặc thiết bị ký phần cứng.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Tài liệu](README.html) · [Giao diện nút](EXCHANGE_INTEGRATION.html) · [API RPC và HTTP](RPC_API.html) · [Ghi chú phiên bản](RELEASE_NOTES.html) · [Kiểm chứng](EXCHANGE_EXAMPLES.html)

[Tài liệu chi tiết tiếng Anh](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
