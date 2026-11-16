"""Nội dung trang khoá học và hồ sơ giảng viên cho web công khai - DỮ LIỆU DEMO của trung tâm giả lập Ánh Dương.

Chỉ điền vào ô còn trống (không ghi đè nội dung quản lý đã sửa trên giao diện). Production không chạy file này:
nội dung thật do trung tâm nhập ở trang Danh mục đào tạo.
"""

import json


def _p(*phases: tuple[str, str]) -> list[dict]:
    return [{"ten": t, "noi_dung": n} for t, n in phases]


# mã -> (mô tả ngắn, đối tượng, kết quả đầu ra, lộ trình)
COURSE_CONTENT: dict[str, tuple[str, str, str, list[dict]]] = {
    "ENG-IF": (
        "Lấy lại gốc tiếng Anh và làm quen đủ 4 kỹ năng IELTS.",
        "Người mất gốc hoặc mới bắt đầu, chưa từng thi IELTS.",
        "Nắm chắc ngữ pháp nền, khoảng 2.000 từ vựng học thuật, làm được đề IELTS ở mức mục tiêu 5.0.",
        _p(
            ("Nền tảng", "Phát âm, các thì cơ bản, câu đơn và câu ghép."),
            ("Làm quen 4 kỹ năng", "Dạng bài Listening, Reading; viết đoạn văn ngắn; nói về chủ đề quen thuộc."),
            ("Tăng tốc", "Từ vựng theo chủ đề, chiến lược đọc lướt và nghe ý chính."),
            ("Thi thử", "Hai bài thi thử có chấm và nhận xét chi tiết từng kỹ năng."),
        ),
    ),
    "ENG-II": (
        "Luyện đề chuyên sâu, có cam kết đầu ra 6.5.",
        "Học viên đã đạt khoảng 5.0, cần 6.5 để du học, xét tuyển hoặc tốt nghiệp.",
        "Đạt mục tiêu 6.5 theo điều kiện cam kết của trung tâm.",
        _p(
            ("Chẩn đoán", "Kiểm tra đầu vào, xác định kỹ năng yếu nhất."),
            ("Writing & Speaking", "Cấu trúc Task 1, Task 2; chữa bài viết hằng tuần; luyện nói theo cặp."),
            ("Listening & Reading", "Kỹ thuật xử lý từng dạng câu hỏi, luyện tốc độ."),
            ("Luyện đề", "Thi thử định kỳ trong điều kiện như thi thật."),
        ),
    ),
    "ENG-IM": (
        "Chiến lược band cao cho Writing và Speaking, chữa bài 1-1.",
        "Học viên đã có 6.5, hướng tới 7.5 trở lên.",
        "Bài viết mạch lạc, từ vựng chính xác, nói trôi chảy ở mức band 7.5+.",
        _p(
            ("Phân tích tiêu chí chấm", "Hiểu rõ 4 tiêu chí và lỗi khiến bài dừng ở 6.5-7.0."),
            ("Writing nâng cao", "Lập luận, liên kết ý, từ vựng học thuật; chữa bài 1-1."),
            ("Speaking nâng cao", "Phát triển ý Part 2-3, ngữ điệu và độ trôi chảy."),
            ("Hoàn thiện", "Thi thử và kế hoạch ôn cá nhân trước ngày thi."),
        ),
    ),
    "ENG-T4": (
        "Ôn TOEIC Listening & Reading cho chuẩn đầu ra.",
        "Sinh viên cần chứng chỉ TOEIC 450+ để tốt nghiệp.",
        "Làm chủ cấu trúc đề, đạt mục tiêu 450+.",
        _p(
            ("Ngữ pháp trọng tâm", "Các điểm ngữ pháp thường gặp trong Part 5-6."),
            ("Listening", "Part 1-4, nghe từ khoá và bẫy đáp án."),
            ("Reading", "Part 7, đọc tìm thông tin nhanh."),
            ("Luyện đề", "Đề thi thử đủ 200 câu, phân tích lỗi."),
        ),
    ),
    "ENG-T7": (
        "Luyện đề TOEIC nâng cao, mẹo xử lý Part 5-7.",
        "Người đã có khoảng 500-600, cần 750+ cho hồ sơ xin việc.",
        "Tốc độ làm bài và độ chính xác đủ cho mục tiêu 750+.",
        _p(
            ("Đánh giá", "Thi thử đầu khoá, xác định phần mất điểm."),
            ("Kỹ thuật nâng cao", "Part 3-4 hội thoại dài, Part 7 đoạn kép và ba đoạn."),
            ("Quản lý thời gian", "Chiến lược phân bổ 75 phút Reading."),
            ("Luyện đề", "Đề thi thử hằng tuần, chữa chi tiết."),
        ),
    ),
    "ENG-GT": (
        "Lớp tối đa 12 người, 70% thời lượng luyện nói.",
        "Người đi làm, sinh viên ngại nói, cần phản xạ giao tiếp hằng ngày.",
        "Tự tin giới thiệu bản thân, hỏi đáp và xử lý tình huống thường gặp bằng tiếng Anh.",
        _p(
            ("Phát âm & phản xạ", "Âm khó, nối âm, trả lời nhanh câu hỏi ngắn."),
            ("Tình huống hằng ngày", "Mua sắm, hỏi đường, nhà hàng, du lịch."),
            ("Công việc", "Giới thiệu công việc, gọi điện, họp ngắn."),
            ("Thuyết trình mini", "Mỗi học viên nói 3 phút về chủ đề tự chọn."),
        ),
    ),
    "ENG-V10": (
        "Bám sát cấu trúc đề thi tuyển sinh lớp 10.",
        "Học sinh lớp 8-9 chuẩn bị thi vào lớp 10.",
        "Làm chắc các dạng bài trong đề thi, tránh lỗi mất điểm đáng tiếc.",
        _p(
            ("Hệ thống kiến thức", "Ngữ pháp và từ vựng trọng tâm chương trình THCS."),
            ("Dạng bài", "Phát âm, trọng âm, viết lại câu, đọc hiểu, điền từ."),
            ("Luyện đề", "Đề các năm và đề tự biên soạn theo cấu trúc mới."),
            ("Báo cáo phụ huynh", "Kết quả từng bài thi thử gửi phụ huynh."),
        ),
    ),
    "ENG-BIZ": (
        "Email, họp, thuyết trình và đàm phán bằng tiếng Anh.",
        "Người đi làm cần dùng tiếng Anh với đối tác, khách hàng nước ngoài.",
        "Viết email chuyên nghiệp, điều phối cuộc họp và thuyết trình bằng tiếng Anh.",
        _p(
            ("Email công việc", "Cấu trúc, giọng văn và các mẫu câu thường dùng."),
            ("Cuộc họp", "Mở đầu, đưa ý kiến, đồng ý và phản đối lịch sự."),
            ("Thuyết trình", "Cấu trúc bài trình bày, mô tả số liệu."),
            ("Đàm phán", "Đóng vai tình huống thực tế."),
        ),
    ),
    "OFF-EX": (
        "Hàm, bảng tính, biểu đồ, Pivot Table; luyện thi MOS Excel.",
        "Sinh viên, nhân viên văn phòng muốn dùng Excel thành thạo hoặc lấy chứng chỉ MOS.",
        "Xử lý bảng dữ liệu, lập báo cáo với Pivot Table và sẵn sàng thi MOS Excel.",
        _p(
            ("Cơ bản", "Định dạng, công thức, tham chiếu ô."),
            ("Hàm thông dụng", "IF, VLOOKUP/XLOOKUP, SUMIFS, COUNTIFS, hàm ngày tháng."),
            ("Báo cáo", "Pivot Table, biểu đồ, định dạng có điều kiện."),
            ("Luyện thi MOS", "Đề mô phỏng theo cấu trúc bài thi."),
        ),
    ),
    "OFF-EXA": (
        "Power Query, hàm mảng, báo cáo động cho kế toán.",
        "Kế toán, nhân viên tài chính đã dùng Excel cơ bản.",
        "Tự động hoá các báo cáo lặp lại hằng tháng, giảm thao tác tay.",
        _p(
            ("Làm sạch dữ liệu", "Power Query: gộp file, chuẩn hoá dữ liệu."),
            ("Hàm mảng", "FILTER, UNIQUE, SORT, LET và hàm động."),
            ("Báo cáo động", "Báo cáo công nợ, doanh thu theo kỳ."),
            ("Dự án", "Tự dựng bộ báo cáo cho công việc của mình."),
        ),
    ),
    "OFF-WP": (
        "Soạn thảo văn bản chuẩn và thiết kế slide thuyết trình.",
        "Người cần làm hồ sơ, báo cáo, slide trình bày gọn gàng.",
        "Văn bản đúng thể thức, slide rõ ràng, dễ nhìn.",
        _p(
            ("Word", "Style, mục lục tự động, trộn thư, văn bản hành chính."),
            ("PowerPoint", "Bố cục, màu sắc, hiệu ứng vừa đủ."),
            ("Thực hành", "Làm một bộ hồ sơ và một bài thuyết trình hoàn chỉnh."),
        ),
    ),
    "DEV-PY": (
        "Nhập môn lập trình với Python cho người chưa biết code.",
        "Người mới, học sinh cấp 3, sinh viên trái ngành.",
        "Viết được chương trình nhỏ, hiểu tư duy lập trình làm nền cho Data hoặc Web.",
        _p(
            ("Làm quen", "Biến, kiểu dữ liệu, nhập xuất."),
            ("Điều khiển", "Rẽ nhánh, vòng lặp, hàm."),
            ("Cấu trúc dữ liệu", "List, dict, xử lý file."),
            ("Dự án nhỏ", "Một ứng dụng dòng lệnh hoàn chỉnh."),
        ),
    ),
    "DEV-FE": (
        "HTML, CSS, JavaScript và React; làm 2 dự án web.",
        "Người muốn chuyển ngành hoặc bắt đầu nghề lập trình web.",
        "Hai dự án web đưa vào hồ sơ xin việc.",
        _p(
            ("HTML & CSS", "Bố cục, responsive, Flexbox, Grid."),
            ("JavaScript", "DOM, sự kiện, gọi API."),
            ("React", "Component, state, hook, router."),
            ("Dự án", "Hai dự án có chấm và review code."),
        ),
    ),
    "DEV-JV": (
        "REST API, bảo mật, database và triển khai với Spring Boot.",
        "Người đã biết Java cơ bản, muốn làm back-end.",
        "Xây và triển khai được một REST API hoàn chỉnh.",
        _p(
            ("Spring Boot", "Cấu trúc dự án, dependency injection."),
            ("REST & database", "JPA, quan hệ bảng, phân trang."),
            ("Bảo mật", "Spring Security, JWT."),
            ("Triển khai", "Docker, kiểm thử và dự án cuối khoá."),
        ),
    ),
    "DEV-KID": (
        "Học sinh 10-15 tuổi học lập trình qua làm game.",
        "Học sinh 10-15 tuổi, chưa cần biết lập trình.",
        "Tư duy logic, tự làm game nhỏ với Scratch và Python.",
        _p(
            ("Scratch", "Kéo thả, sự kiện, làm game đầu tiên."),
            ("Tư duy thuật toán", "Vòng lặp, điều kiện qua trò chơi."),
            ("Python", "Chuyển từ kéo thả sang viết code."),
            ("Ngày hội dự án", "Trình bày sản phẩm cho phụ huynh."),
        ),
    ),
    "DA-SQL": (
        "Truy vấn, JOIN, GROUP BY, window function trên dữ liệu kinh doanh.",
        "Người làm báo cáo, muốn tự lấy số liệu thay vì nhờ IT.",
        "Viết truy vấn trả lời câu hỏi kinh doanh từ cơ sở dữ liệu.",
        _p(
            ("Truy vấn cơ bản", "SELECT, WHERE, ORDER BY."),
            ("Tổng hợp", "GROUP BY, JOIN nhiều bảng."),
            ("Nâng cao", "Subquery, CTE, window function."),
            ("Case study", "Phân tích doanh thu, khách hàng."),
        ),
    ),
    "DA-PBI": (
        "Mô hình dữ liệu, DAX và dashboard quản trị.",
        "Người làm báo cáo, quản lý cần dashboard theo dõi kinh doanh.",
        "Tự dựng dashboard cập nhật tự động.",
        _p(
            ("Nhập dữ liệu", "Kết nối nguồn, Power Query."),
            ("Mô hình", "Quan hệ bảng, star schema."),
            ("DAX", "Measure, time intelligence."),
            ("Dashboard", "Thiết kế và chia sẻ báo cáo."),
        ),
    ),
    "DA-PY": (
        "Pandas, trực quan hoá và phân tích khám phá.",
        "Người đã biết Python cơ bản.",
        "Làm sạch, phân tích và trực quan hoá một bộ dữ liệu thực tế.",
        _p(
            ("Pandas", "Đọc, lọc, nhóm và gộp dữ liệu."),
            ("Trực quan hoá", "Matplotlib, Seaborn."),
            ("Phân tích khám phá", "Tìm xu hướng, ngoại lệ."),
            ("Dự án", "Báo cáo phân tích trên dữ liệu thật."),
        ),
    ),
    "DA-FULL": (
        "Lộ trình SQL, Excel, Power BI, Python với dự án cuối khoá.",
        "Người muốn chuyển nghề sang Data Analyst.",
        "Bộ dự án cho hồ sơ xin việc, kèm hỗ trợ viết CV và phỏng vấn thử.",
        _p(
            ("Excel & SQL", "Nền tảng xử lý và truy vấn dữ liệu."),
            ("Power BI", "Dashboard và kể chuyện bằng số liệu."),
            ("Python", "Phân tích nâng cao với Pandas."),
            ("Dự án & nghề nghiệp", "Dự án cuối khoá, CV, phỏng vấn thử."),
        ),
    ),
    "SK-TT": (
        "Cấu trúc bài nói, giọng và ngôn ngữ cơ thể, luyện quay video.",
        "Người ngại nói trước đám đông, cần thuyết trình trong công việc.",
        "Tự tin trình bày 5-10 phút có cấu trúc rõ ràng.",
        _p(
            ("Cấu trúc", "Mở đầu cuốn hút, thân bài, kết luận."),
            ("Giọng & cơ thể", "Ngữ điệu, ánh mắt, tư thế."),
            ("Thực hành", "Quay video và góp ý từng buổi."),
        ),
    ),
    "SK-PV": (
        "Viết CV, trả lời câu hỏi hành vi, phỏng vấn thử.",
        "Sinh viên năm cuối, người đang tìm việc.",
        "CV hoàn chỉnh và kinh nghiệm qua ít nhất một buổi phỏng vấn thử.",
        _p(
            ("CV", "Viết CV theo vị trí ứng tuyển."),
            ("Câu hỏi hành vi", "Trả lời theo cấu trúc STAR."),
            ("Phỏng vấn thử", "Có nhận xét của người làm tuyển dụng."),
        ),
    ),
    "SK-TG": (
        "Lập kế hoạch, ưu tiên công việc, chống trì hoãn.",
        "Sinh viên và người đi làm thường xuyên trễ hạn.",
        "Một hệ thống lập kế hoạch cá nhân dùng được hằng ngày.",
        _p(
            ("Nhìn lại thời gian", "Ghi nhật ký và tìm chỗ thất thoát."),
            ("Ưu tiên", "Ma trận Eisenhower, mục tiêu tuần."),
            ("Duy trì", "Thói quen và công cụ hỗ trợ."),
        ),
    ),
}

TEACHER_BIO = {
    "ThS. Trần Hoàng Nam": "Thạc sĩ Ngôn ngữ Anh, 10 năm luyện thi IELTS. Phụ trách các lớp IELTS Intensive và Master.",
    "Cô Lê Thu Hà": "Chuyên luyện kỹ năng Speaking, từng giảng dạy tiếng Anh giao tiếp cho doanh nghiệp.",
    "Thầy Phạm Quốc Bảo": "Kỹ sư phần mềm, 8 năm phát triển web. Dạy Front-end và Python cơ bản.",
    "Cô Nguyễn Ngọc Mai": "Giáo viên tiếng Anh THCS, phụ trách lớp luyện thi vào lớp 10 và TOEIC.",
    "Thầy Võ Đức Huy": "Chuyên viên phân tích dữ liệu ngành bán lẻ, dạy SQL và Power BI.",
    "ThS. Đặng Minh Khoa": "Thạc sĩ Khoa học dữ liệu, phụ trách lộ trình Data Analyst toàn diện.",
    "Cô Bùi Phương Linh": "Chuyên tiếng Anh thương mại và kỹ năng viết email chuyên nghiệp.",
    "Thầy Hồ Gia Long": "Lập trình viên back-end Java, hướng dẫn lớp Spring Boot và lập trình cho thiếu niên.",
    "Cô Đỗ Thanh Trang": "Chuyên gia tin học văn phòng, có chứng chỉ MOS Master.",
    "ThS. Ngô Hải Sơn": "Thạc sĩ Quản trị nhân lực, huấn luyện kỹ năng thuyết trình và phỏng vấn.",
}


def fill_public_content(conn) -> int:
    """Điền nội dung còn trống. Trả số khoá học được điền."""
    n = 0
    for ma, (short, who, outcome, phases) in COURSE_CONTENT.items():
        cur = conn.execute(
            """UPDATE khoa_hoc SET mo_ta_ngan = coalesce(mo_ta_ngan, %s), doi_tuong = coalesce(doi_tuong, %s),
                      ket_qua = coalesce(ket_qua, %s),
                      lo_trinh = CASE WHEN lo_trinh = '[]'::jsonb THEN %s::jsonb ELSE lo_trinh END
               WHERE ma = %s AND (mo_ta_ngan IS NULL OR doi_tuong IS NULL OR ket_qua IS NULL OR lo_trinh = '[]'::jsonb)""",
            (short, who, outcome, json.dumps(phases, ensure_ascii=False), ma),
        )
        n += cur.rowcount
    for name, bio in TEACHER_BIO.items():
        conn.execute("UPDATE giang_vien SET tieu_su = coalesce(tieu_su, %s) WHERE ho_ten = %s", (bio, name))
    return n
