# 全栈数据分析平台

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-latest-green)
![Deploy](https://img.shields.io/badge/Render-online-brightgreen)

在线地址：https://data-platform-vp73.onrender.com

## 功能模块

| 模块 | 数据量 | 内容 |
|------|------|------|
| 🍽️ 北京餐饮分析 | 44,512条 | 菜系价格排名、区域消费对比、价格分布 |
| 🎮 游戏评论分析 | 2,531条 | 情感分布、平台评分对比、两极分化 |
| 📈 用户留存分析 | 11,201人 | 留存曲线、队列分析、流失诊断 |
| 🏦 贷款违约预测 | 5,000条 | 随机森林 AUC 0.945、特征重要性 |
| 🤖 AI Agent 问答 | 不限 | 自然语言提问 → Agent 决策 → 返回图表表格 |

## 技术栈

`Python` `FastAPI` `Pandas` `Matplotlib` `Scikit-learn` `DeepSeek API` `Render`

## 本地运行

```bash
pip install -r requirements.txt
set DEEPSEEK_KEY=sk-xxx
python app.py
```

访问 http://127.0.0.1:8000
