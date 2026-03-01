"use client";

import { useEffect } from "react";
import { installGlobalErrorReporter } from "@/lib/remote-log";

/**
 * 安装全局前端错误上报器（仅执行一次）。
 * 放在 RootLayout 中，捕获所有页面的未处理异常并 POST 到后端日志。
 */
export default function ErrorReporter() {
  useEffect(() => {
    installGlobalErrorReporter();
  }, []);
  return null;
}
