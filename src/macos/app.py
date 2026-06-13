"""
Workflow Engine macOS GUI
==========================
tkinter 桌面应用，提供工作流管理功能的图形界面
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from database import WorkflowDatabase
from dag_executor import DAGExecutor
from node_executors import create_default_executors
from models import WorkflowDefinition, NodeType
from datetime import datetime


class WorkflowApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Workflow Engine - 工作流编排引擎")
        self.root.geometry("900x650")
        self.root.configure(bg="#0d1117")

        self.db = WorkflowDatabase("data/dashboard.db")
        executors = create_default_executors()
        self.executor = DAGExecutor(executors)
        self._build_ui()
        self._load_workflows()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background="#0d1117")
        style.configure("TNotebook.Tab", background="#161b22", foreground="#c9d1d9", padding=[12, 6])
        style.map("TNotebook.Tab", background=[("selected", "#58a6ff")], foreground=[("selected", "#fff")])
        style.configure("TFrame", background="#0d1117")
        style.configure("TLabel", background="#0d1117", foreground="#c9d1d9")
        style.configure("TButton", background="#238636", foreground="#fff")
        style.map("TButton", background=[("active", "#2ea043")])

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 工作流列表 Tab
        list_frame = ttk.Frame(notebook)
        notebook.add(list_frame, text="工作流列表")
        bf = ttk.Frame(list_frame)
        bf.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(bf, text="刷新", command=self._load_workflows).pack(side=tk.LEFT)
        ttk.Button(bf, text="删除选中", command=self._delete_workflow).pack(side=tk.LEFT, padx=8)
        self.wf_list = tk.Listbox(list_frame, bg="#0d1117", fg="#c9d1d9", selectbackground="#58a6ff",
                                    font=("Menlo", 12), borderwidth=0, highlightthickness=0)
        self.wf_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,8))

        # 创建工作流 Tab
        create_frame = ttk.Frame(notebook)
        notebook.add(create_frame, text="创建工作流")
        ttk.Label(create_frame, text="名称:").pack(anchor=tk.W, padx=8, pady=(8,2))
        self.wf_name = tk.Entry(create_frame, bg="#0d1117", fg="#c9d1d9", insertbackground="#c9d1d9",
                                  font=("Menlo", 12))
        self.wf_name.pack(fill=tk.X, padx=8)
        ttk.Label(create_frame, text="描述:").pack(anchor=tk.W, padx=8, pady=(8,2))
        self.wf_desc = scrolledtext.ScrolledText(create_frame, height=4, bg="#0d1117", fg="#c9d1d9",
                                                   insertbackground="#c9d1d9", font=("Menlo", 12))
        self.wf_desc.pack(fill=tk.X, padx=8)
        ttk.Button(create_frame, text="创建", command=self._create_workflow).pack(anchor=tk.W, padx=8, pady=6)
        self.create_result = scrolledtext.ScrolledText(create_frame, height=4, bg="#161b22", fg="#c9d1d9",
                                                        font=("Menlo", 11), state=tk.DISABLED)
        self.create_result.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,8))

        # 执行 Tab
        run_frame = ttk.Frame(notebook)
        notebook.add(run_frame, text="执行工作流")
        ttk.Label(run_frame, text="工作流 ID:").pack(anchor=tk.W, padx=8, pady=(8,2))
        self.run_id = tk.Entry(run_frame, bg="#0d1117", fg="#c9d1d9", insertbackground="#c9d1d9",
                                font=("Menlo", 12))
        self.run_id.pack(fill=tk.X, padx=8)
        ttk.Label(run_frame, text="输入参数 (JSON):").pack(anchor=tk.W, padx=8, pady=(8,2))
        self.run_inputs = tk.Entry(run_frame, bg="#0d1117", fg="#c9d1d9", insertbackground="#c9d1d9",
                                    font=("Menlo", 12))
        self.run_inputs.pack(fill=tk.X, padx=8)
        ttk.Button(run_frame, text="执行", command=self._run_workflow).pack(anchor=tk.W, padx=8, pady=6)
        self.run_result = scrolledtext.ScrolledText(run_frame, height=15, bg="#161b22", fg="#c9d1d9",
                                                     font=("Menlo", 11), state=tk.DISABLED)
        self.run_result.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,8))

        # 节点类型 Tab
        node_frame = ttk.Frame(notebook)
        notebook.add(node_frame, text="节点类型")
        ttk.Label(node_frame, text="支持的节点类型:", font=("Menlo", 14)).pack(anchor=tk.W, padx=8, pady=8)
        for nt in NodeType:
            f = ttk.Frame(node_frame)
            f.pack(fill=tk.X, padx=8, pady=2)
            ttk.Label(f, text=nt.value, foreground="#58a6ff", font=("Menlo", 13, "bold")).pack(side=tk.LEFT, padx=(0,12))
            desc = {"start": "开始节点", "end": "结束节点", "llm": "LLM 调用", "tool": "工具调用",
                    "condition": "条件判断", "code": "代码执行", "transform": "数据转换"}.get(nt.value, "")
            ttk.Label(f, text=desc).pack(side=tk.LEFT)

    def _set(self, widget, text):
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.config(state=tk.DISABLED)

    def _load_workflows(self):
        self.wf_list.delete(0, tk.END)
        workflows = self.db.list_workflows()
        if isinstance(workflows, list):
            for wf in workflows:
                name = wf.get("name", "未命名") if isinstance(wf, dict) else getattr(wf, "name", "未命名")
                wf_id = wf.get("id", "") if isinstance(wf, dict) else getattr(wf, "id", "")
                self.wf_list.insert(tk.END, f"{name}  [{wf_id}]")

    def _create_workflow(self):
        name = self.wf_name.get().strip()
        desc = self.wf_desc.get("1.0", tk.END).strip()
        if not name:
            messagebox.showwarning("提示", "名称不能为空")
            return
        wf = WorkflowDefinition(name=name, description=desc, nodes=[], edges=[])
        wf.created_at = datetime.now()
        wf.updated_at = datetime.now()
        self.db.save_workflow(wf)
        self._set(self.create_result, f"已创建工作流: {name}\nID: {wf.id}")
        self._load_workflows()

    def _delete_workflow(self):
        sel = self.wf_list.curselection()
        if not sel:
            return
        item = self.wf_list.get(sel[0])
        wf_id = item.split("[")[-1].rstrip("]").strip()
        if wf_id:
            self.db.delete_workflow(wf_id)
            self._load_workflows()

    def _run_workflow(self):
        wf_id = self.run_id.get().strip()
        if not wf_id:
            messagebox.showwarning("提示", "请输入工作流 ID")
            return
        import json
        inputs = {}
        try:
            inputs = json.loads(self.run_inputs.get() or "{}")
        except json.JSONDecodeError:
            messagebox.showerror("错误", "输入参数格式错误")
            return
        wf = self.db.get_workflow(wf_id)
        if not wf:
            messagebox.showerror("错误", "工作流不存在")
            return
        self._set(self.run_result, "执行中...\n")
        self.root.update()
        result = self.executor.execute(wf, inputs=inputs)
        import json as j
        text = j.dumps(result, indent=2, ensure_ascii=False, default=str) if isinstance(result, dict) else str(result)
        self._set(self.run_result, text)


def main():
    root = tk.Tk()
    WorkflowApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
