#!/bin/bash
# Story2 数据备份脚本

BACKUP_DIR="/opt/backups/story2"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 备份数据目录
echo "Backing up data directory..."
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" -C /opt/story2 data/

# 备份环境变量（注意：生产环境应加密存储）
echo "Backing up configuration..."
cp /opt/story2/.env "$BACKUP_DIR/env_$DATE.bak"

# 清理旧备份
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "data_*.tar.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "env_*.bak" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_DIR/data_$DATE.tar.gz"
