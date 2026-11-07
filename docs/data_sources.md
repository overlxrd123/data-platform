# 数据来源与展示范围

作者确认餐饮、北京租房、招聘、电影和麦当劳问卷为公开网站下载数据，回忆下载渠道包括和鲸社区、天池；原始链接未保留。
平台记录这一下载背景，不把回忆写成“全部来自和鲸”，也不将其等同于发布者及每行数据的独立核实。

| 模块 | 平台文件 | 来源与边界 |
|---|---|---|
| 北京餐饮 | `bj_food_analysis.xlsx` | 作者提供的公开社区下载样本；0元人均按未采集处理；推荐标签来源未核实 |
| 北京租房 | `data/beijing_rental.csv` | 作者确认公开下载；保留国内租房展示。各区域分布均匀、同房型价格面积相关性弱等为样本特征，不据此断言伪造，也不外推全北京 |
| 招聘 | `data/job_data.csv` | 作者提供公开下载；选样与时间含义未保留，保留岗位噪声及日期集中限制 |
| 国产电影 | `data/movies.xlsx` | 原文件为国产电影数据集.xlsx，120部24字段；本地无原始URL、采集脚本或外链。各片截止日期不同；字段名称不足以证明猫眼/豆瓣官方授权或直接采集 |
| 麦当劳调查 | `data/mcdonalds.csv` | 1,453行15字段，品牌形容词、好感、年龄、到访频率及性别；不能当中国或全球消费者总体，也不是交易数据 |
| 美国房价 | `data/housing/train.csv`、`test.csv`、`data_description.txt` | [Kaggle House Prices](https://www.kaggle.com/competitions/house-prices-advanced-regression-techniques/data)。1,460有售价、1,459无售价；美国Ames历史成交，美元和平方英尺 |
| 电商行为 | `data/retailrocket/` | [Retailrocket](https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset)，2015历史匿名行为，平台使用MySQL汇总快照；未包含实验分组、收入和渠道 |

## 展示与复现

原始数据保留，分析不回写原始文件。新模块由 `analysis/portfolio.py` 统一计算，前端通过JSON API读取，AI调用同一分析层。
美国房价是成交售价，北京是月租金，分开呈现，不生成跨市场租金比较。
旧游戏、贷款和模拟留存源码仅供回退，不在活动模块、AI工具和旧JSON API中继续提供数据。
具体文件的发布者、抽样设计及再分发许可未在原下载材料中保留；不将“可公开下载”写成“官方授权”或“已逐行验证”。
