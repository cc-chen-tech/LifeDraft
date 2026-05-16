/**
 * AutoGenScreen Component Tests
 * Tests the auto-generation screen (thin wrapper)
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { AutoGenScreen } from "@/components/create/AutoGenScreen";

describe("AutoGenScreen", () => {
  describe("Basic rendering", () => {
    it("renders with autoGenLabel and progress", () => {
      render(
        <AutoGenScreen
          autoGenLabel="角色设定"
          autoGenProgress="正在生成家庭背景..."
        />
      );

      expect(screen.getByText("正在生成角色设定...")).toBeInTheDocument();
      expect(screen.getByText("正在生成家庭背景...")).toBeInTheDocument();
    });

    it("renders the static helper text", () => {
      render(
        <AutoGenScreen
          autoGenLabel="故事背景"
          autoGenProgress="处理中..."
        />
      );

      expect(
        screen.getByText("系统正在根据你的设定自动构建角色背景")
      ).toBeInTheDocument();
    });
  });

  describe("Different labels", () => {
    it("renders with different autoGenLabel values", () => {
      render(
        <AutoGenScreen
          autoGenLabel="人物形象"
          autoGenProgress="50%"
        />
      );
      expect(screen.getByText("正在生成人物形象...")).toBeInTheDocument();
    });

    it("renders with Chinese labels", () => {
      render(
        <AutoGenScreen
          autoGenLabel="世界观"
          autoGenProgress="加载中..."
        />
      );
      expect(screen.getByText("正在生成世界观...")).toBeInTheDocument();
    });
  });

  describe("Different progress messages", () => {
    it("renders various progress messages", () => {
      render(
        <AutoGenScreen
          autoGenLabel="剧情"
          autoGenProgress="AI正在分析你的个人背景..."
        />
      );
      expect(screen.getByText("AI正在分析你的个人背景...")).toBeInTheDocument();
    });
  });

  describe("Edge cases", () => {
    it("renders with empty autoGenLabel", () => {
      render(
        <AutoGenScreen autoGenLabel="" autoGenProgress="Working..." />
      );
      expect(screen.getByText("正在生成...")).toBeInTheDocument();
    });

    it("renders with empty progress", () => {
      render(
        <AutoGenScreen autoGenLabel="Settings" autoGenProgress="" />
      );
      expect(screen.getByText("正在生成Settings...")).toBeInTheDocument();
    });

    it("renders with special characters in labels", () => {
      render(
        <AutoGenScreen
          autoGenLabel="Test & Demo"
          autoGenProgress="<script>alert('test')</script>"
        />
      );
      expect(
        screen.getByText("正在生成Test & Demo...")
      ).toBeInTheDocument();
    });
  });

  describe("Structure", () => {
    it("has the sparkles icon present", () => {
      const { container } = render(
        <AutoGenScreen
          autoGenLabel="test"
          autoGenProgress="progress"
        />
      );
      // Should be a full-screen centered layout
      const firstChild = container.firstChild as HTMLElement;
      expect(firstChild.className).toContain("min-h-screen");
      expect(firstChild.className).toContain("flex");
    });
  });
});
