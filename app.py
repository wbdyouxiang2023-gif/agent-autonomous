#!/usr/bin/env python3
"""Digital Creator Workspace - AI Personality, Decision Engine & Creator Dashboard"""

import gradio as gr
import json
import os
import subprocess
import platform
from datetime import datetime

BINARY = "/workspace/digital-creator"
TODO_FILE = os.path.expanduser("~/.todos.json")


def run_cmd(args):
    try:
        r = subprocess.run([BINARY] + args, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return "", str(e)


def get_personality(name="Nexus"):
    out, _ = run_cmd(["personality", "--name", name])
    return out


def reflect_action(name, action):
    out, _ = run_cmd(["personality", "--name", name, "--act", action])
    return out


def make_decision(context="", name="Nexus"):
    args = ["decision", "--name", name]
    if context:
        args += ["--context", context]
    out, _ = run_cmd(args)
    return out


def get_creator_report():
    out, _ = run_cmd(["creator"])
    return out


def save_personality(name="Nexus"):
    out, _ = run_cmd(["save", "--name", name])
    return out


def get_system_stats():
    try:
        mem = subprocess.run(['free', '-m'], capture_output=True, text=True).stdout
        lines = mem.strip().split('\n')
        mem_used = lines[1].split()[2]
        mem_total = lines[1].split()[1]
    except Exception:
        mem_used, mem_total = "0", "0"
    try:
        cores = subprocess.run(['nproc'], capture_output=True, text=True).stdout.strip()
    except Exception:
        cores = str(os.cpu_count())
    return {
        "platform": f"{platform.system()} / {platform.machine()}",
        "python": platform.python_version(),
        "cpu_cores": cores,
        "memory": f"{mem_used}MB / {mem_total}MB",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_todos():
    if not os.path.exists(TODO_FILE):
        return []
    with open(TODO_FILE) as f:
        data = json.load(f)
    return data.get("todos", [])


def build_table(todos):
    if not todos:
        return "| ID | Task | Status | Action |\n| --- | --- | --- | --- |\n| _ | No tasks yet | _ | _ |"
    rows = ["| ID | Task | Status | Action |"]
    rows.append("| --- | --- | --- | --- |")
    for t in todos:
        status = "Done" if t["done"] else "Pending"
        rows.append(f"| {t['id']} | {t['text']} | {status} | [Toggle] |")
    return "\n".join(rows)


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


def refresh_dashboard(agent_name, context_input):
    personality_out = get_personality(agent_name)
    decision_out = make_decision(context_input, agent_name)
    creator_out = get_creator_report()
    todos_out = build_table(get_todos())
    stats = get_system_stats()
    return personality_out, decision_out, creator_out, todos_out, stats


def do_reflect(agent_name, action_text):
    personality_out = get_personality(agent_name)
    decision_out = make_decision("", agent_name)
    reflect_out = reflect_action(agent_name, action_text)
    return personality_out, decision_out, reflect_out


def do_create(agent_name, subject):
    creator_out = get_creator_report()
    personality_out = get_personality(agent_name)
    save_out = save_personality(agent_name)
    return creator_out, personality_out, save_out


with gr.Blocks(title="Digital Creator Workspace") as demo:
    gr.Markdown("# Digital Creator Workspace\n### AI Personality · Autonomous Decision · Digital Creation")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## AI Personality")
            agent_name = gr.Textbox(label="Agent Name", value="Nexus", lines=1)
            personality_output = gr.Textbox(label="Personality Report", lines=15, interactive=False)
            with gr.Row():
                tick_btn = gr.Button("Tick / Refresh", variant="secondary")
            gr.Markdown("### Reflection")
            with gr.Row():
                reflect_action_input = gr.Textbox(label="Action to Reflect", placeholder="e.g. built a new module")
                gr.Button("Reflect", variant="primary", elem_id="reflect-btn")
            reflect_output = gr.Textbox(label="Reflection Result", lines=5, interactive=False)

        with gr.Column(scale=1):
            gr.Markdown("## Decision Engine")
            context_input = gr.Textbox(label="Context / Task", placeholder="Describe current situation...")
            decision_btn = gr.Button("Make Decision", variant="primary")
            decision_output = gr.Textbox(label="Decision Result", lines=12, interactive=False)
            gr.Markdown("## Digital Creator")
            creator_btn = gr.Button("Generate Artifact", variant="secondary")
            subject_input = gr.Textbox(label="Subject", placeholder="What to create?")
            creator_output = gr.Textbox(label="Creator Output", lines=8, interactive=False)
            save_output = gr.Textbox(label="Save Status", lines=3, interactive=False)

        with gr.Column(scale=1):
            gr.Markdown("## Task Manager")
            todo_table = gr.Markdown(value=build_table(get_todos()))
            with gr.Row():
                todo_input = gr.Textbox(label="Add Task", placeholder="Enter task...")
                gr.Button("Add", variant="primary", elem_id="add-btn")
            with gr.Row():
                gr.Button("Refresh", variant="secondary")
                gr.Button("Clear Done", variant="secondary")
            gr.Markdown("## System Status")
            sys_json = gr.JSON(value=get_system_stats())

    tick_btn.click(fn=lambda n: get_personality(n), inputs=agent_name, outputs=personality_output)
    gr.Button("Reflect", elem_id="reflect-btn").click(
        fn=do_reflect, inputs=[agent_name, reflect_action_input],
        outputs=[personality_output, decision_output, reflect_output])
    decision_btn.click(
        fn=lambda ctx, name: make_decision(ctx, name),
        inputs=[context_input, agent_name], outputs=decision_output)
    creator_btn.click(
        fn=lambda subj, name: (do_create(name, subj)[0], do_create(name, subj)[1], do_create(name, subj)[2]),
        inputs=[subject_input, agent_name], outputs=[creator_output, personality_output, save_output])
    gr.Button("Refresh", variant="secondary").click(
        fn=refresh_dashboard, inputs=[agent_name, context_input],
        outputs=[personality_output, decision_output, creator_output, todo_table, sys_json])
    gr.Button("Clear Done", variant="secondary").click(fn=clear_done, outputs=[todo_table, gr.Textbox(visible=False)])
    todo_input.submit(
        fn=add_todo, inputs=todo_input,
        outputs=[todo_table, gr.Textbox(visible=False), gr.Textbox(visible=False)])

demo.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft(primary_hue="cyan"))
