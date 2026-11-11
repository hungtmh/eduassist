-- EduAssist Platform: mở rộng schema prototype thành nền tảng nghiệp vụ (mục 5, 6, 8 của đề xuất).
-- Chạy qua Alembic (migrations/versions/0002_platform.py). Idempotent: chạy lại trên DB đã nâng cấp không sao.
--
-- Nguyên tắc: luật nghiệp vụ nằm ở tầng Service (Python). Ràng buộc ở đây là lưới an toàn cuối cùng
-- (khoá ngoại, CHECK, UNIQUE) để dữ liệu không thể sai kể cả khi có lỗi ở tầng trên.

-- =====================================================================
-- HỆ THỐNG: 6 vai trò
-- =====================================================================
ALTER TABLE app_user DROP CONSTRAINT IF EXISTS app_user_role_check;
UPDATE app_user SET role = 'consultant' WHERE role = 'staff';
ALTER TABLE app_user ADD CONSTRAINT app_user_role_check
    CHECK (role IN ('student', 'consultant', 'academic', 'accountant', 'teacher', 'manager'));
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT true;

-- =====================================================================
-- ĐÀO TẠO: cơ sở, phòng, giảng viên, buổi học
-- =====================================================================
CREATE TABLE IF NOT EXISTS co_so (
    id       SERIAL PRIMARY KEY,
    ten      TEXT UNIQUE NOT NULL,
    dia_chi  TEXT NOT NULL
);
COMMENT ON TABLE co_so IS 'Cơ sở (chi nhánh) của trung tâm';

CREATE TABLE IF NOT EXISTS phong_hoc (
    id        SERIAL PRIMARY KEY,
    co_so_id  INTEGER NOT NULL REFERENCES co_so(id),
    ten       TEXT NOT NULL,
    suc_chua  INTEGER NOT NULL CHECK (suc_chua > 0),
    UNIQUE (co_so_id, ten)
);
COMMENT ON TABLE phong_hoc IS 'Phòng học tại từng cơ sở';

CREATE TABLE IF NOT EXISTS giang_vien (
    id         SERIAL PRIMARY KEY,
    ho_ten     TEXT UNIQUE NOT NULL,
    email      TEXT UNIQUE NOT NULL,
    chuyen_mon TEXT NOT NULL,
    username   TEXT UNIQUE REFERENCES app_user(username) ON DELETE SET NULL
);
COMMENT ON TABLE giang_vien IS 'Giảng viên. lop_hoc.giang_vien_id trỏ tới đây';

ALTER TABLE lop_hoc ADD COLUMN IF NOT EXISTS giang_vien_id INTEGER REFERENCES giang_vien(id);
ALTER TABLE lop_hoc ADD COLUMN IF NOT EXISTS phong_hoc_id INTEGER REFERENCES phong_hoc(id);
ALTER TABLE lop_hoc ADD COLUMN IF NOT EXISTS si_so_toi_thieu INTEGER NOT NULL DEFAULT 8;
ALTER TABLE lop_hoc DROP CONSTRAINT IF EXISTS lop_hoc_trang_thai_check;
ALTER TABLE lop_hoc ADD CONSTRAINT lop_hoc_trang_thai_check
    CHECK (trang_thai IN ('sap_khai_giang', 'dang_hoc', 'da_ket_thuc', 'da_huy'));
COMMENT ON COLUMN lop_hoc.si_so_toi_thieu IS 'Lớp chỉ được khai giảng khi số ghi danh còn hiệu lực đạt mức này';
COMMENT ON COLUMN lop_hoc.trang_thai IS 'sap_khai_giang | dang_hoc | da_ket_thuc | da_huy (huỷ vì không đủ sĩ số)';

CREATE TABLE IF NOT EXISTS buoi_hoc (
    id          SERIAL PRIMARY KEY,
    lop_hoc_id  INTEGER NOT NULL REFERENCES lop_hoc(id),
    so_thu_tu   INTEGER NOT NULL CHECK (so_thu_tu > 0),
    ngay        DATE NOT NULL,
    trang_thai  TEXT NOT NULL DEFAULT 'du_kien' CHECK (trang_thai IN ('du_kien', 'da_hoc', 'nghi')),
    UNIQUE (lop_hoc_id, so_thu_tu)
);
CREATE INDEX IF NOT EXISTS buoi_hoc_ngay_idx ON buoi_hoc (ngay);
COMMENT ON TABLE buoi_hoc IS 'Từng buổi học của một lớp, đánh số 1..so_buoi';

-- =====================================================================
-- GHI DANH & HỌC VỤ
-- don_hang = một lần ghi danh vào một lớp, kiêm hoá đơn của lần ghi danh đó (giữ tên cũ để
-- Text-to-SQL, eval và báo cáo của prototype không gãy).
--   trang_thai     : trạng thái THANH TOÁN (hoá đơn)
--   trang_thai_hoc : trạng thái HỌC (ghi danh)
-- =====================================================================
ALTER TABLE don_hang ADD COLUMN IF NOT EXISTS trang_thai_hoc TEXT NOT NULL DEFAULT 'dang_hoc';
ALTER TABLE don_hang DROP CONSTRAINT IF EXISTS don_hang_trang_thai_hoc_check;
ALTER TABLE don_hang ADD CONSTRAINT don_hang_trang_thai_hoc_check
    CHECK (trang_thai_hoc IN ('cho_thanh_toan', 'dang_hoc', 'bao_luu', 'tam_dung', 'hoan_thanh', 'da_huy'));
ALTER TABLE don_hang ADD COLUMN IF NOT EXISTS tra_gop BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE don_hang ADD COLUMN IF NOT EXISTS voucher_id INTEGER REFERENCES voucher(id);
ALTER TABLE don_hang ADD COLUMN IF NOT EXISTS da_chuyen_lop BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE don_hang ADD COLUMN IF NOT EXISTS created_by TEXT;
COMMENT ON COLUMN don_hang.trang_thai_hoc IS
    'Trạng thái học: cho_thanh_toan | dang_hoc | bao_luu | tam_dung (do nợ quá hạn) | hoan_thanh | da_huy';
COMMENT ON COLUMN don_hang.tra_gop IS 'true = chia 2 đợt (chỉ cho khoá từ 5.000.000đ)';

CREATE TABLE IF NOT EXISTS dot_thanh_toan (
    id              SERIAL PRIMARY KEY,
    don_hang_id     INTEGER NOT NULL REFERENCES don_hang(id),
    so_thu_tu       INTEGER NOT NULL CHECK (so_thu_tu IN (1, 2)),
    so_tien         INTEGER NOT NULL CHECK (so_tien > 0),
    han_thanh_toan  DATE NOT NULL,
    trang_thai      TEXT NOT NULL DEFAULT 'chua_thanh_toan'
                    CHECK (trang_thai IN ('chua_thanh_toan', 'da_thanh_toan', 'qua_han', 'da_huy')),
    UNIQUE (don_hang_id, so_thu_tu)
);
CREATE INDEX IF NOT EXISTS dot_thanh_toan_han_idx ON dot_thanh_toan (han_thanh_toan) WHERE trang_thai <> 'da_thanh_toan';
COMMENT ON TABLE dot_thanh_toan IS 'Các đợt phải thu của một hoá đơn (1 đợt, hoặc 2 đợt nếu trả góp) và hạn của từng đợt';
COMMENT ON COLUMN dot_thanh_toan.trang_thai IS 'chua_thanh_toan | da_thanh_toan | qua_han (quá hạn mà chưa đóng) | da_huy';

ALTER TABLE thanh_toan ADD COLUMN IF NOT EXISTS ghi_chu TEXT;
ALTER TABLE thanh_toan ADD COLUMN IF NOT EXISTS created_by TEXT;

CREATE TABLE IF NOT EXISTS diem_danh (
    buoi_hoc_id  INTEGER NOT NULL REFERENCES buoi_hoc(id),
    don_hang_id  INTEGER NOT NULL REFERENCES don_hang(id),
    trang_thai   TEXT NOT NULL CHECK (trang_thai IN ('co_mat', 'vang', 'vang_co_phep', 'di_tre')),
    ghi_chu      TEXT,
    updated_by   TEXT NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (buoi_hoc_id, don_hang_id)
);
COMMENT ON TABLE diem_danh IS 'Điểm danh: một dòng cho mỗi (buổi học, ghi danh)';
COMMENT ON COLUMN diem_danh.trang_thai IS 'co_mat | vang | vang_co_phep | di_tre (trễ quá 15 phút = vắng nửa buổi)';

CREATE TABLE IF NOT EXISTS diem_so (
    id           SERIAL PRIMARY KEY,
    don_hang_id  INTEGER NOT NULL REFERENCES don_hang(id),
    loai         TEXT NOT NULL CHECK (loai IN ('giua_khoa', 'cuoi_khoa')),
    diem         NUMERIC(5, 2) NOT NULL CHECK (diem BETWEEN 0 AND 100),
    nhan_xet     TEXT,
    updated_by   TEXT NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (don_hang_id, loai)
);

CREATE TABLE IF NOT EXISTS bao_luu (
    id           SERIAL PRIMARY KEY,
    don_hang_id  INTEGER NOT NULL REFERENCES don_hang(id),
    tu_ngay      DATE NOT NULL,
    den_ngay     DATE NOT NULL,
    phi          INTEGER NOT NULL DEFAULT 300000,
    ly_do        TEXT NOT NULL,
    created_by   TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (den_ngay > tu_ngay)
);

CREATE TABLE IF NOT EXISTS hoan_phi (
    id            SERIAL PRIMARY KEY,
    don_hang_id   INTEGER NOT NULL REFERENCES don_hang(id),
    da_dong       INTEGER NOT NULL,
    ty_le         INTEGER NOT NULL CHECK (ty_le BETWEEN 0 AND 100),
    so_tien       INTEGER NOT NULL CHECK (so_tien >= 0),
    can_cu        TEXT NOT NULL,
    trang_thai    TEXT NOT NULL DEFAULT 'cho_duyet' CHECK (trang_thai IN ('cho_duyet', 'da_duyet', 'tu_choi')),
    created_by    TEXT NOT NULL,
    approved_by   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE hoan_phi IS 'Yêu cầu hoàn phí; ty_le tính bằng code theo thời điểm huỷ (chính sách 03)';

-- Yêu cầu học viên gửi từ cổng học viên (bảo lưu, hoàn phí, chuyển lớp, khác)
CREATE TABLE IF NOT EXISTS yeu_cau (
    id            SERIAL PRIMARY KEY,
    hoc_vien_id   INTEGER NOT NULL REFERENCES hoc_vien(id),
    don_hang_id   INTEGER REFERENCES don_hang(id),
    loai          TEXT NOT NULL CHECK (loai IN ('bao_luu', 'hoan_phi', 'chuyen_lop', 'khac')),
    noi_dung      TEXT NOT NULL,
    trang_thai    TEXT NOT NULL DEFAULT 'moi' CHECK (trang_thai IN ('moi', 'dang_xu_ly', 'da_xu_ly', 'tu_choi')),
    phan_hoi      TEXT,
    xu_ly_boi     TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- TUYỂN SINH (CRM)
-- =====================================================================
CREATE TABLE IF NOT EXISTS khach_tiem_nang (
    id                 SERIAL PRIMARY KEY,
    ho_ten             TEXT NOT NULL,
    so_dien_thoai      TEXT NOT NULL,
    email              TEXT,
    nguon              TEXT NOT NULL CHECK (nguon IN ('facebook', 'zalo', 'gioi_thieu', 'website', 'tiktok', 'walk_in')),
    nhu_cau            TEXT NOT NULL DEFAULT '',
    khoa_quan_tam_id   INTEGER REFERENCES khoa_hoc(id),
    trang_thai         TEXT NOT NULL DEFAULT 'moi'
                       CHECK (trang_thai IN ('moi', 'da_lien_he', 'hen_hoc_thu', 'da_ghi_danh', 'khong_tiep_tuc')),
    phu_trach          TEXT REFERENCES app_user(username),
    diem               INTEGER CHECK (diem BETWEEN 0 AND 100),
    lien_he_cuoi       TIMESTAMPTZ,
    ly_do_dung         TEXT,
    hoc_vien_id        INTEGER REFERENCES hoc_vien(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS khach_tiem_nang_trang_thai_idx ON khach_tiem_nang (trang_thai);
COMMENT ON TABLE khach_tiem_nang IS 'Khách tiềm năng (lead) của tư vấn viên';
COMMENT ON COLUMN khach_tiem_nang.trang_thai IS 'moi -> da_lien_he -> hen_hoc_thu -> da_ghi_danh, hoặc -> khong_tiep_tuc';
COMMENT ON COLUMN khach_tiem_nang.diem IS 'Điểm tiềm năng 0-100 do agent tuyển sinh chấm';

CREATE TABLE IF NOT EXISTS lich_hen (
    id          SERIAL PRIMARY KEY,
    khach_id    INTEGER NOT NULL REFERENCES khach_tiem_nang(id),
    loai        TEXT NOT NULL CHECK (loai IN ('tu_van', 'hoc_thu')),
    thoi_gian   TIMESTAMPTZ NOT NULL,
    lop_hoc_id  INTEGER REFERENCES lop_hoc(id),
    ket_qua     TEXT,
    created_by  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS viec_can_lam (
    id                SERIAL PRIMARY KEY,
    tieu_de           TEXT NOT NULL,
    mo_ta             TEXT NOT NULL DEFAULT '',
    nguoi_phu_trach   TEXT REFERENCES app_user(username),
    han               DATE NOT NULL,
    loai_doi_tuong    TEXT,
    doi_tuong_id      INTEGER,
    trang_thai        TEXT NOT NULL DEFAULT 'mo' CHECK (trang_thai IN ('mo', 'xong', 'huy')),
    khoa_chong_trung  TEXT UNIQUE,
    created_by        TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- THÔNG BÁO
-- =====================================================================
ALTER TABLE email_log ADD COLUMN IF NOT EXISTS loai TEXT;
ALTER TABLE email_log ADD COLUMN IF NOT EXISTS hoc_vien_id INTEGER REFERENCES hoc_vien(id);
ALTER TABLE email_log ADD COLUMN IF NOT EXISTS de_xuat_id INTEGER;
CREATE INDEX IF NOT EXISTS email_log_dedupe_idx ON email_log (loai, hoc_vien_id, sent_at);

CREATE TABLE IF NOT EXISTS thong_bao (
    id          SERIAL PRIMARY KEY,
    nguoi_nhan  TEXT NOT NULL,          -- username, hoặc 'role:<vai trò>' cho cả nhóm
    tieu_de     TEXT NOT NULL,
    noi_dung    TEXT NOT NULL,
    lien_ket    TEXT,
    da_doc      BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS thong_bao_nguoi_nhan_idx ON thong_bao (nguoi_nhan, da_doc);

-- =====================================================================
-- TẦNG AGENTIC
-- =====================================================================
CREATE TABLE IF NOT EXISTS chinh_sach_tu_chu (
    loai_hanh_dong  TEXT PRIMARY KEY,
    muc             TEXT NOT NULL CHECK (muc IN ('L0', 'L1', 'L2', 'cam')),
    han_muc_ngay    INTEGER NOT NULL DEFAULT 0 CHECK (han_muc_ngay >= 0),
    mo_ta           TEXT NOT NULL,
    updated_by      TEXT NOT NULL DEFAULT 'system',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE chinh_sach_tu_chu IS
    'Mức tự chủ theo TỪNG LOẠI THAO TÁC: L0 gợi ý, L1 chờ duyệt, L2 tự động trong han_muc_ngay, cam = không bao giờ';

CREATE TABLE IF NOT EXISTS lan_chay_agent (
    id          SERIAL PRIMARY KEY,
    agent       TEXT NOT NULL,
    kich_hoat   TEXT NOT NULL,           -- 'lich:daily', 'su_kien:<loai>', 'thu_cong:<username>'
    ngay_nghiep_vu DATE NOT NULL,
    bat_dau     TIMESTAMPTZ NOT NULL DEFAULT now(),
    ket_thuc    TIMESTAMPTZ,
    trang_thai  TEXT NOT NULL DEFAULT 'dang_chay' CHECK (trang_thai IN ('dang_chay', 'xong', 'loi')),
    so_de_xuat  INTEGER NOT NULL DEFAULT 0,
    so_tu_dong  INTEGER NOT NULL DEFAULT 0,
    tom_tat     TEXT,
    loi         TEXT
);
CREATE INDEX IF NOT EXISTS lan_chay_agent_agent_idx ON lan_chay_agent (agent, bat_dau DESC);

CREATE TABLE IF NOT EXISTS de_xuat_agent (
    id                SERIAL PRIMARY KEY,
    agent             TEXT NOT NULL,
    loai_hanh_dong    TEXT NOT NULL,
    tieu_de           TEXT NOT NULL,
    tom_tat           TEXT NOT NULL,
    tham_so           JSONB NOT NULL DEFAULT '{}',   -- vài tham số ngắn LLM/agent chọn
    du_lieu           JSONB NOT NULL DEFAULT '{}',   -- dữ liệu sẽ được dùng khi thực thi, DO CODE TÍNH
    can_cu            JSONB NOT NULL DEFAULT '[]',   -- căn cứ dẫn tới đề xuất (để người duyệt kiểm tra)
    muc_tu_chu        TEXT NOT NULL CHECK (muc_tu_chu IN ('L0', 'L1', 'L2')),
    trang_thai        TEXT NOT NULL DEFAULT 'cho_duyet'
                      CHECK (trang_thai IN ('goi_y', 'da_xem', 'cho_duyet', 'da_duyet', 'da_thuc_hien',
                                            'that_bai', 'tu_choi', 'het_han')),
    khoa_chong_trung  TEXT UNIQUE,
    nguoi_yeu_cau     TEXT NOT NULL,                 -- agent:<tên> hoặc username (khi ra lệnh qua chat)
    vai_tro_thuc_thi  TEXT NOT NULL,                 -- vai trò dùng để kiểm tra quyền khi thực thi
    nguoi_duyet       TEXT,
    da_sua            BOOLEAN NOT NULL DEFAULT false,
    ly_do_tu_choi     TEXT,
    ket_qua           TEXT,
    lan_chay_id       INTEGER REFERENCES lan_chay_agent(id),
    ngay_nghiep_vu    DATE NOT NULL DEFAULT current_date,
    het_han_luc       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at        TIMESTAMPTZ,
    executed_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS de_xuat_agent_trang_thai_idx ON de_xuat_agent (trang_thai, created_at DESC);
COMMENT ON TABLE de_xuat_agent IS
    'Đề xuất của agent: goi_y/da_xem (L0) | cho_duyet -> da_duyet -> da_thuc_hien/that_bai | tu_choi | het_han';

CREATE TABLE IF NOT EXISTS outbox_su_kien (
    id            BIGSERIAL PRIMARY KEY,
    loai          TEXT NOT NULL,
    payload       JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at  TIMESTAMPTZ,
    attempts      INTEGER NOT NULL DEFAULT 0,
    error         TEXT
);
CREATE INDEX IF NOT EXISTS outbox_pending_idx ON outbox_su_kien (id) WHERE processed_at IS NULL;
COMMENT ON TABLE outbox_su_kien IS 'Sự kiện nghiệp vụ, ghi CÙNG transaction với thay đổi dữ liệu; worker đọc để kích hoạt agent';

CREATE TABLE IF NOT EXISTS audit_log (
    id             BIGSERIAL PRIMARY KEY,
    actor          TEXT NOT NULL,          -- username hoặc agent:<tên>
    actor_role     TEXT NOT NULL,
    hanh_dong      TEXT NOT NULL,
    doi_tuong      TEXT NOT NULL,
    doi_tuong_id   TEXT,
    truoc          JSONB,
    sau            JSONB,
    ly_do          TEXT,
    de_xuat_id     INTEGER REFERENCES de_xuat_agent(id),
    duyet_boi      TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_log_created_idx ON audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_obj_idx ON audit_log (doi_tuong, doi_tuong_id);
