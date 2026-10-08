# 📐 Typography System - tw-canslim-web

统一的字体规范，参考 squeeze-tw-screener 的设计系统。

## 字体堆栈

```css
body { font-family: 'Noto Sans TC', sans-serif; font-size: 15px; }
.font-mono { font-family: 'JetBrains Mono', monospace; }
```

## 尺度系统（12px ~ 28px）

| 用途 | 大小 | 权重 | 用例 |
|------|------|------|------|
| **标签/副本** | 12px | 400 | 表格列头、徽章标签、辅助文本 |
| **小标题** | 13px | 500 | 筛选芯片、评分徽章 |
| **正文** | 14px | 400 | 表格数据、卡片内容 |
| **输入框** | 15px | 400 | 搜索框、文本输入 |
| **副标题** | 14px | 400 | 描述文本 |
| **小标题** | 22px | 900 | 详情面板标题 |
| **h1 标题** | 28px | 900 | 页面主标题 |
| **Stat值** | 24px | 900 | 数据卡片大数字 |

## 关键类名规范

### 标题
- `.h1` → 28px, weight:900
- `.h2` → 22px, weight:900
- `.h3` → 18px, weight:700
- `.h4` → 16px, weight:700

### 数据展示
- `.stat-value` → 24px, weight:900
- `.stat-label` → 12px, color:#666
- `.score-badge` → 13px, weight:700
- `.sqz-on`, `.sqz-off`, `.sqz-fired` → 14px, weight:700

### 表格
- `th` → 12px, weight:400, color:#666
- `td` → 14px, weight:400
- 最小行高: 10px padding

### 交互
- `.btn` → 14px, weight:700
- `.btn-sm` → 12px, weight:700
- `.filter-chip` → 13px, weight:500
- `input` → 15px（等于body基础）

## 色彩标准

```css
/* 文本 */
#1a1a2e - 主文本
#666666 - 辅助文本（标签）
#999999 - 占位符

/* 背景 */
#f0f2f5 - 页面背景
#ffffff - 卡片背景
#f8f9fa - Stat卡片背景

/* 状态 */
#e94560 - 压缩/看空（红）
#10b981 - 正常/看多（绿）
#f59e0b - 释放（黄）
#1a73e8 - 主操作（蓝）
```

## 响应式调整（≤640px）

```css
@media(max-width:640px) {
  table { font-size:13px; }
  th, td { padding:8px 4px; }
  .stat-grid { grid-template-columns:repeat(2,1fr); }
  h1 { font-size:24px; }
}
```

## 间距标准

- **padding**: 24px（卡片）, 16px（标准）, 12px（紧凑）
- **gap**: 12px（卡片间）, 8px（筛选）, 6px（按钮内）
- **margin-bottom**: 24px（段落）, 16px（元素）

## 禁止的做法

❌ 混用 rem / em / px  
❌ 字体大小跨度超过 3 倍（12px → 56px）  
❌ 行高小于 1.2  
❌ 字重只用 400 / 700 之外的值  

## 检查清单

- [ ] 所有 h1 都是 28px, weight:900
- [ ] 所有表格 th 都是 12px
- [ ] 所有表格 td 都是 14px
- [ ] Stat 大值都是 24px, weight:900
- [ ] Stat 标签都是 12px, color:#666
- [ ] 最小字号不低于 12px
- [ ] 颜色只用规范中的 6 种
