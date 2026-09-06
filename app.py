#!/usr/bin/env python3
"""Agent Autonomous Workspace - Beautiful Dashboard"""

import gradio as gr
import json
import os
import subprocess
import platform
import time
from datetime import datetime
from pathlib import Path

TODO_FILE = os.path.expanduser("~/.todos.json")
WORKSPACE = Path("/workspace")

def get_todos():
    if not os.path.exists(TODO_FILE):
        return []
    with open(TODO_FILE) as f:
        data = json.load(f)
    return data.get("todos", [])

def get_system_stats():
    try:
        mem = subprocess.run(['free', '-m'], capture_output=True, text=True).stdout
        lines = mem.strip().split('\n')
        mem_used = lines[1].split()[2]
        mem_total = lines[1].split()[1]
    except:
        mem_used, mem_total = "0", "0"
    return {
        "platform": f"{platform.system()} / {platform.machine()}",
        "python": platform.python_version(),
        "cpu_cores": os.cpu_count(),
        "memory": f"{mem_used}MB / {mem_total}MB",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

def add_todo(text):
    if not text.strip():
        return build_table(get_todos()), "Please enter a task", ""
    todos = get_todos()
    next_id = max([t["id"] for t in todos], default=0) + 1
    todos.append({"id": next_id, "text": text.strip(), "done": False, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
    with open(TODO_FILE, "w") as f:
        json.dump({"path": TODO_FILE, "todos": todos, "next_id": next_id + 1}, f, indent=2)
    return build_table(todos), f"Task #{next_id} added!", ""

def clear_done():
    todos = [t for t in get_todos() if not t["done"]]
    with open(TODO_FILE, "w") as f:
        json.dump({"path": TODO_FILE, "todos": todos, "next_id": max([t["id"] for t in todos], default=0) + 1}, f, indent=2)
    return build_table(todos), "Cleared completed tasks"

def refresh_all():
    return build_table(get_todos()), get_system_stats()

def build_table(todos):
    if not todos:
        return "| ID | Task | Status | Action |\n| --- | --- | --- | --- |\n| _ | No tasks yet | _ | _ |"
    rows = ["| ID | Task | Status | Action |"]
    rows.append("| --- | --- | --- | --- |")
    for t in todos:
        status = "Done" if t["done"] else "Pending"
        rows.append(f"| {t['id']} | {t['text']} | {status} | [Toggle] |")
    return "\n".join(rows)

with gr.Blocks(title="Agent Workspace") as demo:
    gr.Markdown("# 🤖 Agent Autonomous Workspace\n### Self-Driving AI Development System")
    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("## 📋 Task Manager")
            todo_table = gr.Markdown(value=build_table(get_todos()))
            with gr.Row():
                todo_input = gr.Textbox(label="Add Task", placeholder="Enter task...")
                gr.Button("Add", variant="primary", elem_id="add-btn")
            with gr.Row():
                gr.Button("Refresh", variant="secondary")
                gr.Button("Clear Done", variant="secondary")
        with gr.Column(scale=1):
            gr.Markdown("## 📊 System Status")
            sys_json = gr.JSON(value=get_system_stats())
    demo.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft(primary_hue="cyan"))
