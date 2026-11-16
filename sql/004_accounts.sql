-- 004: tài khoản cho production - khoá tạm khi nhập sai, thu hồi phiên, bắt đổi mật khẩu, đặt lại mật khẩu;
--      khoá học ngừng bán.

ALTER TABLE app_user ADD COLUMN IF NOT EXISTS token_version        INTEGER NOT NULL DEFAULT 0;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS failed_logins        INTEGER NOT NULL DEFAULT 0;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS locked_until         TIMESTAMPTZ;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS last_login_at        TIMESTAMPTZ;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS password_changed_at  TIMESTAMPTZ;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS created_at           TIMESTAMPTZ NOT NULL DEFAULT now();
COMMENT ON COLUMN app_user.token_version IS 'Tăng lên khi đổi mật khẩu / khoá tài khoản / đổi vai trò -> mọi token cũ hết hiệu lực';

-- Một học viên tối đa một tài khoản; email đăng nhập không trùng
CREATE UNIQUE INDEX IF NOT EXISTS app_user_hoc_vien_uidx ON app_user (hoc_vien_id) WHERE hoc_vien_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS app_user_email_uidx ON app_user (lower(email)) WHERE email IS NOT NULL;

CREATE TABLE IF NOT EXISTS password_reset (
    id          SERIAL PRIMARY KEY,
    username    TEXT NOT NULL REFERENCES app_user(username) ON DELETE CASCADE,
    token_hash  TEXT UNIQUE NOT NULL,
    muc_dich    TEXT NOT NULL DEFAULT 'dat_lai' CHECK (muc_dich IN ('dat_lai', 'kich_hoat')),
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE password_reset IS 'Link đặt lại / kích hoạt mật khẩu. Chỉ lưu SHA-256 của token, không lưu token';

ALTER TABLE khoa_hoc ADD COLUMN IF NOT EXISTS dang_mo_ban BOOLEAN NOT NULL DEFAULT true;
COMMENT ON COLUMN khoa_hoc.dang_mo_ban IS 'false = ngừng bán: không mở lớp mới, lớp cũ vẫn học tiếp';
