import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { api } from "@/lib/api";
import { useUserStore } from "@/stores/useUserStore";
import PlazaPage from "@/app/plaza/page";
import PublicStoryPage from "@/app/plaza/[publicId]/page";
import ManagePlazaPage from "@/app/plaza/manage/page";

jest.mock("next/navigation", () => ({
  useParams: () => ({ publicId: "public-1" }),
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/plaza",
}));

jest.mock("@/lib/api", () => ({
  api: {
    auth: { me: jest.fn() },
    plaza: {
      list: jest.fn(),
      get: jest.fn(),
      mine: jest.fn(),
      setPublication: jest.fn(),
    },
  },
}));

const plaza = api.plaza as jest.Mocked<typeof api.plaza>;

beforeEach(() => {
  jest.clearAllMocks();
  useUserStore.setState({ isAuthenticated: true, user: {
    user_id: 1, public_id: "author01", display_name: "作者", private_id: "secret",
  } });
});

it("lets a visitor browse a story without an account prompt", async () => {
  useUserStore.setState({ isAuthenticated: false, user: null });
  plaza.list.mockResolvedValue({ items: [{
    public_id: "public-1", title: "林晚", author_name: "作者", chapter_count: 2,
    excerpt: "第一天的故事", updated_at: "2026-09-01T00:00:00Z",
  }], has_more: false, next_offset: 1 });
  render(<PlazaPage />);
  expect(await screen.findByRole("link", { name: /林晚/ })).toHaveAttribute("href", "/plaza/public-1");
  expect(screen.queryByText(/请先登录/)).not.toBeInTheDocument();
});

it("reads chapters from a direct public link", async () => {
  useUserStore.setState({ isAuthenticated: false, user: null });
  plaza.get.mockResolvedValue({
    public_id: "public-1", title: "林晚", author_name: "作者", chapter_count: 2,
    excerpt: "第一天", updated_at: null,
    chapters: [
      { number: 1, date: "2026-09-01", text: "第一天" },
      { number: 2, date: "2026-09-02", text: "第二天" },
    ],
  });
  render(<PublicStoryPage />);
  expect(await screen.findByText("第一天")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "下一章" }));
  expect(screen.getByText("第二天")).toBeInTheDocument();
});

it("uses one switch for the whole story and hides its link when off", async () => {
  plaza.mine.mockResolvedValue([{ game_id: 7, title: "林晚", chapter_count: 2,
    can_publish: true, enabled: true, public_id: "public-1", updated_at: null }]);
  plaza.setPublication.mockResolvedValue({ game_id: 7, title: "林晚", chapter_count: 2,
    can_publish: true, enabled: false, public_id: "public-1", updated_at: null });
  render(<ManagePlazaPage />);
  const toggle = await screen.findByRole("switch", { name: "公开林晚" });
  expect(toggle).toHaveAttribute("aria-checked", "true");
  expect(screen.getByRole("link", { name: "查看公开故事" })).toBeInTheDocument();
  fireEvent.click(toggle);
  await waitFor(() => expect(plaza.setPublication).toHaveBeenCalledWith(7, false));
  expect(toggle).toHaveAttribute("aria-checked", "false");
  expect(screen.queryByRole("link", { name: "查看公开故事" })).not.toBeInTheDocument();
});

it("explains that authors must log in without blocking anonymous reading", async () => {
  useUserStore.setState({ isAuthenticated: false, user: null });
  (api.auth.me as jest.Mock).mockRejectedValue({ status: 401 });
  render(<ManagePlazaPage />);
  expect(await screen.findByText("登录后管理分享")).toBeInTheDocument();
  expect(screen.getByText("阅读广场故事无需登录。要公开或关闭自己的故事，请先登录。")).toBeInTheDocument();
  expect(plaza.mine).not.toHaveBeenCalled();
});
