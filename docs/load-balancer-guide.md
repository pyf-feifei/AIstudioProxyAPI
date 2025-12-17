# 多账号负载均衡功能指南

## 概述

本项目现已支持多账号负载均衡功能，可以配置多个认证文件，并通过负载均衡策略将请求分发到不同的浏览器实例。

## 功能特性

### ✅ 已实现功能

1. **多实例管理**
   - 支持管理多个浏览器实例
   - 每个实例使用独立的认证文件
   - 实例状态监控（就绪/未就绪）
   - 实例启用/禁用控制

2. **负载均衡策略**
   - **轮询 (Round Robin)**: 按顺序轮流分配请求
   - **随机 (Random)**: 随机选择实例
   - **最少连接 (Least Connections)**: 选择当前请求数最少的实例

3. **认证文件管理**
   - 上传认证 JSON 文件
   - 查看认证文件列表
   - 删除认证文件
   - 文件大小和路径显示

4. **配置管理页面**
   - Web UI 配置界面 (`/config`)
   - 实时查看实例状态
   - 动态调整负载均衡策略
   - 实例统计信息

5. **API 端点**
   - `/api/config/auth-files` - 认证文件列表
   - `/api/config/auth-files/upload` - 上传认证文件
   - `/api/config/auth-files/{filename}` - 删除认证文件
   - `/api/config/load-balance` - 负载均衡配置
   - `/api/config/load-balance/strategy` - 设置负载均衡策略
   - `/api/config/instances` - 实例列表
   - `/api/config/instances/{id}/enable` - 启用/禁用实例
   - `/api/config/stats` - 详细统计信息

## 使用方法

### 1. 启用多实例模式

在 `.env` 文件中设置：

```env
ENABLE_MULTI_INSTANCE=true
```

### 2. 准备认证文件

**目录说明**：
- `auth_profiles/saved/` - **所有认证文件的存储库**（推荐用于多实例模式）
- `auth_profiles/active/` - **单实例模式的激活文件**（多实例模式也会读取以兼容）

**推荐做法**：将多个认证 JSON 文件放入 `auth_profiles/saved/` 目录：

```
auth_profiles/
├── saved/          ← 多实例模式主要使用此目录
│   ├── account1.json
│   ├── account2.json
│   └── account3.json
└── active/         ← 单实例模式使用，多实例模式也会读取
    └── 1_save.json (当前激活的文件)
```

**注意**：
- `saved/` 目录是所有认证文件的**存储库**，用于多实例负载均衡
- `active/` 目录是**单实例模式**的激活文件位置
- 多实例模式会同时读取两个目录，避免重复

### 3. 启动服务

```bash
python launch_camoufox.py --headless
```

### 4. 访问配置页面

打开浏览器访问：`http://localhost:2048/config`

### 5. 配置负载均衡

在配置页面中：
1. 选择负载均衡策略（轮询/随机/最少连接）
2. 查看实例状态和统计信息
3. 上传或删除认证文件
4. 启用/禁用特定实例

## API 使用示例

### 获取负载均衡配置

```bash
curl http://localhost:2048/api/config/load-balance
```

### 设置负载均衡策略

```bash
curl -X POST http://localhost:2048/api/config/load-balance/strategy \
  -H "Content-Type: application/json" \
  -d '{"strategy": "round_robin"}'
```

### 上传认证文件

```bash
curl -X POST http://localhost:2048/api/config/auth-files/upload \
  -F "file=@/path/to/auth.json"
```

### 获取实例统计

```bash
curl http://localhost:2048/api/config/stats
```

## 架构说明

### 核心组件

1. **MultiInstanceManager** (`api_utils/instance_manager.py`)
   - 管理浏览器实例集合
   - 实现负载均衡策略
   - 跟踪实例状态和统计

2. **LoadBalancer** (`api_utils/load_balancer.py`)
   - 提供负载均衡接口
   - 请求分发逻辑
   - 统计信息收集

3. **配置 API** (`api_utils/routers/config.py`)
   - RESTful API 端点
   - 认证文件管理
   - 配置更新接口

### 工作流程

```
请求到达
  ↓
LoadBalancer.get_instance()
  ↓
MultiInstanceManager.get_next_instance()
  ↓
根据策略选择实例
  ↓
使用选中的实例处理请求
  ↓
更新实例统计信息
```

## 注意事项

### 当前限制

1. **单浏览器进程**: 当前实现使用同一个 Camoufox 进程，通过不同的认证文件切换。真正的多实例需要启动多个 Camoufox 进程（每个使用不同端口）。

2. **串行处理**: 请求仍然通过队列串行处理，负载均衡主要用于错误恢复和认证文件切换。

3. **认证文件切换**: 在错误恢复时会自动切换到下一个可用的认证文件。

### 未来改进

1. **真正的多进程**: 支持启动多个 Camoufox 进程，实现真正的并发处理
2. **并发请求**: 支持多个请求同时处理（每个使用不同的实例）
3. **健康检查**: 自动检测实例健康状态，移除故障实例
4. **权重配置**: 支持为不同实例设置权重

## 测试

运行测试脚本验证功能：

```bash
python test_load_balancer_standalone.py
```

## 故障排除

### 问题：实例未初始化

**原因**: 多实例模式未启用或认证文件不存在

**解决**: 
1. 检查 `.env` 文件中的 `ENABLE_MULTI_INSTANCE=true`
2. 确保 `auth_profiles/saved/` 或 `auth_profiles/active/` 目录下有认证文件
3. 推荐将认证文件放在 `saved/` 目录（这是认证文件的存储库）

### 问题：负载均衡不工作

**原因**: 只有一个实例或所有实例都被禁用

**解决**:
1. 检查实例列表：`curl http://localhost:2048/api/config/instances`
2. 确保至少有一个实例是启用状态

### 问题：认证文件上传失败

**原因**: 文件格式错误或权限问题

**解决**:
1. 确保文件是有效的 JSON 格式
2. 检查文件权限和目录权限

## 相关文件

- `api_utils/instance_manager.py` - 实例管理器
- `api_utils/load_balancer.py` - 负载均衡器
- `api_utils/routers/config.py` - 配置 API
- `api_utils/multi_instance_init.py` - 多实例初始化
- `api_utils/context_init.py` - 请求上下文初始化（已修改支持负载均衡）
- `static/config.html` - 配置管理页面

