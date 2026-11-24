"""Load the large-model self-study deck. Re-running replaces this domain only."""

from __future__ import annotations

from datetime import date, datetime

from main import connect, init_db

DOMAIN = "大模型自学"
NOTE = "红色是原文里不成立或把两个概念混在一起的地方，红字后面是更准确的说法。图片笔记里没有文字，这里不补不存在的截图。"


def card(number: int, question: str, answer: str) -> tuple[str, str]:
    return f"【自学 {number:02d}】{question}", answer.strip()


CARDS: list[tuple[str, str]] = [
    card(1, "现在说的大模型是什么？", """
现在口语里的大模型，多半指大语言模型（Large Language Model，LLM）。它用大量文本训练，按上下文生成自然语言，所以能做问答、摘要、翻译和写代码。ChatGPT、DeepSeek、通义千问都是这一类产品。

[[red]]原文把例子写成 ChatGPT-o4、qianwen-plus。没有这个正式型号。[[/red]]
[[red]]正确：对话模型常见的是 GPT-4o 这一支；带推理过程的型号写作 o4-mini 等，不叫 ChatGPT-o4。通义千问的接口名是 qwen-plus，不是 qianwen-plus。[[/red]]

[[red]]原文说大模型一般指的都是 LLM，以前的搜索、广告、OCR 等专业模型就是小模型。[[/red]]
[[red]]正确：大模型还包括视觉、语音和多模态模型，不都是 LLM。专业模型和模型大小是两回事。OCR 可以是很小的专用模型，也可以做大；小模型指的是参数少，不是「凡是专用的都叫小模型」。[[/red]]
"""),
    card(2, "大模型的「大」指什么？", """
大主要体现在三件事。

参数多。参数是训练后留在模型里的数值，不是训练文本的复印件。Qwen2.5-72B、LLaMA2-13B 里的 B 是 billion，72B 就是约 720 亿个参数。Ollama 和 Hugging Face 的型号说明指的就是这个规模。

训练数据多。语料来自网页、书、代码和对话，要覆盖多种语言和领域，模型才学得到用词、常识和常见推理习惯。

算力大。训练前沿模型要用大量 GPU 或 TPU，跑很多天，所以训练成本高。个人更常见的是调用已经训好的模型，或者在本地跑量化后的小模型。

[[red]]原文说 GPT-3 的数据集 WebText2 就有数百 GB。[[/red]]
[[red]]正确：WebText 是 GPT-2 的主要语料。GPT-3 是混合语料，WebText2 只是其中一部分（约 190 亿 token）。论文里的全部训练语料大约 4990 亿 token，主要来自过滤后的 Common Crawl，再加上书籍和维基百科。[[/red]]

[[red]]原文说 2026 年后可能就没有高质量数据了，于是靠模型自己造数据就能继续进化。[[/red]]
[[red]]正确：这是早年对公开高质量文本会不够用的预测，不是已经发生的事实。合成数据是模型生成后再筛选的文本，可以补充推理和代码样本。若不筛选，模型会把自己的错误越学越深。数据问题变成「如何筛选和配比」，不是「人工数据已经没了」。[[/red]]
"""),
    card(3, "参数和训练数据是什么关系？", """
训练数据是模型读过的材料。参数是读完之后留下来的内部数值，用来在新的上下文里预测下一个词。

背诗的比喻可以用：读过的诗是数据，留下来的押韵和对仗习惯更接近参数。模型并不把训练文本原样存在参数里，所以它会写得像那么回事，却说不出某句话是不是某本书的原文。

参数多少不等于读过的字数。数据要和参数规模相配：参数很多、高质量数据不够，模型记不稳；数据很多、参数太少，表达能力又不够。
"""),
    card(4, "大模型生成文字的基本原理是什么？", """
GPT 这一类模型的基本任务是：给定已经出现的文字，预测下一个词的概率。

输入「你是个好」，它会给「人」「东西」等各一个概率。生成时把选中的词接回去，再预测下一个，直到结束或达到长度。temperature 越高，越容易选到概率不是最高的词，所以不会每次都一样。

同一个词的下文取决于整句。「苹果很好吃」和「苹果发布了新手机」里的「苹果」不是一个意思。自注意力用来估计句中哪些词对当前这个词更重要。

[[red]]原文写训练就是把句子中间遮住，让模型填 [MASK]，并且每个模型都在调数万亿个旋钮。[[/red]]
[[red]]正确：中间挖空是 BERT 的掩码语言模型。GPT 这种生成模型用的是因果语言模型：只根据左边的词预测右边下一个词，训练时不能看见未来的词。参数规模通常是数十亿到几千亿；「数万亿参数」只适合描述个别超大模型，不是普遍事实。[[/red]]
"""),
    card(5, "Transformer 相对 RNN 改了什么？", """
2017 年《Attention Is All You Need》提出 Transformer，当时要解决的是机器翻译。GPT 这个名字里的 T 就是 Transformer。

RNN 按顺序读词。读到后面时，开头的信息容易变弱，这就是长距离依赖问题；而且后一个词要等前一个词算完，不容易并行。

Transformer 用自注意力直接计算句中任意两个词的关系，距离远也可以。编码器一侧可以同时处理整句，所以训练时更适合 GPU。

[[red]]原文把这篇论文称为大语言模型的开山之作，并说 Transformer 不按顺序、同时看所有词。[[/red]]
[[red]]正确：论文奠定的是架构，论文任务是翻译，不是今天这种对话模型。真正的 LLM 是后来用海量文本、把 Transformer 做得很大。另外，GPT 使用的解码器有因果掩码，预测下一个词时不能看右边还没生成的词。不是所有 Transformer 都允许每个词看见整句的未来。[[/red]]
"""),
    card(6, "自注意力和多头注意力是什么？", """
处理一个词时，模型会给句中其他词各打一个相关性分数，再按分数把这些词的信息加起来。分数高的词对当前词影响更大。代词该指向谁，就靠这种关系来区分。

多头是并行做多组注意力，每组可以关注不同的关系，最后再合并。不是把同一件事按时间重做很多遍。

[[red]]原文用看图片只盯着人脸，说明注意力是为了节省资源、只处理重点。[[/red]]
[[red]]正确：标准自注意力仍要和窗口里的每个词计算相关性，计算量随长度明显增加。它省掉的是 RNN 那种必须逐词等待，不是只算几个重点就把其余词丢掉。[[/red]]
"""),
    card(7, "原始 Transformer 和 GPT 的结构有什么差别？", """
原始翻译模型是编码器加解码器。

词先变成向量，再加上位置编码。因为同时看多个词时，向量本身不包含顺序，「猫追老鼠」和「老鼠追猫」需要位置才能分开。

编码器多层堆叠。每层有多头自注意力、前馈网络，以及残差连接和层归一化。它把整句源文变成一组表示。

解码器也有多层。它先看已经生成的词，再通过交叉注意力去看编码器的结果，然后预测下一个词，把这个词接上继续生成。

[[red]]原文把这套编码器—解码器流程当成今天大模型的完整流程，同时又说 ChatGPT 的核心是解码器。前后不一致。[[/red]]
[[red]]正确：GPT、LLaMA、Qwen 这类生成模型是只有解码器的结构。没有编码器，也没有「回头看编码器」的交叉注意力。编码器—解码器仍用于一部分翻译和 T5 这类模型。BERT 则主要用编码器，适合理解，不负责一个词一个词地往下写。[[/red]]

Transformer 的实际优势是便于并行、能直接建立远距离关系，并成为后来这些模型的共同底座。

[[red]]原文说长距离依赖因此无敌。[[/red]]
[[red]]正确：关系可以跨很远，但仍受上下文长度限制。标准注意力的计算量随长度增长得很快，超长文本还是要切片或另做处理。[[/red]]
"""),
    card(8, "模型和社区平台分别做什么？", """
模型服务和模型社区不是一类东西。

ChatGPT、DeepSeek、通义千问的网站是直接对话。Hugging Face 更像模型、数据集和演示的公共仓库。ModelScope（魔搭）是国内类似的社区，上面有模型、数据集和应用，适合访问 Hugging Face 不便的时候。

Ollama 把开源模型拉到本机运行，并在本机提供接口。量化后的小模型可以只用 CPU，但速度和能跑的规模有限，大模型仍然依赖足够的内存或 GPU。

百炼是阿里云的模型服务和应用平台：可以调用通义等模型，也可以搭知识库、智能体和工作流。它不是开源模型仓库。

[[red]]原文说硅基流动「继承」了很多模型，所以是个中介。[[/red]]
[[red]]正确：用词应是接入，不是继承。硅基流动提供多家模型的推理接口，应用可以用同一套调用方式更换模型。模型权重并不因此属于硅基流动。[[/red]]
"""),
    card(9, "Dify、RAGFlow、n8n、Coze 有什么差别？", """
这几个都能碰到大模型和流程，但侧重点不同。

Dify 用来搭对话应用、知识库和智能体，很多团队用它做内部问答。RAGFlow 更侧重文档解析和检索，适合 PDF、表格很难切的知识库。n8n 擅长把邮件、数据库、定时任务和模型调用串成自动化流程，知识库不是它最强的部分。FastGPT 也偏向知识库问答。

Coze（扣子）是字节的智能体平台，低代码完整，适合较快做出一个小应用。产品本身不是开源社区发行版。开发者也可以用它的插件和接口，并非只给完全不会编程的人。

[[red]]原文先说这些工具差别真不太大，后面又说 n8n 的知识库偏弱、流程编排更强。[[/red]]
[[red]]正确：界面都像在画流程，能力并不一样。选的时候看主任务：要把文档答准，用 Dify 或 RAGFlow；要接很多业务系统，用 n8n；要快速做一个轻量智能体，再看 Coze。[[/red]]
"""),
    card(10, "百炼怎么调用？Coding Plan 要注意什么？", """
百炼上可以试用文本、语音和视觉模型，也有推理、微调、评测和部署。应用侧常见两类：智能体，以及步骤固定的工作流。平台还有 MCP 服务可以直接选用。

代码里调用按量计费的接口时，在控制台创建 API Key，请求发到 OpenAI 兼容地址，例如：

https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions

请求头用 Authorization: Bearer，后面是 Key。正文里的 model 可以是 qwen-plus，messages 里分 system 和 user。Key 不要写进仓库。

[[red]]原文介绍百炼时写成「全链路工具，没包括 MCP、智能体、工作流」。[[/red]]
[[red]]正确：这里的「没」是笔误。百炼的应用开发包括 MCP、智能体和工作流。同一篇笔记前面已经写了包括。[[/red]]

Coding Plan 是另一套套餐。它的 Key 和地址与按量计费不通用。编程工具里常见的兼容地址是：

OpenAI 兼容：https://coding.dashscope.aliyuncs.com/v1
Anthropic 兼容：https://coding.dashscope.aliyuncs.com/apps/anthropic

[[red]]原文说官方禁止通过 API 调用，否则有封号风险。[[/red]]
[[red]]正确：Coding Plan 本身就是用专用 Key 和上述地址，从编程工具里按接口调用。禁止的不是「使用 API」，而是把它当成普通业务接口、转卖，或和按量计费的 Key、地址混用。是否允许你的用法，以当前控制台的使用条款为准。[[/red]]
"""),
    card(11, "怎样用 Ollama 在本地跑模型？", """
一种用法是调用云上已经部署好的模型。另一种是把模型放到自己的机器上。参数不大、并且做了量化时，Ollama 可以在普通电脑上跑。

安装可以从 https://ollama.com/download 下载，项目在 https://github.com/ollama/ollama 。Linux 或 macOS 也可以用官方安装脚本。装好后用 ollama --version 检查。

Docker 可以跑，但只映射端口不够：

[[red]]原文的命令是 docker run -p 11434:11434 ollama/ollama。容器一旦删除，拉下来的模型就没了。[[/red]]
[[red]]正确：加上名字和数据卷，例如 docker run -d --name ollama -p 11434:11434 -v ollama:/root/.ollama ollama/ollama。要用 NVIDIA GPU，还得把显卡挂进容器。没有卷也可以暂时运行，只是不能当作正式安装。[[/red]]

服务默认在本机 11434 端口。常用命令有 pull、run、list、ps、stop、rm、show。

以 deepseek-r1:7b 为例，在 https://ollama.com/library/deepseek-r1 选型号，然后：

ollama pull deepseek-r1:7b
ollama run deepseek-r1:7b

[[red]]原文写「拉取并不部署」。[[/red]]
[[red]]正确：是拉取并准备好这个模型。pull 下载，run 会在本地启动它。[[/red]]

量化模型的内存只是下限，不是保证流畅：1.5B 适合先试；7B 至少准备 8GB 内存；14B 更稳的是 16GB 以上；32B 通常要 32GB 以上。系统自己还要占用内存。

程序调用本机模型时访问 http://localhost:11434 。生成接口是 POST /api/generate，JSON 里给 model 和 prompt。网页界面可以用 Open WebUI，浏览器里也可以用 Page Assist。

DeepSeek-R1 会先输出思考过程。若只想要最终答案，应换非推理型号。

[[red]]原文把替代型号写成 deekseek-v3。[[/red]]
[[red]]正确：拼写是 deepseek-v3。R1 是推理模型，把它的思考关掉，就放弃了选用它的主要原因。[[/red]]
"""),
    card(12, "大模型擅长什么，不擅长什么？", """
语言模型比较擅长：读和总结文本，按要求起草文章或代码，做翻译和信息抽取，解释一段代码，以及回答训练数据里常见的公开知识。这些能力也不是每题都正确，仍然要核对事实和计算结果。

[[red]]原文把图像生成、语音识别、语音合成和视频生成都写成 LLM 擅长的方向，并举了 DALL·E、Stable Diffusion、Whisper、VALL-E、Sora。[[/red]]
[[red]]正确：那些是图像、语音或视频模型，不是语言模型本身。多模态模型可以接收图片或音频，但海报、语音转写和文生视频不是「因为下一个词预测所以顺便会」。介绍能力时要分开说：文本用 LLM，图像、语音、视频用对应的模型。[[/red]]

四个典型限制：

幻觉：句子通顺，不代表事实成立。下一个词概率高，不能证明这件事发生过。

精确计算不稳。比较 3.11 和 3.9 时，模型可能按字符串觉得 3.11 更小。

[[red]]原文说模型本身不具备数据计算能力。[[/red]]
[[red]]正确：纯生成时，算术和大小比较不可靠，尤其是小数、长乘法。不是永远算不对。需要精确结果时，应把计算交给代码或计算器，再把结果交回模型。[[/red]]

知识有截止日期，也没有你们公司的内部文档。关闭联网后，它不知道截止日期之后的事。

[[red]]原文用 2025 年 10 月的一则人物逝世，证明模型必须联网才知道新闻。[[/red]]
[[red]]正确：这个机制是对的，但这则时事不要未经核实写进笔记。考试和面试里改说：训练截止日期之后的事件，不开检索或工具，模型就没有这条新事实。私有制度、内部代码同样不在公开训练集里。[[/red]]
"""),
    card(13, "这些限制分别用什么工程手段补？", """
应用开发不是重新训练一个更大的模型，而是给模型接上资料、工具和流程。

[[red]]原文只列出提示词、RAG、MCP、Function Calling、微调和 Agent，并说学完课程就知道。没有对应到上面的问题。[[/red]]
[[red]]正确：按问题选手段，而不是所有问题都用同一种。[[/red]]

幻觉和「说得像真的」：收紧提示词，要求给出处；用 RAG 把相关原文放进上下文；仍然不对时拒答。微调不保证不再编造。

算数、查询和执行动作：用 Function Calling，让程序去算、去查。MCP 是把这些工具用统一方式接进来，它本身不算数。

新发生的事：接检索或业务接口。只靠模型参数会停在训练截止日期。

公司内部文档：做 RAG，按权限过滤。内部资料没进训练集，不是把模型换大就能知道。

微调适合固定格式、术语或风格，不适合拿来记住每天都在变的制度。

Agent 只用在步骤不固定、要连续调用工具的任务上。一步就能检索回答的，不要套上代理。

[[red]]原文说性能和算力问题未来一定能解决。[[/red]]
[[red]]正确：推理成本会下降，但上下文、延迟和费用仍然是设计限制。方案要写明现在怎么处理，不能写成以后自然消失。[[/red]]
"""),
]


def main() -> None:
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
            (domain_id, "怎么读这套笔记", NOTE, stamp, stamp),
        )
        for front, back in CARDS:
            conn.execute(
                """
                INSERT INTO cards
                    (domain_id, note_id, front, back, ease, interval_days, repetitions, due, created_at)
                VALUES (?, NULL, ?, ?, 2.5, 0, 0, ?, ?)
                """,
                (domain_id, front, back, due, stamp),
            )
    print(f"{DOMAIN}: {len(CARDS)} cards")


if __name__ == "__main__":
    main()
