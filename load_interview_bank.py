"""面试题库使用你发来的原文。只给有误的原句套红，并在题下追加正确备注。"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from main import connect, init_db

DOMAIN = "面试题库"
ROOT = Path(__file__).resolve().parent
SOURCE_A = ROOT / "data" / "source_1.txt"
SOURCE_B = ROOT / "data" / "source_2.txt"
NOTE = "题目和答案都是你发来的原文。红色只标出有误的原句，题下红字是正确备注，其余文字没有改写。"


def mark(text: str, phrase: str, nth: int = 1) -> str:
    start = 0
    found = -1
    for _ in range(nth):
        found = text.find(phrase, start)
        if found < 0:
            raise SystemExit(f"找不到原句：{phrase}")
        start = found + len(phrase)
    return text[:found] + "[[red]]" + phrase + "[[/red]]" + text[found + len(phrase) :]


def remark(text: str, comment: str) -> str:
    return text.rstrip() + "\n\n[[red]]正确备注：\n" + comment.strip() + "[[/red]]\n"


def split_lecture(text: str) -> list[tuple[str, str]]:
    text = text.replace("以上内容存进面试题库", "").strip()
    chunks = re.split(r"\n(?=1\.\d+ )", text)
    cards = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not re.match(r"1\.\d+ ", chunk):
            continue
        title, _, body = chunk.partition("\n")
        cards.append((title.strip(), body.strip()))
    return cards


def split_notes(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    groups: list[list[str]] = []
    expected = 1
    for line in lines:
        matched = re.match(r"^(\d+)\. ", line)
        if matched and int(matched.group(1)) == expected and expected <= 19:
            groups.append([line])
            expected += 1
        elif groups:
            groups[-1].append(line)
    q19 = "\n".join(groups[18])
    head, sep, tail = q19.partition("\n1. 元数据过滤")
    groups[18] = [head.rstrip()]
    rest = ("1. 元数据过滤" + tail).strip()
    headers = [
        "1. 元数据过滤",
        "2. Query改写",
        "3. 查询路由",
        "4. 查询构造",
        "5. HyDE",
        "6. 混合检索",
        "7. 重排序",
        "8. Graph RAG",
        "9、RAG 评测",
    ]
    pattern = "(" + "|".join(re.escape(item) for item in headers) + ")"
    pieces = re.split(pattern, rest)
    sections: list[tuple[str, str]] = []
    i = 1
    while i < len(pieces):
        title = pieces[i].strip()
        body = pieces[i + 1]
        sections.append((title, (title + body).strip()))
        i += 2
    flow_title = "它的整个流程分为这样几步："
    eval_title, eval_body = sections[-1]
    if flow_title in eval_body:
        before, flow = eval_body.split(flow_title, 1)
        sections[-1] = (eval_title, before.replace("以上内容整理进面试题库", "").strip())
        groups[18].append("\n" + flow_title + flow.strip())
    cards = []
    for group in groups:
        raw = "\n".join(group).strip()
        title, _, body = raw.partition("\n")
        cards.append((title.strip(), body.strip()))
    cards.extend(sections)
    return cards


def annotate(cards: list[tuple[str, str]]) -> list[tuple[str, str]]:
    done = []
    for title, body in cards:
        if title.startswith("1.2 "):
            body = mark(body, "加权排序分数融合（RRF）： 对两个结果列表中的每个文档的排名进行加权计算，得到一个新的综合分数并重新排序。这是最常用的方法。")
            body = mark(body, "** reciprocal rank fusion** 取各自排名的倒数后进行加权求和。")
            body = remark(body, "这两处说的是同一种方法。RRF 就是 Reciprocal Rank Fusion，倒数排名融合，只使用名次，不把 BM25 和向量的原始分数加权相加。先归一化再按权重相加的，是下面单独写的线性加权融合。")
        elif title.startswith("3. 装饰器"):
            body = mark(body, "实现了 iter 和 next 方法")
            body = remark(body, "协议方法是 __iter__ 和 __next__。iter 和 next 是内置函数，用来取得迭代器并取出下一项。")
        elif title.startswith("5. 项目"):
            body = mark(body, "流式对话")
            body = remark(body, "流式对话可以作为例子，但要说清用法：模型每产生一段就 yield 一段，接口把这段推给前端，不用等全文结束。生成器就是迭代器。大段检索结果或大文件也可以按迭代器逐条处理，而不是先装进一个完整列表。")
        elif title.startswith("6. python"):
            body = mark(body, "他们主要是与AI大模型平台进行对接")
            body = remark(body, "对接模型接口只是其中一层。LangChain 用来组合提示词、模型、检索和工具；LangGraph 用来保存状态，并允许流程循环或停下来问人。FastAPI 是后面那句已经写明的 Web 框架。")
        elif title.startswith("7. 主流"):
            body = mark(body, "暂时无法在飞书文档外展示此内容")
            body = remark(body, "Milvus 适合大规模并带过滤的生产检索，功能全，部署重。Qdrant 适合中等规模、过滤多的服务。pgvector 适合数据量不大且已经在用 PostgreSQL 的系统。FAISS 是检索库，不是带权限和持久化的数据库。Elasticsearch 适合已经有关键词检索、再补向量的系统。Chroma 适合原型和小库。")
        elif title.startswith("8. 你们"):
            body = mark(body, "用的是string类型, key是问题名称, 值就是回答的内容")
            body = remark(body, "缓存回答可以用 string，但 key 不要用问题原文。问题一长 key 就很大，措辞稍变也命不中，还没有过期时间和知识库版本。key 应使用规范化问题的哈希，并带上知识库版本和模型名，value 是答案 JSON，同时设置 TTL。")
        elif title.startswith("10. 你知道"):
            body = mark(body, "暂时无法在飞书文档外展示此内容")
            body = remark(body, "浮点向量常见 FLAT、IVF_FLAT、IVF_SQ8、IVF_PQ、HNSW、SCANN、DISKANN。GPU 上有 GPU_IVF_FLAT、GPU_IVF_PQ、GPU_CAGRA。二进制有 BIN_FLAT、BIN_IVF_FLAT。稀疏向量有 SPARSE_INVERTED_INDEX、SPARSE_WAND。也可以用 AUTOINDEX。具体名称以所用 Milvus 版本文档为准。")
        elif title.startswith("11. 你是"):
            body = mark(body, "他会先通过一个模型选择使用不同的相似度度量（余弦相似度-文本，欧式距离-图像常用，内积）将数据转换为向量")
            body = mark(body, "适合在小型、百万级数据集上寻求完全精确的搜索结果")
            body = remark(body, "嵌入模型负责把数据变成向量。余弦、内积、欧氏距离是建索引和查询时选择的度量，不是用来把数据变成向量的。图像也不固定使用欧氏距离。FLAT 是精确暴力搜索，适合小数据或作为对照；到了较大数据量，延迟通常已经不合适。")
        elif title.startswith("13. LangChain和"):
            body = mark(body, "组织成一张有向无环图(DAG)")
            body = remark(body, "LangChain 是把提示词、模型和解析串成管道，主流是顺序步骤，也可以有简单分支。它不把业务流程定义成一张图，也不能从后面的步骤回到前面。允许循环、重试和中途问人的是 LangGraph。")
        elif title.startswith("17. 聊一聊"):
            body = mark(body, "LangChain不限技术栈")
            body = remark(body, "LangChain 官方主要是 Python 和 JavaScript，不是任意技术栈都能直接用。Spring AI 面向 Java。差别是生态和接入成本。")
        elif title.startswith("2. Query改写"):
            body = mark(body, "Kafa和rocketMQ")
            body = mark(body, "kafa有哪些特性")
            body = mark(body, "kafa和rocketmq特性有哪些相同点")
            body = mark(body, "孵化是指")
            body = mark(body, "输出富化过后的新问题，不要包含多余的解释性内容", nth=2)
            body = remark(body, "产品名是 Kafka，不是 Kafa 或 kafa。「孵化是指」应为「富化是指」，这一节的标题本来就是富化。多样化提示词的结尾抄成了富化的输出要求；富化只输出一个新问题，多样化要输出 JSON 数组里的多条变体。")
        elif title.startswith("8. Graph RAG"):
            body = mark(body, "不再依赖相似度检索，而是改用图的拓扑结构来定位相关信息")
            body = mark(body, "nero4j")
            body = mark(body, "少--较多--好多--膨胀--减--优!")
            body = mark(body, "Activity\nActiviti")
            body = remark(body, "图检索通常仍要先找到入口实体，这一步经常还是关键词或向量，找到后再沿边做多跳。它是在相似度检索之外增加关系，不是取消相似度检索。产品名是 Neo4j。标红的「规划、Activity、Activiti」不是 Graph RAG 的内容，Activiti 是工作流引擎。")
        elif title.startswith("9、RAG"):
            body = mark(body, "支持没有标准答案情况下自动进行评估!")
            body = remark(body, "没有标准答案时，RAGAS 可以评忠实度和答案相关性。上下文召回、答案正确性通常需要参考材料或标准答案。避免裁判模型胡编：先摘出依据再打分，温度放低，同一题多评一次，再抽一部分人工核对。评测集要像真实提问，每题能指回来源，并包含事实题、多跳题和不该回答的题。题可以从真实日志抽取后由人补出处，也可以让模型按文档出题，再删掉文档里答不出的题。")
        done.append((title, body))
    return done


def main() -> None:
    lecture = split_lecture(SOURCE_A.read_text(encoding="utf-8"))
    notes = split_notes(SOURCE_B.read_text(encoding="utf-8"))
    cards = annotate(lecture + notes)
    init_db()
    stamp = datetime.now().isoformat(timespec="seconds")
    due = date.today().isoformat()
    with connect() as conn:
        row = conn.execute("SELECT id FROM domains WHERE name = ?", (DOMAIN,)).fetchone()
        if row:
            domain_id = row["id"]
            conn.execute("DELETE FROM notes WHERE domain_id = ?", (domain_id,))
            conn.execute("DELETE FROM cards WHERE domain_id = ?", (domain_id,))
        else:
            cur = conn.execute(
                "INSERT INTO domains (name, created_at) VALUES (?, ?)",
                (DOMAIN, stamp),
            )
            domain_id = cur.lastrowid
        conn.execute(
            "INSERT INTO notes (domain_id, title, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (domain_id, "原文说明", NOTE, stamp, stamp),
        )
        for title, body in cards:
            conn.execute(
                """
                INSERT INTO cards
                    (domain_id, note_id, front, back, ease, interval_days, repetitions, due, created_at)
                VALUES (?, NULL, ?, ?, 2.5, 0, 0, ?, ?)
                """,
                (domain_id, title, body, due, stamp),
            )
    print(f"{DOMAIN}: {len(cards)} cards")
    for title, _ in cards:
        print(title)


if __name__ == "__main__":
    main()
