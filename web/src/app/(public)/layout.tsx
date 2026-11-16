import { ChatWidget } from "@/components/public/chat-widget";
import { SiteFooter } from "@/components/public/site-footer";
import { SiteHeader } from "@/components/public/site-header";
import { type Center, pub } from "@/lib/public-api";

// Render khi có request (không render lúc build): lúc build trong Docker chưa có API để lấy dữ liệu.
// Dữ liệu vẫn được cache 5 phút nhờ fetch revalidate trong pub().
export const dynamic = "force-dynamic";

export default async function PublicLayout({ children }: { children: React.ReactNode }) {
  const center = await pub<Center>("/public/center").catch(() => null);
  return (
    <>
      <SiteHeader />
      <main id="noi-dung">{children}</main>
      <SiteFooter center={center} />
      <ChatWidget />
    </>
  );
}
