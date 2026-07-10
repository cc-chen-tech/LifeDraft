"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useUserStore } from "@/stores/useUserStore";
import { useHydration } from "@/hooks/useHydration";
import {
  ArrowLeft,
  Copy,
  Check,
  UserPlus,
  Loader2,
  Users,
  X,
} from "lucide-react";

export default function ProfilePage() {
  const router = useRouter();
  const {
    user,
    isAuthenticated,
    friends,
    pendingRequests,
    fetchFriends,
    fetchPendingRequests,
    sendFriendRequest,
    respondToRequest,
    removeFriend,
    fetchMe,
  } = useUserStore();

  const [copied, setCopied] = useState(false);
  const [friendCode, setFriendCode] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState("");
  const [authChecked, setAuthChecked] = useState(false);
  const hydrated = useHydration();

  useEffect(() => {
    if (!hydrated) return;

    if (!isAuthenticated) {
      let cancelled = false;
      fetchMe()
        .catch(console.error)
        .finally(() => {
          if (!cancelled) {
            setAuthChecked(true);
          }
        });
      return () => {
        cancelled = true;
      };
    }

    setAuthChecked(true);
    fetchFriends().catch(console.error);
    fetchPendingRequests().catch(console.error);
  }, [hydrated, isAuthenticated, fetchMe, fetchFriends, fetchPendingRequests]);

  useEffect(() => {
    if (!hydrated || !authChecked || isAuthenticated) return;
    router.push("/");
  }, [hydrated, authChecked, isAuthenticated, router]);

  if (!hydrated || !authChecked || !isAuthenticated) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>正在验证登录状态...</span>
        </div>
      </div>
    );
  }

  const handleCopyPublicId = () => {
    if (user?.public_id) {
      import("@/lib/utils").then(({ copyToClipboard }) => {
        copyToClipboard(user.public_id).then((success) => {
          if (success) {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }
        });
      });
    }
  };

  const handleSendRequest = async () => {
    if (!friendCode.trim()) return;
    setIsSending(true);
    setSendError("");
    try {
      await sendFriendRequest(friendCode.trim());
      setFriendCode("");
    } catch (err) {
      setSendError(String((err as Error).message || "发送失败"));
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="min-h-screen bg-background animate-page-enter">
      <header className="sticky top-0 z-40 bg-background/80 backdrop-blur-sm border-b border-border">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            返回
          </Button>
          <h1 className="text-lg font-bold text-foreground ml-3">个人资料</h1>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 space-y-6">
        {/* User info */}
        <Card className="p-4 bg-card border-border">
          <h2 className="font-bold text-foreground text-lg mb-3">
            {user?.display_name || "旅行者"}
          </h2>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">公开ID</span>
              <div className="flex items-center gap-2">
                <code className="text-primary font-mono">{user?.public_id}</code>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-6 w-6"
                  onClick={handleCopyPublicId}
                  aria-label={copied ? "已复制公开 ID" : "复制公开 ID"}
                >
                  {copied ? (
                    <Check className="w-3 h-3 text-success" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                </Button>
              </div>
            </div>
          </div>
        </Card>

        <Separator />

        {/* Add friend */}
        <div>
          <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
            <UserPlus className="w-4 h-4" />
            添加好友
          </h3>
          <div className="flex gap-2">
            <Input
              value={friendCode}
              onChange={(e) => setFriendCode(e.target.value)}
              placeholder="输入好友的公开ID"
              className="flex-1 bg-secondary border-border h-10 font-mono text-sm"
            />
            <Button
              size="sm"
              className="h-10 touch-target"
              disabled={!friendCode.trim() || isSending}
              onClick={handleSendRequest}
            >
              {isSending ? <Loader2 className="w-4 h-4 animate-spin" /> : "发送"}
            </Button>
          </div>
          {sendError && (
            <p className="text-xs text-destructive mt-1">{sendError}</p>
          )}
        </div>

        {/* Pending requests */}
        {pendingRequests.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-foreground mb-3">
              待处理请求 ({pendingRequests.length})
            </h3>
            <div className="space-y-2">
              {pendingRequests.map((req) => (
                <Card
                  key={req.request_id}
                  className="p-3 bg-card border-border flex items-center justify-between"
                >
                  <span className="text-sm text-foreground">
                    {req.from_user.display_name || req.from_user.public_id}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => respondToRequest(req.request_id, true)}
                    >
                      接受
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => respondToRequest(req.request_id, false)}
                    >
                      拒绝
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Friends list */}
        <div>
          <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
            <Users className="w-4 h-4" />
            好友列表 ({friends.length})
          </h3>
          {friends.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              暂无好友
            </p>
          ) : (
            <div className="space-y-2">
              {friends.map((friend) => (
                <Card
                  key={friend.user_id}
                  className="p-3 bg-card border-border flex items-center justify-between"
                >
                  <div>
                    <span className="text-sm text-foreground">
                      {friend.display_name || "旅行者"}
                    </span>
                    <Badge variant="outline" className="ml-2 text-xs">
                      {friend.public_id}
                    </Badge>
                  </div>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                    onClick={() => removeFriend(friend.user_id)}
                    aria-label={`删除好友${friend.display_name || friend.public_id}`}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </Card>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
