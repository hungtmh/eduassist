-- EduAssist schema. Chạy bằng: uv run eduassist-setup  (idempotent - chạy lại không sao)
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================================
-- DỮ LIỆU NGHIỆP VỤ (giả lập) - Analytics agent được SELECT các bảng này
-- =====================================================================
CREATE TABLE IF NOT EXISTS khoa_hoc (
    id          SERIAL PRIMARY KEY,
    ma          TEXT UNIQUE NOT NULL,
    ten         TEXT NOT NULL,
    danh_muc    TEXT NOT NULL,
    trinh_do    TEXT NOT NULL,
    hoc_phi     INTEGER NOT NULL CHECK (hoc_phi > 0),
    so_buoi     INTEGER NOT NULL,
    mo_ta       TEXT NOT NULL
);
COMMENT ON TABLE  khoa_hoc IS 'Danh mục khoá học trung tâm đang mở bán';
COMMENT ON COLUMN khoa_hoc.danh_muc IS 'Một trong: Tiếng Anh, Tin học văn phòng, Lập trình, Phân tích dữ liệu, Kỹ năng mềm';
COMMENT ON COLUMN khoa_hoc.trinh_do IS 'Một trong: Cơ bản, Trung cấp, Nâng cao';
COMMENT ON COLUMN khoa_hoc.hoc_phi IS 'Học phí niêm yết trọn khoá, đơn vị VND';

CREATE TABLE IF NOT EXISTS lop_hoc (
    id               SERIAL PRIMARY KEY,
    ma_lop           TEXT UNIQUE NOT NULL,
    khoa_hoc_id      INTEGER NOT NULL REFERENCES khoa_hoc(id),
    ngay_khai_giang  DATE NOT NULL,
    ca_hoc           TEXT NOT NULL CHECK (ca_hoc IN ('sang', 'chieu', 'toi')),
    lich_hoc         TEXT NOT NULL,
    hinh_thuc        TEXT NOT NULL CHECK (hinh_thuc IN ('offline', 'online')),
    si_so_toi_da     INTEGER NOT NULL,
    giang_vien       TEXT NOT NULL,
    trang_thai       TEXT NOT NULL CHECK (trang_thai IN ('sap_khai_giang', 'dang_hoc', 'da_ket_thuc'))
);
COMMENT ON TABLE  lop_hoc IS 'Mỗi khoá học có nhiều lớp (đợt khai giảng)';
COMMENT ON COLUMN lop_hoc.lich_hoc IS 'Các thứ học trong tuần, VD: T2-T4-T6, T3-T5-T7, T7-CN';

CREATE TABLE IF NOT EXISTS hoc_vien (
    id              SERIAL PRIMARY KEY,
    ho_ten          TEXT NOT NULL,
    email           TEXT UNIQUE NOT NULL,
    so_dien_thoai   TEXT NOT NULL,
    nam_sinh        INTEGER NOT NULL,
    thanh_pho       TEXT NOT NULL,
    nguon           TEXT NOT NULL CHECK (nguon IN ('facebook', 'zalo', 'gioi_thieu', 'website', 'tiktok')),
    ngay_dang_ky    DATE NOT NULL
);
COMMENT ON COLUMN hoc_vien.nguon IS 'Kênh học viên biết tới trung tâm';

CREATE TABLE IF NOT EXISTS don_hang (
    id            SERIAL PRIMARY KEY,
    hoc_vien_id   INTEGER NOT NULL REFERENCES hoc_vien(id),
    lop_hoc_id    INTEGER NOT NULL REFERENCES lop_hoc(id),
    ngay_dat      DATE NOT NULL,
    hoc_phi_goc   INTEGER NOT NULL,
    giam_gia      INTEGER NOT NULL DEFAULT 0,
    thanh_tien    INTEGER NOT NULL,
    trang_thai    TEXT NOT NULL CHECK (trang_thai IN
                  ('da_thanh_toan', 'thanh_toan_mot_phan', 'chua_thanh_toan', 'da_huy', 'da_hoan_tien'))
);
COMMENT ON TABLE  don_hang IS 'Một lần học viên đăng ký vào một lớp. Doanh thu = tổng thanh_toan, KHÔNG phải tổng thanh_tien';
COMMENT ON COLUMN don_hang.thanh_tien IS 'Số tiền phải trả = hoc_phi_goc - giam_gia (VND)';
COMMENT ON COLUMN don_hang.trang_thai IS 'da_thanh_toan | thanh_toan_mot_phan | chua_thanh_toan | da_huy | da_hoan_tien';

CREATE TABLE IF NOT EXISTS thanh_toan (
    id                SERIAL PRIMARY KEY,
    don_hang_id       INTEGER NOT NULL REFERENCES don_hang(id),
    ngay_thanh_toan   DATE NOT NULL,
    so_tien           INTEGER NOT NULL,
    phuong_thuc       TEXT NOT NULL CHECK (phuong_thuc IN ('chuyen_khoan', 'tien_mat', 'the'))
);
COMMENT ON TABLE thanh_toan IS 'Các lần thu tiền. Hoàn tiền được ghi là so_tien âm';

CREATE TABLE IF NOT EXISTS voucher (
    id            SERIAL PRIMARY KEY,
    ma            TEXT UNIQUE NOT NULL,
    hoc_vien_id   INTEGER NOT NULL REFERENCES hoc_vien(id),
    phan_tram     INTEGER NOT NULL CHECK (phan_tram BETWEEN 1 AND 30),
    ly_do         TEXT NOT NULL,
    han_su_dung   DATE NOT NULL,
    created_by    TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE voucher IS 'Mã giảm giá đã cấp cho học viên';

-- =====================================================================
-- BẢNG CỦA ỨNG DỤNG - agent_ro KHÔNG được đọc
-- =====================================================================
CREATE TABLE IF NOT EXISTS app_user (
    id             SERIAL PRIMARY KEY,
    username       TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    role           TEXT NOT NULL CHECK (role IN ('student', 'staff', 'manager')),
    display_name   TEXT NOT NULL,
    hoc_vien_id    INTEGER REFERENCES hoc_vien(id)
);

CREATE TABLE IF NOT EXISTS email_log (
    id          SERIAL PRIMARY KEY,
    recipients  TEXT[] NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    sent_by     TEXT NOT NULL,
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Mỗi câu SQL agent đã chạy -> nguồn dữ liệu cho vòng học liên tục
CREATE TABLE IF NOT EXISTS query_log (
    id          SERIAL PRIMARY KEY,
    run_id      TEXT NOT NULL,
    thread_id   TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    question    TEXT NOT NULL,
    sql_text    TEXT NOT NULL,
    ok          BOOLEAN NOT NULL,
    error       TEXT,
    row_count   INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS query_log_run_idx ON query_log (run_id);

CREATE TABLE IF NOT EXISTS feedback (
    id          SERIAL PRIMARY KEY,
    run_id      TEXT NOT NULL,
    thread_id   TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    role        TEXT NOT NULL,
    score       SMALLINT NOT NULL CHECK (score IN (-1, 1)),
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, user_id)
);

-- =====================================================================
-- VECTOR (pgvector) - 384 chiều = paraphrase-multilingual-MiniLM-L12-v2
-- =====================================================================
CREATE TABLE IF NOT EXISTS policy_chunks (
    id         SERIAL PRIMARY KEY,
    source     TEXT NOT NULL,
    section    TEXT NOT NULL,
    content    TEXT NOT NULL,
    embedding  vector(384) NOT NULL
);

CREATE TABLE IF NOT EXISTS sql_examples (
    id          SERIAL PRIMARY KEY,
    question    TEXT UNIQUE NOT NULL,
    sql_text    TEXT NOT NULL,
    source      TEXT NOT NULL CHECK (source IN ('seed', 'feedback')),
    created_by  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    embedding   vector(384) NOT NULL
);
