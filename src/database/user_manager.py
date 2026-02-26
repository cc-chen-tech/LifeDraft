"""用户管理器 - 处理用户创建、登录、好友等功能"""
import secrets
import string
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from src.database.models import User, Friendship, Game, SessionLocal

logger = logging.getLogger(__name__)


def generate_private_id() -> str:
    """
    生成32位私有ID (用于登录)
    格式: 8组4位字符，用-分隔，如: ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456
    """
    alphabet = string.ascii_uppercase + string.digits
    parts = [''.join(secrets.choice(alphabet) for _ in range(4)) for _ in range(8)]
    return '-'.join(parts)


def generate_public_id() -> str:
    """
    生成8位公有ID (用于分享/加好友)
    格式: 8位大写字母和数字，如: AB12CD34
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))


class UserManager:
    """用户管理类"""
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        初始化用户管理器
        
        Args:
            db_session: 数据库会话，如果不提供则自动创建
        """
        self._db = db_session
        self._owns_session = db_session is None
    
    @property
    def db(self) -> Session:
        """获取数据库会话"""
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def close(self):
        """关闭数据库会话（如果是自己创建的）"""
        if self._owns_session and self._db is not None:
            self._db.close()
            self._db = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # ==================== 用户创建与登录 ====================
    
    def create_user(self, display_name: Optional[str] = None) -> Tuple[User, str]:
        """
        创建新用户
        
        Args:
            display_name: 可选的显示名称
        
        Returns:
            Tuple[User, str]: (用户对象, 私有ID明文)
            注意：私有ID只在创建时返回一次，用户需要保存好！
        """
        # 生成唯一ID
        private_id = generate_private_id()
        public_id = generate_public_id()
        
        # 确保ID唯一
        while self.db.query(User).filter(User.private_id == private_id).first():
            private_id = generate_private_id()
        while self.db.query(User).filter(User.public_id == public_id).first():
            public_id = generate_public_id()
        
        # 创建用户
        user = User(
            private_id=private_id,
            public_id=public_id,
            display_name=display_name,
            last_login=datetime.utcnow()
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        logger.info(f"Created new user: public_id={public_id}")
        return user, private_id
    
    def login_by_private_id(self, private_id: str) -> Optional[User]:
        """
        通过私有ID登录
        
        Args:
            private_id: 用户的私有ID
        
        Returns:
            User对象，如果登录失败则返回None
        """
        # 标准化私有ID格式（移除空格，转大写）
        private_id = private_id.strip().upper().replace(' ', '-')
        
        user = self.db.query(User).filter(User.private_id == private_id).first()
        
        if user:
            user.last_login = datetime.utcnow()
            self.db.commit()
            logger.info(f"User logged in: public_id={user.public_id}")
        else:
            logger.warning(f"Login failed: private_id not found")
        
        return user
    
    def get_user_by_public_id(self, public_id: str) -> Optional[User]:
        """
        通过公有ID获取用户（用于添加好友）
        
        Args:
            public_id: 用户的公有ID
        
        Returns:
            User对象，如果未找到则返回None
        """
        public_id = public_id.strip().upper()
        return self.db.query(User).filter(User.public_id == public_id).first()
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """通过用户ID获取用户"""
        return self.db.query(User).filter(User.user_id == user_id).first()
    
    def update_display_name(self, user_id: int, display_name: str) -> bool:
        """
        更新用户显示名称
        
        Args:
            user_id: 用户ID
            display_name: 新的显示名称
        
        Returns:
            是否更新成功
        """
        user = self.get_user_by_id(user_id)
        if user:
            user.display_name = display_name[:50]  # 限制长度
            self.db.commit()
            return True
        return False
    
    # ==================== 好友功能 ====================
    
    def send_friend_request(self, user_id: int, friend_public_id: str) -> Dict[str, Any]:
        """
        发送好友请求
        
        Args:
            user_id: 发送者的用户ID
            friend_public_id: 接收者的公有ID
        
        Returns:
            Dict with 'success', 'message', 'friendship' keys
        """
        friend = self.get_user_by_public_id(friend_public_id)
        
        if not friend:
            return {"success": False, "message": "用户不存在", "friendship": None}
        
        if friend.user_id == user_id:
            return {"success": False, "message": "不能添加自己为好友", "friendship": None}
        
        # 检查是否已有好友关系
        existing = self.db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == user_id, Friendship.friend_id == friend.user_id),
                and_(Friendship.user_id == friend.user_id, Friendship.friend_id == user_id)
            )
        ).first()
        
        if existing:
            if existing.status == "accepted":
                return {"success": False, "message": "你们已经是好友了", "friendship": existing}
            elif existing.status == "pending":
                if existing.user_id == user_id:
                    return {"success": False, "message": "已发送过好友请求，等待对方接受", "friendship": existing}
                else:
                    # 对方先发的请求，自动接受
                    existing.status = "accepted"
                    existing.updated_at = datetime.utcnow()
                    self.db.commit()
                    return {"success": True, "message": "已接受对方的好友请求", "friendship": existing}
            elif existing.status == "rejected":
                # 重新发送请求
                existing.status = "pending"
                existing.user_id = user_id
                existing.friend_id = friend.user_id
                existing.updated_at = datetime.utcnow()
                self.db.commit()
                return {"success": True, "message": "好友请求已发送", "friendship": existing}
        
        # 创建新的好友请求
        friendship = Friendship(
            user_id=user_id,
            friend_id=friend.user_id,
            status="pending"
        )
        self.db.add(friendship)
        self.db.commit()
        self.db.refresh(friendship)
        
        logger.info(f"Friend request sent: {user_id} -> {friend.user_id}")
        return {"success": True, "message": "好友请求已发送", "friendship": friendship}
    
    def respond_to_friend_request(self, user_id: int, friendship_id: int, accept: bool) -> Dict[str, Any]:
        """
        响应好友请求
        
        Args:
            user_id: 接收者的用户ID
            friendship_id: 好友请求ID
            accept: 是否接受
        
        Returns:
            Dict with 'success', 'message' keys
        """
        friendship = self.db.query(Friendship).filter(
            Friendship.id == friendship_id,
            Friendship.friend_id == user_id,
            Friendship.status == "pending"
        ).first()
        
        if not friendship:
            return {"success": False, "message": "好友请求不存在或已处理"}
        
        friendship.status = "accepted" if accept else "rejected"
        friendship.updated_at = datetime.utcnow()
        self.db.commit()
        
        action = "接受" if accept else "拒绝"
        logger.info(f"Friend request {action}: {friendship.user_id} <-> {user_id}")
        return {"success": True, "message": f"已{action}好友请求"}
    
    def get_friends(self, user_id: int) -> List[User]:
        """
        获取用户的好友列表
        
        Args:
            user_id: 用户ID
        
        Returns:
            好友User对象列表
        """
        # 查找已接受的好友关系
        friendships = self.db.query(Friendship).filter(
            or_(
                Friendship.user_id == user_id,
                Friendship.friend_id == user_id
            ),
            Friendship.status == "accepted"
        ).all()
        
        friends = []
        for f in friendships:
            friend_id = f.friend_id if f.user_id == user_id else f.user_id
            friend = self.get_user_by_id(friend_id)
            if friend:
                friends.append(friend)
        
        return friends
    
    def get_pending_friend_requests(self, user_id: int) -> List[Dict[str, Any]]:
        """
        获取待处理的好友请求
        
        Args:
            user_id: 用户ID
        
        Returns:
            待处理的好友请求列表
        """
        requests = self.db.query(Friendship).filter(
            Friendship.friend_id == user_id,
            Friendship.status == "pending"
        ).all()
        
        result = []
        for req in requests:
            sender = self.get_user_by_id(req.user_id)
            if sender:
                result.append({
                    "friendship_id": req.id,
                    "sender_public_id": sender.public_id,
                    "sender_display_name": sender.display_name or sender.public_id,
                    "created_at": req.created_at
                })
        
        return result
    
    def remove_friend(self, user_id: int, friend_user_id: int) -> bool:
        """
        删除好友
        
        Args:
            user_id: 当前用户ID
            friend_user_id: 要删除的好友ID
        
        Returns:
            是否删除成功
        """
        friendship = self.db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == user_id, Friendship.friend_id == friend_user_id),
                and_(Friendship.user_id == friend_user_id, Friendship.friend_id == user_id)
            ),
            Friendship.status == "accepted"
        ).first()
        
        if friendship:
            self.db.delete(friendship)
            self.db.commit()
            logger.info(f"Friendship removed: {user_id} <-> {friend_user_id}")
            return True
        return False
    
    # ==================== 游戏相关 ====================
    
    def get_user_games(self, user_id: int) -> List[Game]:
        """
        获取用户的所有游戏
        
        Args:
            user_id: 用户ID
        
        Returns:
            Game对象列表
        """
        return self.db.query(Game).filter(Game.user_id == user_id).order_by(Game.created_at.desc()).all()
    
    def get_friend_public_games(self, user_id: int, friend_user_id: int) -> List[Game]:
        """
        获取好友的公开游戏
        
        Args:
            user_id: 当前用户ID
            friend_user_id: 好友用户ID
        
        Returns:
            好友的公开Game对象列表
        """
        # 验证是否为好友
        is_friend = self.db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == user_id, Friendship.friend_id == friend_user_id),
                and_(Friendship.user_id == friend_user_id, Friendship.friend_id == user_id)
            ),
            Friendship.status == "accepted"
        ).first()
        
        if not is_friend:
            return []
        
        return self.db.query(Game).filter(
            Game.user_id == friend_user_id,
            Game.is_public == True
        ).order_by(Game.created_at.desc()).all()
    
    def set_game_public(self, game_id: int, user_id: int, is_public: bool) -> bool:
        """
        设置游戏是否公开
        
        Args:
            game_id: 游戏ID
            user_id: 用户ID（验证所有权）
            is_public: 是否公开
        
        Returns:
            是否设置成功
        """
        game = self.db.query(Game).filter(
            Game.game_id == game_id,
            Game.user_id == user_id
        ).first()
        
        if game:
            game.is_public = is_public
            self.db.commit()
            return True
        return False
