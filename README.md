# Writing Ideas

博客选题推荐页面，由 Tom-Blogs-Manager 自动更新。

## 工作原理

1. AI-Informer 每天收集 AI 领域资讯并产出日报
2. Tom-Blogs-Manager 运行 `scorer.py` 对日报内容进行五维评分
3. 评分结果生成为 `data/ideas.json`，推送到本 repo
4. GitHub Pages 部署为静态页面，通过 `index.html` 展示

## 评分维度

| 维度 | 说明 |
|------|------|
| 受众覆盖度 | 能触达多少类目标读者（技术同行/业务决策者/合作方） |
| 传播潜力 | 搜索引擎和社交媒体的传播性 |
| 作者独特性 | Tom 能否基于自身经验提供独特视角 |
| 时效性 | 发布窗口期 |
| 系列化潜力 | 能否展开为系列内容 |

总分 25 分：20+ 强烈推荐，15-19 值得考虑，<15 优先级低。

## 本地使用

```bash
# 生成评分数据
python scorer.py

# 数据输出到 data/ideas.json
```
