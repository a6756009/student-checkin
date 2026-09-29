[app]

# 基本信息
title = 学生签到
package.name = studentcheckin
package.domain = org.local.source

# 入口
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttc,ttf,xml
version = 1.0

# 依赖
requirements = python3 ==3.11.16,kivy,openpyxl

# 启动界面
presplash.color = #2E7D32

# 全屏
fullscreen = 0

# 横竖屏
orientation = portrait

# 权限（网络 + 写存储）
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# 目标架构（小米/OPPO 都是 arm64）
android.archs = arm64-v8a, armeabi-v7a

# 允许存储外部文件（导出 Excel 需要）
android.allow_backup = True

# 把字体文件打包进去
android.add_files = fonts/msyh.ttc

# 应用主题
android.theme = @android:style/Theme.DeviceDefault.Light.NoActionBar

# ===========
[buildozer]

log_level = 2
warn_on_root = 1
