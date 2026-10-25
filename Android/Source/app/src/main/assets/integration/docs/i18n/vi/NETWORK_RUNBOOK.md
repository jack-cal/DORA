# SUMUWW Android 0.6.95 · Vận hành nút

SUMUWW Android 0.6.95 · Nút xác thực, lưu trữ, truyền và cung cấp dữ liệu chuỗi.

## Mạng và địa chỉ

Mạng công khai là `sumuww`, bí danh nội bộ là `dora`. Kiểm tra hash khối khởi nguyên bên dưới. Địa chỉ gốc dùng witness v0 P2WPKH và HASH160 của khóa công khai secp256k1 nén. Không bắt buộc memo hay tag. Từ chối sai mạng và checksum không hợp lệ. Ghi lại nhánh HD nhận/tiền thừa và chỉ số; không giả định đường dẫn suy dẫn của Bitcoin.

## Tra cứu giao dịch và khối

`getrawtransaction` tìm trong chuỗi hoạt động và mempool, không tìm giao dịch chỉ còn ở nhánh bị loại. Đầu vào chỉ ra đầu ra trước đó, không phải một địa chỉ người gửi duy nhất. `getblock` nhận `verbose` Boolean; khối lưu nhưng không hoạt động có `active=false`, `confirmations=-1`. Vẫn lấy được giao dịch thô qua hash khối. `findspendingtransaction` chỉ tìm khoản chi đã xác nhận trong chuỗi hoạt động; null không chứng minh khả dụng. Kiểm tra `gettxout` với `include_mempool=true`. Số xác nhận và trạng thái hoạt động có thể đổi sau tái tổ chức.

[API_CONTRACT.json](../../../API_CONTRACT.json)
