# SUMUWW · Giao diện nút

SUMUWW PC 0.57.46 · Nút xác thực, lưu trữ, truyền và cung cấp dữ liệu chuỗi.

## Mạng và địa chỉ

Mạng công khai là `sumuww`, bí danh nội bộ là `dora`. Kiểm tra hash khối khởi nguyên bên dưới. Địa chỉ gốc dùng witness v0 P2WPKH và HASH160 của khóa công khai secp256k1 nén. Không bắt buộc memo hay tag. Từ chối sai mạng và checksum không hợp lệ. Ghi lại nhánh HD nhận/tiền thừa và chỉ số; không giả định đường dẫn suy dẫn của Bitcoin.

## Định dạng chữ ký

SDK mã nguồn tùy chọn tạo giao dịch và kiểm tra chữ ký được cung cấp mà không cần khóa hay mạng. Đây không phải chương trình ký hoặc lệnh của nút. Giới hạn thanh toán P2WPKH thuộc định dạng ví dụ, không phải nút. Ví cá nhân hiện có vẫn dùng được.

## API RPC và HTTP

validateaddress kiểm tra checksum và mạng đã chọn. decoded_only của decoderawtransaction chỉ nghĩa là giải mã, không xác nhận chữ ký hay giao dịch. OP_RETURN lưu dữ liệu cho chương trình ngoài. Nút có thêm truy vấn phí, kiểm tra trước khi gửi, trạng thái thay thế RBF và đọc dữ liệu theo thứ tự khối. Giao dịch thay thế được xác minh trước khi xóa giao dịch đang chờ. Đa chữ ký và đầu ra khóa đã được triển khai để thử kích hoạt trong môi trường riêng; chưa kích hoạt trên mạng công khai.

## Xác thực và giới hạn

Chủ động bật RPC tại loopback dạng số `127.0.0.1:18443` với Bearer token riêng tư. Không cung cấp mở khóa ví hay ký từ xa. Dùng dịch vụ cục bộ hoặc đường hầm có xác thực; yêu cầu trình duyệt Origin/Referer bị từ chối. JSON-RPC dùng POST `/rpc`, `params` dạng đối tượng/mảng và `id`; thông báo trả HTTP 204. Giới hạn: thân 8004096 byte, header 8192, lô 16, yêu cầu đồng thời 16, hạn 10 giây; limit 1–1000, offset 0–1000000. Có 28 phương thức và 11 tuyến REST.

## Số tiền và đầu ra khả dụng

`_units` là số nguyên đơn vị nhỏ nhất; `_smw` là chuỗi 8 chữ số thập phân; `_dora` là bí danh tương thích. Không có trường tiền `_sumuww`. 1 SMW = 100000000 đơn vị. `gettxout` không có `spendable` và có thể trả coinbase chưa đủ tuổi. Cần ít nhất 100 xác nhận để tiêu ở khối kế tiếp. Lọc `listunspent` theo `spendable`; available trong `getaddressbalance` loại tiền chưa đủ tuổi và tiền bị dùng trong giao dịch chờ. Đầu ra mới trong mempool chưa được xác nhận. Kiểm tra đỉnh giữa các trang và xác minh lại đầu vào đã chọn.

1 SMW = 100.000.000 yugeon. Phí tự động có ba mức dựa trên dữ liệu quan sát cục bộ, không bảo đảm thời gian xác nhận. Bạn có thể nhập mức phí yugeon/vB. Hãy kiểm tra phí cuối cùng và tổng số SMW trước khi gửi. Giao dịch bị từ chối không làm giảm số dư.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Phí tự động dựa trên lượng dữ liệu đang chờ, dung lượng khối và mức ưu tiên của giao dịch. Không sử dụng phí từ các khối cũ. Khi hàng đợi ngắn, mức phí tối thiểu được giữ nguyên. Bản xem trước được cập nhật; bước xác nhận cuối cùng cố định phí. Dữ liệu phản ánh nút cục bộ đang kết nối, không phải mọi nút.

Lịch sử thay thế giao dịch do nút này ghi nhận được giữ lại sau khi khởi động lại ví. Giao dịch bị loại bỏ không ảnh hưởng đến số dư.

Lịch sử đào tách riêng phát hành mới, phí giao dịch và tổng phần thưởng của từng khối. Số tiền ví của bạn nhận được hiển thị riêng. Khi chỉ nhận một phần, hệ thống không tự suy đoán cách chia hai thành phần. Nút cung cấp 28 phương thức RPC, bao gồm ước tính phí, đồng thời xác minh và chuyển tiếp giao dịch đã ký.

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

[Tài liệu](README.html) · [API RPC và HTTP](RPC_API.html) · [Vận hành nút](NETWORK_RUNBOOK.html) · [Ghi chú phiên bản](RELEASE_NOTES.html) · [Kiểm chứng](EXCHANGE_EXAMPLES.html)

[Tài liệu chi tiết tiếng Anh](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
