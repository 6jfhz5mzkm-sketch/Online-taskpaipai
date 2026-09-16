# -*- coding: utf-8 -*-
"""从历史 Codex 会话中抽取各子 Agent 的对话资料（总控专用工具）。"""
import json
import os

SESS = r"C:\Users\ext.ahs.luoyingkai1\.codex\sessions"
OUT = os.path.join(os.getcwd(), "dev-docs", "子Agent资料")

BOILER = (
    "permissions instructions",
    "AGENTS.md instructions",
    "multi_agent_mode",
    "<environment_context>",
    "## Skills",
    "You are Codex",
    "app-context",
    "collaboration_mode",
)

ROLES = {
    "规划Agent": [
        (r"2026\07\16\rollout-2026-07-16T14-10-42-019f698c-7cc9-7f40-a2c4-3dd372f52602.jsonl", "立项（产品讨论与立项设计）"),
        (r"2026\07\09\rollout-2026-07-09T12-03-16-019f450b-4da5-7712-811d-08594a457011.jsonl", "基础框架沟通（商家成长体系指引）"),
        (r"2026\07\16\rollout-2026-07-16T16-58-19-019f6a25-dea0-7270-a6fc-679b6d989f85.jsonl", "设计方案规范（设计规范/开发规则/骨架搭建）"),
    ],
    "前端Agent-阶段一": [
        (r"2026\07\10\rollout-2026-07-10T10-18-47-019f49d2-00cb-7361-b08b-254cbbf1271e.jsonl", "【前端】阶段一开发（基于高保真原型）"),
        (r"2026\07\16\rollout-2026-07-16T17-42-34-019f6a4e-6ce1-72f3-866c-b8974a3aa199.jsonl", "【前端】阶段一开发（按规范重开发）"),
        (r"2026\07\16\rollout-2026-07-16T17-59-38-019f6a5e-0004-78b0-8c6f-c33de2ce8cd2.jsonl", "阶段一组件开发"),
        (r"2026\07\16\rollout-2026-07-16T18-00-05-019f6a5e-6ab8-7420-8618-2f809b3b9019.jsonl", "阶段一文件骨架"),
    ],
    "前端Agent-阶段二": [
        (r"2026\08\05\rollout-2026-08-05T16-06-10-019fd0f5-4fd3-7ab0-9035-cd33c62434e7.jsonl", "阶段二前端开发"),
    ],
    "后端Agent": [
        (r"2026\07\17\rollout-2026-07-17T09-47-35-019f6dc1-dfff-76e3-9b60-dca0a87ec1dd.jsonl", "数据库开发"),
        (r"2026\07\20\rollout-2026-07-20T17-23-05-019f7ed5-fc39-7e53-ae13-2e7b23dc9da2.jsonl", "后端技术方案"),
    ],
    "数据库开发Agent": [
        (r"2026\07\17\rollout-2026-07-17T09-47-35-019f6dc1-dfff-76e3-9b60-dca0a87ec1dd.jsonl", "数据库开发"),
    ],
    "测试Agent": [
        (r"2026\07\10\rollout-2026-07-10T10-14-06-019f49cd-b6dc-76d2-ab44-d258cdd88403.jsonl", "测试流程"),
    ],
    "脑暴Agent": [
        (r"2026\07\28\rollout-2026-07-28T15-56-24-019fa7b9-7c82-7282-8d50-6db5ebaa6736.jsonl", "脑暴"),
    ],
}


def extract_text(content):
    if isinstance(content, list):
        parts = []
        for it in content:
            if isinstance(it, dict):
                t = it.get("text") or it.get("input_text") or it.get("output_text") or ""
                if t:
                    parts.append(t)
        return " ".join(parts)
    return ""


def is_boiler(txt):
    head = txt[:80]
    return any(b in head for b in BOILER) or txt.startswith("## Referenced chats")


def cap(txt, n=800):
    txt = txt.strip()
    idx = txt.find("## Referenced chats")
    if idx >= 0:
        txt = txt[:idx].strip()
    if len(txt) > n:
        return txt[:n] + " ……（截断）"
    return txt


def main():
    os.makedirs(OUT, exist_ok=True)
    for role, sources in ROLES.items():
        lines = [
            f"# {role} 历史对话资料\n",
            f"> 本文件由总控从历史会话中抽取生成（{len(sources)} 个来源），用于恢复该子 Agent 的历史上下文。\n",
            "> 子 Agent 应通读本文件后按角色卡进入待命；本文件只读，禁止修改。\n",
        ]
        last_user = 0
        for src, label in sources:
            path = os.path.join(SESS, src)
            if not os.path.exists(path):
                lines.append(f"\n## 来源缺失：{label}（{src}）\n")
                continue
            lines.append(f"\n## 来源：{label}\n")
            n_user = 0
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    if o.get("type") != "response_item":
                        continue
                    p = o.get("payload", {})
                    if p.get("type") != "message":
                        continue
                    role_msg = p.get("role")
                    if role_msg not in ("user", "assistant"):
                        continue
                    txt = extract_text(p.get("content", []))
                    if not txt or is_boiler(txt):
                        continue
                    if role_msg == "user":
                        n_user += 1
                        lines.append(f"\n### 用户（{n_user}）\n\n{cap(txt)}\n")
                    else:
                        lines.append(f"\n**Agent：** {cap(txt, 500)}\n")
            last_user += n_user
        out = os.path.join(OUT, f"{role}.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"{role}: {os.path.getsize(out)} bytes, {last_user} user msgs")


if __name__ == "__main__":
    main()
