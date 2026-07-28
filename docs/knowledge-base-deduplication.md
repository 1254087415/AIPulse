# 知识库去重与查漏补缺方案

> 本文档描述 AIPulse 如何判断新获取的信息是否已被用户掌握，并识别知识缺口。对应需求文档 v0.2 章节 **5.5 知识库去重与查漏补缺**。

---

## 1. 问题定义

AIPulse 每天从 RSS、新闻、论文、GitHub、社交媒体等渠道采集大量信息。如果不加过滤，会出现两个问题：

1. **信息重复**：同一事件被多个来源报道，知识库中重复归档多篇相似笔记。
2. **信息过载**：用户无法判断哪些内容是真正的新知识，哪些是已经掌握的内容。

因此需要一套机制：
- **去重**：判断新信息是否已存在等价或高度相似的笔记。
- **查漏补缺**：判断新信息是否补充了已有知识的空白，帮助用户聚焦增量内容。

---

## 2. 核心思路

把问题拆成三层：

```
新信息输入
    ↓
第一层：快速去重（URL / 哈希 / 标题相似度）
    ↓
第二层：语义相似度比对（向量检索）
    ↓
第三层：LLM 关系判断（重复 / 补充 / 全新）
    ↓
增量归档 + 知识缺口提示
```

---

## 3. 第一层：快速去重

### 3.1 URL 去重
- 同一原始链接只处理一次。
- 在 `VideoSummary` / `SourceItem` 表中记录 `original_url`，处理前检查是否存在。

### 3.2 标题/摘要哈希去重
- 对标题和摘要生成 SimHash / MinHash。
- 用于发现内容相同但 URL 不同的转载文章。
- 适合文章类内容，速度快、成本低。

### 3.3 输出
- `duplicate_url`：URL 已存在，直接跳过。
- `duplicate_hash`：标题/摘要高度重复，进入人工确认或自动跳过。
- `needs_semantic_check`：进入第二层。

---

## 4. 第二层：语义相似度比对（RAG 检索）

### 4.1 向量化
- 把新信息的标题 + 摘要生成 embedding（OpenAI text-embedding-3 / 本地模型）。
- 把知识库中已有的笔记（Obsidian 中的归档内容）也生成 embedding。
- 新信息处理时，使用已有的 embedding 做相似度搜索。

### 4.2 向量存储
- 使用 Chroma / Qdrant 存储笔记向量。
- 每个向量关联：`note_id`、`title`、`summary`、`file_path`、`created_at`。
- 向量库需要与 Obsidian 本地文件保持同步（新增/修改/删除）。

### 4.3 相似度阈值

| 相似度 | 含义 | 处理策略 |
|---|---|---|
| > 0.90 | 高度相似 | 大概率重复，进入 LLM 确认 |
| 0.70 - 0.90 | 相关 | 可能是补充内容，进入 LLM 判断 |
| < 0.70 | 弱相关或无相关 | 视为新知识 |

阈值可根据用户反馈动态调整。

### 4.4 输出
- 返回 top-k（默认 5）篇最相关的已有笔记。
- 连同相似度分数一起交给第三层 LLM 判断。

---

## 5. 第三层：LLM 关系判断

### 5.1 Prompt 设计

```
你是一位知识管理专家。请判断以下新信息与用户已有知识的关系。

新信息：
标题：{new_title}
摘要：{new_summary}

用户已有的相关笔记：
{for each note}
- 笔记标题：{note_title}
- 笔记摘要：{note_summary}
- 相似度：{similarity}
{/for}

请判断：
1. 新信息是否基本重复已有知识？（duplicate）
2. 是否补充了已有知识的细节？（supplement）
3. 是否是全新的知识？（new）

输出 JSON：
{
  "relation": "duplicate" | "supplement" | "new",
  "reason": "判断理由，50字以内",
  "target_note_id": "如果是 supplement，对应补充的笔记 ID",
  "knowledge_gap": "如果存在知识缺口，说明新信息填补了哪些空白"
}
```

### 5.2 处理策略

| 关系 | 归档策略 | 用户通知 |
|---|---|---|
| `duplicate` | 不创建新笔记，可选更新互动数据或来源链接 | 可选："该内容与你已有的《xxx》重复，已跳过" |
| `supplement` | 在目标笔记末尾追加新信息，标注补充来源和时间 | "《xxx》已补充新内容" |
| `new` | 创建新笔记，并自动双向链接到相关旧笔记 | "已归档新笔记《xxx》" |

---

## 6. 知识缺口识别

### 6.1 概念

知识缺口识别不是判断"知不知道"，而是判断"知道了 A，但还不知道 B，而新信息提到了 B"。

例如：
- 用户已有 Transformer 笔记。
- 新论文是 "MoE 架构改进"。
- 系统提示："这篇论文涉及 MoE，你的知识库中暂无 MoE 相关内容，是否需要一并了解？"

### 6.2 实现方式

1. **主题覆盖度分析**
   - 对知识库中的笔记做主题聚类（ LDA / BERTopic ）。
   - 生成用户知识图谱：已掌握主题 vs 稀疏主题。
   - 新信息出现时，判断它属于哪个主题，是否在稀疏区域。

2. **LLM 生成缺口提示**
   - 在新信息总结后，让 LLM 分析：
     - 这篇内容涉及哪些概念？
     - 用户的知识库中是否覆盖这些概念？
     - 缺少哪些前置知识？
   - 输出 "建议延伸阅读" 列表。

3. **反向提问**
   - 系统主动向用户提问：
     - "这篇论文提到了 KV Cache 优化，你的笔记中只有基础 KV Cache，是否需要归档这篇优化内容？"
     - "这个话题与你 3 个月前整理的《xxx》相关，但角度不同，要补充吗？"

---

## 7. 数据模型扩展

在 v0.1 的 `VideoSummary` / `SourceItem` / `ArchiveEntry` 基础上，新增：

```python
class NoteEmbedding:
    """知识库笔记的向量表示"""
    id: str
    note_id: str
    note_type: str        # video_summary / article / hotspot
    title: str
    summary: str
    embedding: list       # 向量
    file_path: str        # Obsidian 文件路径
    created_at: datetime

class KnowledgeRelation:
    """新信息与已有笔记的关系判断"""
    id: str
    new_item_id: str
    existing_note_id: str
    relation: str         # duplicate / supplement / new
    similarity: float
    reason: str
    created_at: datetime

class KnowledgeGap:
    """知识缺口提示"""
    id: str
    item_id: str
    topic: str
    missing_prerequisites: list
    suggested_actions: list
    created_at: datetime
```

---

## 8. 技术实现流程

```python
async def process_new_item(item: SourceItem | VideoSummary):
    # 1. URL 去重
    if await is_url_processed(item.url):
        return {"status": "duplicate_url"}

    # 2. 哈希去重
    if await is_hash_duplicate(item.title, item.summary):
        return {"status": "duplicate_hash"}

    # 3. 生成 embedding
    embedding = await embed(f"{item.title}\n{item.summary}")

    # 4. 向量相似度检索
    similar_notes = await vector_store.similarity_search(embedding, k=5)

    # 5. LLM 判断关系
    relation = await llm_judge_relation(item, similar_notes)

    # 6. 根据关系归档
    if relation.relation == "duplicate":
        await mark_as_duplicate(item, relation.target_note_id)
    elif relation.relation == "supplement":
        await append_to_note(item, relation.target_note_id)
    else:
        await create_new_note(item, related_notes=similar_notes)

    # 7. 识别知识缺口
    gaps = await identify_knowledge_gaps(item, similar_notes)
    if gaps:
        await notify_user_about_gaps(item, gaps)

    return {"status": relation.relation}
```

---

## 9. 与 RAG 的关系

| 能力 | 是否用 RAG | 说明 |
|---|---|---|
| 判断"我是否知道 X" | ✅ 是 | RAG 检索已有笔记，LLM 回答 |
| 语义去重 | ⚠️ 部分使用 | 用向量检索找到相似笔记，但判断逻辑需 LLM |
| 知识缺口识别 | ✅ 是 | RAG 检索 + LLM 分析主题覆盖度 |
| 增量归档 | ❌ 不是 RAG | 是基于关系判断的写操作 |

**结论**：RAG 是这套方案的基础设施，但完整方案需要加上 **embedding 相似度 + LLM 关系判断 + 增量归档策略**。

---

## 10. 验收标准

- [ ] 能识别 URL 重复并跳过
- [ ] 能识别标题/摘要高度重复的内容
- [ ] 能通过向量相似度找到相关笔记
- [ ] LLM 能正确判断 duplicate / supplement / new 关系
- [ ] 重复内容不创建新笔记
- [ ] 补充内容追加到原笔记
- [ ] 全新内容创建新笔记并链接相关旧笔记
- [ ] 能生成知识缺口提示
- [ ] 用户可配置相似度阈值

---

## 11. 后续演进

| 阶段 | 能力 |
|---|---|
| v0.2 | 基础去重：URL + embedding + LLM 关系判断 |
| v0.3 | 自动双向链接、归档标签可视化 |
| v0.4 | 主题覆盖度分析、知识图谱、主动推荐延伸阅读 |
