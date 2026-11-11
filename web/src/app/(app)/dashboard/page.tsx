"use client";

import Link from "next/link";
import useSWR from "swr";
import { BarChart } from "@/components/bar-chart";
import { Badge, Card, CardHeader, ErrorBox, PageHeader, Spinner, Stat, Table, td, th } from "@/components/ui";
import { fmtDate, num, pct, vnd } from "@/lib/format";

type Dash = {
  ngay: string;
  doanh_thu_thang: number;
  doanh_thu_cung_ky_thang_truoc: number;
  doanh_thu_theo_thang: { thang: string; doanh_thu: number }[];
  cong_no: { qua_han: number; hv_qua_han: number; tong_con_no: number };
  hoc_vien_dang_hoc: number;
  tuyen_sinh: { moi_30_ngay: number; ghi_danh: number; cham_lien_he: number };
  lop_sap_khai_giang: {
    id: number;
    ma_lop: string;
    khoa_hoc: string;
    ngay_khai_giang: string;
    si_so: number;
    si_so_toi_da: number;
    si_so_toi_thieu: number;
  }[];
  chuyen_can_4_tuan: number | null;
  agent: { cho_duyet: number; tu_dong_7_ngay: number; duyet_7_ngay: number };
};

export default function DashboardPage() {
  const { data: d, error, mutate } = useSWR<Dash>("/dashboard");
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!d) return <Spinner />;
  const change = d.doanh_thu_cung_ky_thang_truoc ? d.doanh_thu_thang / d.doanh_thu_cung_ky_thang_truoc - 1 : null;
  const conv = d.tuyen_sinh.moi_30_ngay ? d.tuyen_sinh.ghi_danh / d.tuyen_sinh.moi_30_ngay : null;

  return (
    <>
      <PageHeader title="Tổng quan" description={`Số liệu đến ngày ${fmtDate(d.ngay)}. Tính từ cùng một nguồn với agent phân tích.`} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Doanh thu tháng này"
          value={vnd(d.doanh_thu_thang)}
          hint={change == null ? undefined : `${change >= 0 ? "Tăng" : "Giảm"} ${pct(Math.abs(change))} so với cùng kỳ tháng trước`}
        />
        <Stat
          label="Nợ quá hạn"
          value={vnd(d.cong_no.qua_han)}
          tone={d.cong_no.qua_han ? "danger" : undefined}
          hint={`${num(d.cong_no.hv_qua_han)} học viên · tổng còn phải thu ${vnd(d.cong_no.tong_con_no)}`}
        />
        <Stat
          label="Học viên đang học"
          value={num(d.hoc_vien_dang_hoc)}
          hint={d.chuyen_can_4_tuan == null ? undefined : `Chuyên cần 4 tuần qua ${pct(d.chuyen_can_4_tuan)}`}
        />
        <Stat
          label="Khách mới 30 ngày"
          value={num(d.tuyen_sinh.moi_30_ngay)}
          hint={`${conv == null ? "–" : pct(conv)} đã ghi danh · ${d.tuyen_sinh.cham_lien_he} khách quá 3 ngày chưa liên hệ`}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader title="Doanh thu theo tháng" description="Tiền đã thu, đã trừ hoàn phí" />
          <div className="px-4 pb-4">
            <BarChart
              label="Doanh thu theo tháng"
              format={vnd}
              data={d.doanh_thu_theo_thang.map((r) => ({ key: r.thang, label: `T${Number(r.thang.slice(5))}`, value: r.doanh_thu }))}
            />
          </div>
        </Card>
        <Card>
          <CardHeader
            title="Agent tuần này"
            action={
              <Link href="/inbox" className="text-[0.8125rem] font-medium text-accent-fg hover:underline">
                Mở hộp duyệt
              </Link>
            }
          />
          <dl className="grid grid-cols-1 gap-4 px-4 pb-4">
            {[
              ["Đang chờ bạn duyệt", d.agent.cho_duyet, "Đề xuất L1 cần người có quyền quyết định"],
              ["Tự thực hiện trong hạn mức", d.agent.tu_dong_7_ngay, "Việc L2, ví dụ nhắc học phí lần đầu"],
              ["Được duyệt và thực hiện", d.agent.duyet_7_ngay, "Trong 7 ngày qua"],
            ].map(([k, v, h]) => (
              <div key={String(k)}>
                <dt className="text-fg-secondary">{k}</dt>
                <dd className="num text-xl font-semibold">{v}</dd>
                <dd className="text-xs text-fg-tertiary">{h}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader title="Lớp khai giảng trong 30 ngày" description="Lớp chưa đạt sĩ số tối thiểu sẽ được agent giáo vụ đề xuất gộp hoặc huỷ khi còn 7 ngày." />
        <Table label="Lớp sắp khai giảng">
          <thead>
            <tr>
              <th className={th}>Lớp</th>
              <th className={th}>Khai giảng</th>
              <th className={`${th} text-end`}>Sĩ số</th>
              <th className={th}>Tình trạng</th>
            </tr>
          </thead>
          <tbody>
            {d.lop_sap_khai_giang.map((c) => (
              <tr key={c.id} className="hover:bg-surface-hover">
                <td className={td}>
                  <Link href={`/classes/${c.id}`} className="font-medium hover:underline">
                    {c.ma_lop}
                  </Link>
                  <p className="text-fg-tertiary">{c.khoa_hoc}</p>
                </td>
                <td className={`${td} num`}>{fmtDate(c.ngay_khai_giang)}</td>
                <td className={`${td} num text-end`}>
                  {c.si_so}/{c.si_so_toi_da}
                </td>
                <td className={td}>
                  {c.si_so < c.si_so_toi_thieu ? (
                    <Badge tone="warning">Thiếu {c.si_so_toi_thieu - c.si_so} để mở lớp</Badge>
                  ) : (
                    <Badge tone="success">Đủ sĩ số</Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
    </>
  );
}
