# Cookie 导出详细教程

部分视频平台（抖音、TikTok、小红书等）有反爬机制，需要提供浏览器 Cookie 才能下载视频。
本教程以**抖音**为例，其他平台操作完全相同。

---

## 第一步：安装 Chrome 扩展

1. 打开 Chrome 浏览器
2. 访问 Chrome 扩展商店：
   - 搜索 **"Get cookies.txt LOCALLY"**
   - 或直接打开：https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
3. 点击 **"添加到 Chrome"** → 确认安装
4. 安装完成后，浏览器右上角会出现一个 🍪 Cookie 图标

> **为什么选这个扩展？**
> - 完全本地运行，不上传任何数据
> - 导出格式就是 yt-dlp 需要的 Netscape 格式
> - 免费、开源、无广告

---

## 第二步：登录抖音网页版

1. 在 Chrome 中打开 **https://www.douyin.com**
2. 点击右上角 **"登录"**
3. 用手机抖音 App **扫码登录**（推荐）
   - 也可以用手机号+验证码登录
4. 登录成功后，确认页面右上角显示你的头像/昵称

> **不登录行不行？**
> - 不行。抖音要求至少有一个有效的访客 Cookie（"Fresh cookies"）
> - 登录后的 Cookie 最稳定，有效期更长

---

## 第三步：导出 Cookie 文件

1. **确保当前页面在 www.douyin.com**（任意抖音页面都行）
2. 点击浏览器右上角的 🍪 **Cookie 扩展图标**
3. 在弹出的面板中：
   - 确认域名显示的是 `www.douyin.com` 或 `.douyin.com`
   - 点击 **"Export"** 或 **"导出"** 按钮
4. 浏览器会自动下载一个文件，通常叫 `www.douyin.com_cookies.txt` 或 `cookies.txt`
5. 在 **Downloads（下载）** 文件夹找到这个文件

> **验证文件格式正确：** 用文本编辑器打开，第一行应该是：
> ```
> # Netscape HTTP Cookie File
> ```
> 后面是一行行的 Cookie 数据，类似：
> ```
> .douyin.com	TRUE	/	FALSE	1700000000	ttwid	xxxxxxxx
> .douyin.com	TRUE	/	FALSE	1700000000	msToken	yyyyyyyy
> ```

---

## 第四步：放到项目目录

将下载的 Cookie 文件**重命名**并**移动**到项目的 `config/cookies/` 目录：

### 方法 A：命令行（推荐）

```bash
# 假设下载的文件在 ~/Downloads/
mv ~/Downloads/www.douyin.com_cookies.txt \
   ~/Documents/soft/DeepDistill/config/cookies/douyin.txt
```

### 方法 B：Finder 手动操作

1. 打开 Finder → 前往 `~/Downloads/`
2. 找到刚下载的 Cookie 文件
3. 重命名为 `douyin.txt`
4. 移动到 `~/Documents/soft/DeepDistill/config/cookies/` 目录

---

## 第五步：验证（无需重启）

Cookie 文件放好后，**不需要重启 Docker 容器**（config 目录已挂载），直接提交抖音链接即可。

系统会自动：
1. 检测到抖音 URL → 查找 `config/cookies/douyin.txt`
2. 带 Cookie 调用 yt-dlp 下载视频
3. ASR 语音转文字
4. AI 提炼知识点

---

## 其他平台 Cookie

操作完全相同，只需要：
1. 在浏览器中打开对应平台并登录
2. 用同一个扩展导出 Cookie
3. 按下表命名放到 `config/cookies/` 目录

| 平台 | 登录网址 | Cookie 文件名 |
|------|----------|---------------|
| 抖音 | www.douyin.com | `douyin.txt` |
| TikTok | www.tiktok.com | `tiktok.txt` |
| B站 | www.bilibili.com | `bilibili.txt` |
| 小红书 | www.xiaohongshu.com | `xiaohongshu.txt` |
| 快手 | www.kuaishou.com | `kuaishou.txt` |
| 微博 | weibo.com | `weibo.txt` |
| Instagram | www.instagram.com | `instagram.txt` |
| Facebook | www.facebook.com | `facebook.txt` |
| 通用（兜底） | — | `default.txt` |

---

## 常见问题

### Q: Cookie 多久过期？
A: 一般 7-30 天，取决于平台。过期后重新执行第二~四步即可。

### Q: 导出后还是报错？
A: 检查以下几点：
- 文件名是否正确（`douyin.txt`，不是 `douyin.txt.txt`）
- 文件是否在 `config/cookies/` 目录下（不是 `config/` 根目录）
- 文件内容第一行是否为 `# Netscape HTTP Cookie File`
- 导出时是否在抖音页面上（不是在其他网站）

### Q: 会不会泄露我的账号？
A: Cookie 文件仅在本地 Docker 容器内使用，不会上传到任何地方。
   且已在 `.gitignore` 中排除，不会被提交到 Git。

### Q: 不想登录怎么办？
A: 可以不登录，只要在抖音网页上浏览过视频（产生访客 Cookie），
   然后导出即可。但登录后的 Cookie 更稳定。
