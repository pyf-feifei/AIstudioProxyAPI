# 认证文件目录说明

## 目录结构

项目使用两个目录来管理认证文件：

```
auth_profiles/
├── saved/     # 认证文件存储库（所有认证文件的保存位置）
└── active/    # 激活的认证文件（单实例模式使用）
```

## 目录用途

### `auth_profiles/saved/` - 存储库

**用途**：所有认证文件的**存储库**和**备份位置**

**特点**：
- ✅ 用于**多实例负载均衡模式**的主要来源
- ✅ 用于**错误恢复**时的认证文件切换
- ✅ 通过配置 API 上传的认证文件会保存到这里
- ✅ 可以存储多个账号的认证文件

**使用场景**：
- 多实例模式：从此目录读取所有可用的认证文件
- 错误恢复：`AuthManager` 从此目录选择下一个认证文件
- 配置管理：通过 Web UI 上传的认证文件保存到此目录

### `auth_profiles/active/` - 激活目录

**用途**：**单实例模式**的当前激活认证文件

**特点**：
- ✅ 用于**单实例模式**（默认模式）
- ✅ 启动时自动选择此目录中的第一个 `.json` 文件
- ✅ 通常只包含**一个**认证文件
- ✅ 多实例模式也会读取此目录（兼容性）

**使用场景**：
- 单实例模式：启动时从此目录读取认证文件
- 快速切换：将认证文件移动到此目录即可激活

## 工作流程

### 单实例模式（默认）

```
1. 启动时检查 auth_profiles/active/ 目录
2. 使用第一个找到的 .json 文件
3. 如果 active/ 为空，检查 saved/ 目录
```

### 多实例模式

```
1. 启动时检查 ENABLE_MULTI_INSTANCE=true
2. 从 saved/ 目录读取所有认证文件（主要来源）
3. 也从 active/ 目录读取（兼容性，去重）
4. 为每个认证文件创建浏览器实例
5. 使用负载均衡策略分配请求
```

### 错误恢复

```
1. 当前认证文件失败（配额耗尽等）
2. AuthManager 从 saved/ 目录选择下一个可用文件
3. 切换到新的认证文件继续处理请求
```

## 最佳实践

### 推荐做法

1. **开发/调试阶段**：
   - 使用 `active/` 目录快速切换认证文件
   - 将认证文件复制到 `active/` 目录即可激活

2. **生产环境（多实例）**：
   - 将所有认证文件放在 `saved/` 目录
   - 启用 `ENABLE_MULTI_INSTANCE=true`
   - 通过配置 API 或 Web UI 管理认证文件

3. **文件管理**：
   - `saved/` = 所有认证文件的存储库
   - `active/` = 当前激活的文件（单实例模式）
   - 可以通过配置页面在两者之间移动文件

## 代码中的使用

### 单实例模式

```python
# launcher/runner.py
# 启动时从 active/ 目录选择认证文件
active_json_files = sorted([f for f in os.listdir(ACTIVE_AUTH_DIR) if f.endswith(".json")])
self.effective_active_auth_json_path = os.path.join(ACTIVE_AUTH_DIR, active_json_files[0])
```

### 多实例模式

```python
# api_utils/multi_instance_init.py
# 从 saved/ 和 active/ 目录读取认证文件
for auth_dir in [SAVED_AUTH_DIR, ACTIVE_AUTH_DIR]:
    pattern = os.path.join(auth_dir, "*.json")
    files = glob.glob(pattern)
    auth_files.extend(files)
```

### 错误恢复

```python
# api_utils/auth_manager.py
# 从 saved/ 目录选择下一个认证文件
async def get_available_profiles(self):
    pattern = os.path.join(SAVED_AUTH_DIR, "*.json")
    profiles = await loop.run_in_executor(None, glob.glob, pattern)
    return sorted(profiles)
```

## 总结

| 目录 | 用途 | 单实例模式 | 多实例模式 | 错误恢复 |
|------|------|-----------|-----------|---------|
| `saved/` | 存储库 | 备用 | ✅ 主要来源 | ✅ 使用 |
| `active/` | 激活文件 | ✅ 使用 | 兼容读取 | - |

**关键点**：
- `saved/` = 所有认证文件的**存储库**
- `active/` = **单实例模式**的激活文件
- 多实例模式主要使用 `saved/` 目录
- 两个目录都会被读取，避免重复




