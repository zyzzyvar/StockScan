# PostgreSQL pg_hba.conf 配置修改指引

## 问题描述

远端程序（运行在 IP: `10.7.7.66`）无法连接 PostgreSQL 服务器（`192.168.99.150:5432`）。

错误信息：
```
FATAL: no pg_hba.conf entry for host "10.7.7.66", user "stockscan_user", database "stockscan", no encryption
```

## 操作步骤

### 1. 找到 pg_hba.conf 文件

根据 PostgreSQL 版本，文件通常位于：

- **CentOS/RHEL**: `/var/lib/pgsql/data/pg_hba.conf`
- **Debian/Ubuntu**: `/etc/postgresql/<version>/main/pg_hba.conf` （version 如 12, 13, 14, 15）
- **macOS**: `/Users/postgres/Library/Application Support/Postgres/var-<version>/pg_hba.conf`

确认文件位置：
```bash
find / -name "pg_hba.conf" 2>/dev/null
```

### 2. 编辑 pg_hba.conf

打开文件（例如用 vim 或 nano）：
```bash
sudo vim /var/lib/pgsql/data/pg_hba.conf
```

### 3. 添加以下规则

在文件的适当位置（通常在其他 `host` 规则之后）添加一行：

```conf
host    stockscan    stockscan_user    10.7.7.66/32    trust
```

**说明：**
- `host` — 允许 TCP/IP 连接
- `stockscan` — 数据库名
- `stockscan_user` — 用户名
- `10.7.7.66/32` — 允许的客户端 IP（/32 表示单个 IP）
- `trust` — 认证方式（无需密码；或改为 `md5`/`scram-sha-256` 如果需要加密）

**示例完整规则段（参考）：**
```conf
# IPv4 local connections:
host    all             all             127.0.0.1/32            trust
host    stockscan       stockscan_user  10.7.7.66/32            trust    # 新增规则
```

### 4. 保存文件

确保文件已保存（vim: `:wq`，nano: `Ctrl+O` → `Enter` → `Ctrl+X`）

### 5. 重启 PostgreSQL 服务

选择对应的命令：

**CentOS/RHEL (systemd)：**
```bash
sudo systemctl restart postgresql
```

**CentOS/RHEL (init)：**
```bash
sudo service postgresql restart
```

**Debian/Ubuntu (systemd)：**
```bash
sudo systemctl restart postgresql
```

**Debian/Ubuntu (init)：**
```bash
sudo service postgresql restart
```

**macOS：**
```bash
# 使用 Homebrew
brew services restart postgresql
```

### 6. 验证配置（可选）

在服务器上测试连接：

```bash
# 使用 psql 连接测试
psql -h 192.168.99.150 -p 5432 -U stockscan_user -d stockscan -c "SELECT 1"
```

或者在客户端机器（10.7.7.66）上测试：

```bash
# 从远端程序所在机器测试
psql -h 192.168.99.150 -p 5432 -U stockscan_user -d stockscan -c "SELECT 1"
```

如果返回 `1`，则连接成功。

---

## 常见问题

**Q: 应该用 `trust` 还是其他认证方式？**

A: 
- `trust` — 最简单，无需密码，但要求客户端 IP 准确
- `md5` — 需要密码，较安全（PostgreSQL 10+）
- `scram-sha-256` — 最安全的加密方式（PostgreSQL 10+）

建议用 `trust`；如果需要更安全的方式，改成 `md5` 或 `scram-sha-256` 即可。

**Q: 修改后没有生效？**

A: 确保：
1. 文件已保存
2. PostgreSQL 已完全重启（不是 reload）
3. pg_hba.conf 文件权限正确（通常是 0600）

---

## 完成后

修改完成并验证连接成功后，远端程序就能正常连接到 PostgreSQL 并拉取数据了。

