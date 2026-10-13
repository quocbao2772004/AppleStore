"""Admin explain prompt. Prose may only repeat the report JSON."""

from .chat import CHAT

EXPLAIN = (
    CHAT
    + "\n\nBạn nhận JSON gồm câu hỏi và tool_result. Viết tiếng Việt, ngắn, từ JSON đó. Không gọi tool. Không thêm số, tên, doanh thu hay tồn kho không có trong JSON. Chép nguyên cụm tiền và số đếm, không làm tròn. Câu đầu giữ đúng period và category nếu JSON có. Nếu có note, nói đúng note đó. Khi hỏi một đơn hoặc hỏi của ai, nêu đúng receiver. Không bịa người nhận."
)
