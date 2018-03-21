#!/usr/bin/python
import gi
import re
import os
import sys
import json
import time
import tempfile
import threading
import subprocess
from collections import OrderedDict
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0') 
gi.require_version('GtkSource', '3.0')
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import GtkSource

BINARY_DIRECTORY = "/".join(sys.argv[0].split("/")[:-1])
BINARY_DIRECTORY = BINARY_DIRECTORY+"/" if BINARY_DIRECTORY else ""

class TerminalWindow(Gtk.ScrolledWindow):
    def __init__(self):
        Gtk.ScrolledWindow.__init__(self)

        self.box = Gtk.EventBox()

        self.box.modify_bg(Gtk.StateType.NORMAL, Gdk.Color.parse("#000000")[1]);

        self.label = Gtk.Label()
        self.label.set_halign(Gtk.Align.START)
        self.label.set_valign(Gtk.Align.START)
        self.label.modify_fg(Gtk.StateType.NORMAL, Gdk.Color.parse("#FFFFFF")[1]);
        self.label.modify_font(Pango.FontDescription("Monospace 10"))

        self.add(self.box)
        self.box.add(self.label)

    def get_text(self):
        return self.label.get_text()

    def set_text(self, text):
        self.label.set_text(text)
        self.get_vadjustment().set_value(self.get_vadjustment().get_upper())

    def connect_to_stream_async(self, stream):
        for line in iter(lambda: stream.readline().decode("utf8"), ''):
            Gdk.threads_enter()
            self.label.set_text(terminal.get_text()+"    "+line)
            Gdk.threads_leave()

    def connect_to_stream(self, stream):
        threading.Thread(target=self.connect_to_stream_async, args=(stream,)).start()

class ConstraintsView(GtkSource.View):
    def __init__(self):
        GtkSource.View.__init__(self)

        tempdirname = tempfile.mkdtemp()
        tempfilehandle = open(tempdirname+"/idl.lang", "w")
        tempfilehandle.write("""<?xml version="1.0" encoding="UTF-8"?>
<language id="idl" _name="LLVM IR" version="2.0" _section="Source">
  <metadata>
    <property name="line-comment-start">#</property>
  </metadata>

  <styles>
    <style id="comment"     _name="Comment"       map-to="def:comment"/>
    <style id="keyword"     _name="Keyword"       map-to="def:keyword"/>
    <style id="identifier"  _name="Identifier"    map-to="def:identifier"/>
  </styles>

  <definitions>
    <context id="keywords" style-ref="keyword">
      <!-- Linkage Types -->
      <keyword>Constraint</keyword>
      <keyword>End</keyword>
      <keyword>and</keyword>
      <keyword>or</keyword>
      <keyword>if not otherwise specified</keyword>
      <keyword>if</keyword>
      <keyword>then</keyword>
      <keyword>else</keyword>
      <keyword>endif</keyword>
      <keyword>with</keyword>
      <keyword>for some</keyword>
      <keyword>for all</keyword>
      <keyword>for</keyword>
      <keyword>as</keyword>
      <keyword>include</keyword>
      <keyword>collect</keyword>
    </context>

    <context id="identifier" style-ref="identifier">
      <match>\{[a-zA-Z_][a-zA-Z0-9_\.\[\],+-]*\}</match>
    </context>

    <context id="line-comment" style-ref="comment" end-at-line-end="true">
      <start>#</start>
    </context>

    <context id="idl">
      <include>
        <context ref="keywords"/>
        <context ref="identifier"/>
        <context ref="line-comment"/>
      </include>
    </context>

  </definitions>
</language>
""")
        tempfilehandle.close()

        language_manager = GtkSource.LanguageManager()
        language_manager.set_search_path([tempdirname]+language_manager.get_search_path())

        self.code = open(BINARY_DIRECTORY+"llvm/lib/IDLParser/IdiomSpecification.txt").read()
        self.get_buffer().set_language(language_manager.get_language("idl"))
        self.get_buffer().set_highlight_syntax(True)
        self.modify_font(Pango.FontDescription("Monospace 10"))
        self.set_show_line_numbers(True)

        os.remove(tempdirname+"/idl.lang")
        os.rmdir(tempdirname)

        self.set_text(self.code)

    def set_text(self, text):
        self.get_buffer().begin_not_undoable_action()
        self.get_buffer().set_text(text)
        self.get_buffer().end_not_undoable_action()

    def get_text(self):
        return self.get_buffer().get_text(self.get_buffer().get_bounds()[0],
                                          self.get_buffer().get_bounds()[1], False)

    def update_file(self):
        new_code = self.get_text()

        if new_code != self.code:
            open(BINARY_DIRECTORY+"llvm/lib/IDLParser/IdiomSpecification.txt", "w").write(new_code)
            self.code = new_code

class CodeView(GtkSource.View):
    def __init__(self):
        GtkSource.View.__init__(self)

        language_manager = GtkSource.LanguageManager()
        self.get_buffer().set_language(language_manager.get_language("cpp"))
        self.get_buffer().set_highlight_syntax(True)
        self.modify_font(Pango.FontDescription("Monospace 10"))
        self.set_show_line_numbers(True)

    def set_text(self, text):
        self.get_buffer().set_text(text)

        terminal.set_text(terminal.get_text()+"Done\n")

    def get_text(self):
        return self.get_buffer().get_text(self.get_buffer().get_bounds()[0],
                                          self.get_buffer().get_bounds()[1], False)

class IRView(GtkSource.View):
    def __init__(self):
        GtkSource.View.__init__(self)

        language_manager = GtkSource.LanguageManager()
        self.get_buffer().set_language(language_manager.get_language("llvm"))
        self.get_buffer().set_highlight_syntax(True)
        self.modify_font(Pango.FontDescription("Monospace 10"))
        self.set_show_line_numbers(True)
        self.set_editable(False)

    def demangle(self, string):
        if string.startswith("_Z") and string[2:3].isdigit():
            if string[3:4].isdigit():
                return string[4:4+int(string[2:4])]
            else:
                return string[3:3+int(string[2:3])]
        elif string.startswith("_Z"):
            return None
        else:
            return string

    def set_text(self, text):

        processed = [None]
        for line in text.split("\n"):
            if line.startswith("define"):
                line = line.split(")")[0]
                first, third = line.split("(", 1)
                first, second = " ".join(first.split()[:-1]), self.demangle(first.split()[-1][1:])

                third = third.replace(" nocapture", "")
                third = third.replace(" signext", "")
                third = third.replace(" readonly", "")
                third = third.replace("%class.", "%")
                third = third.replace("%struct.", "%")
                third = third.replace("%\"class.", "%\"")
                third = third.replace("%\"struct.", "%\"")

                if second:
                    processed.append(first+" @"+second+"("+third+") {")
                else:
                    processed.append(None)

            if line.startswith("  ") and processed[-1]:
                line = line.split(", align")[0]
                line = line.split(", !")[0]
                line = line.split(", !")[0]
                line = line.split(" #")[0]
                line = line.replace("tail call", "call")
                line = line.replace("getelementptr inbounds", "getelementptr")
                line = line.replace(" nonnull", "")
                line = line.replace(" signext", "")
                line = line.replace(" dereferenceable(272)", "")
                line = line.replace("%class.", "%")
                line = line.replace("%struct.", "%")
                line = line.replace("%\"class.", "%\"")
                line = line.replace("%\"struct.", "%\"")

                processed.append(line)

            elif line.startswith("}") and processed[-1]:
                processed.append(line)

            elif line.startswith("; <label>:") and processed[-1]:
                processed.append(line.split(": ")[0])

        text = "\n".join([line for line in processed if line])

        text = text.replace("}\ndefine", "}\n\ndefine")
        text = text.replace("\n; <label>:", "\n\n; <label>:")

        self.get_buffer().set_text(text)

    def get_text(self):
        return self.get_buffer().get_text(self.get_buffer().get_bounds()[0],
                                          self.get_buffer().get_bounds()[1], False)

class SolutionView(Gtk.TreeView):
    def __init__(self):
        self.treestore = Gtk.TreeStore(str, str)

        Gtk.TreeView.__init__(self, self.treestore)

        self.cell1 = Gtk.CellRendererText()
        self.cell2 = Gtk.CellRendererText()

        self.tvcolumn1 = Gtk.TreeViewColumn('detected idioms', self.cell1, text=0)
        self.tvcolumn2 = Gtk.TreeViewColumn('assigned value', self.cell2, text=1)

        self.append_column(self.tvcolumn1)
        self.append_column(self.tvcolumn2)

    def cut_down_line(self, line):
        line = line.split(", align")[0]
        line = line.split(", !")[0]
        line = line.split(", !")[0]
        line = line.split(" #")[0]
        line = line.replace("tail call", "call")
        line = line.replace("getelementptr inbounds", "getelementptr")
        line = line.replace(" nonnull", "")
        line = line.replace(" signext", "")
        line = line.replace(" dereferenceable(272)", "")
        line = line.replace("%class.", "%")
        line = line.replace("%struct.", "%")
        line = line.replace("%\"class.", "%\"")
        line = line.replace("%\"struct.", "%\"")
        return line

    def get_short_synopsis(self, solution):
        abbrev = self.get_synopsis(solution).split(" = ")[0]
        if len(abbrev) <= 20 and "," not in abbrev:
            return abbrev
        elif abbrev.startswith("calculates "):
            return abbrev.split(" from")[0]
        elif abbrev.startswith("transforms "):
            return "calculation"
        elif abbrev.startswith("results in "):
            return "calculation"
        elif abbrev.startswith("outputs "):
            return "calculation"
        elif abbrev.startswith("spans over "):
            return "control structure"
        elif abbrev.startswith("wraps "):
            return "wrapper"
        else:
            return "..."
            
    def get_synopsis(self, solution):
        if repr(type(solution)) in ["<type 'unicode'>", "<class 'str'>"]:
            return self.cut_down_line(solution)
        elif type(solution) is OrderedDict:
            if "input" in solution:
                input_str = self.get_short_synopsis(solution["input"])
                if "value" in solution:
                    return "calculates "+self.get_short_synopsis(solution["value"])+" from "+self.get_synopsis(solution["input"])
                elif "output" in solution:
                    return "calculates "+self.get_short_synopsis(solution["output"])+" from "+self.get_synopsis(solution["input"])
                else:
                    "transforms "+self.get_synopsis(solution["input"])
            elif "value" in solution:
                return "results in "+self.get_synopsis(solution["value"])
            elif "output" in solution:
                return "outputs "+self.get_synopsis(solution["output"])
            elif "begin" in solution and "end" in solution:
                begin_str = self.get_short_synopsis(solution["begin"])
                end_str   = self.get_synopsis(solution["end"])
                return "spans over "+begin_str+" -- "+end_str
            elif len(solution) == 1:
                return "wraps "+self.get_synopsis(list(solution)[0][1])
            else:
                return "..."
        elif type(solution) is list:
            return "[ "+", ".join([self.get_short_synopsis(l) for l in solution])+" ]"
        else:
            return "?"

    def set_idom_at(self, iterator, text):
        for key in text:
            if repr(type(text[key])) in ["<type 'unicode'>", "<class 'str'>"]:
                self.treestore.append(iterator, [key, self.get_synopsis(text[key])])
            elif type(text[key]) is OrderedDict:
                newiter = self.treestore.append(iterator, [key, self.get_synopsis(text[key])])
                self.set_idom_at(newiter, text[key])
            elif type(text[key]) is list:
                iterator2 = self.treestore.append(iterator, [key+"[...]", self.get_synopsis(text[key])])
                for i,t in enumerate(text[key]):
                    self.set_idom_at(iterator2, {"{}[{}]".format(key,i):t})

    def demangle(self, string):
        if string.startswith("_Z") and string[2:3].isdigit():
            if string[3:4].isdigit():
                return string[4:4+int(string[2:4])]
            else:
                return string[3:3+int(string[2:3])]
        elif string.startswith("_Z"):
            return "???"
        return string

    def set_text(self, text):
        self.treestore.clear()
        filedata = json.loads(text, object_pairs_hook=OrderedDict)

        piter1 = self.treestore.append(None, ["idiomatic loops", ""])
        piter2 = self.treestore.append(None, ["non-loop idioms", ""])

        for loopdata in filedata["loops"]:
            functionname = self.demangle(loopdata["function"])
            if len(functionname) > 18:
                functionname = functionname[:15]+"..."
            piter3 = self.treestore.append(piter1, ["line {} in {}".format(loopdata["line"], functionname), ""])

            for idiomdata in loopdata["idioms"]:
                piter4 = self.treestore.append(piter3, [idiomdata["type"], self.get_synopsis(idiomdata["solution"])])
                self.set_idom_at(piter4, idiomdata["solution"])

        for idiomdata in filedata["transformations"]:
            piter5 = self.treestore.append(piter2, [idiomdata["type"]+" in "+self.demangle(idiomdata["function"]), ""])
            self.set_idom_at(piter5, idiomdata["solution"])

        self.expand_row(self.treestore.get_path(piter1), False)
        self.expand_row(self.treestore.get_path(piter2), False)

class RunButton(Gtk.HBox):
    def __init__(self, code_window, ir_window, solution_view):
        Gtk.HBox.__init__(self)

        self.code_window   = code_window
        self.ir_window     = ir_window
        self.solution_view = solution_view

        self.command_label  = Gtk.Label()
        self.run_button     = Gtk.Button()
        self.run_label      = Gtk.AccelLabel("Run")
        self.run_label.set_accel_widget(Gtk.Label("F8"))
        self.run_label.set_accel(Gdk.KEY_A, Gdk.ModifierType.CONTROL_MASK)
        self.run_button.add(self.run_label)

        self.accel_group = Gtk.AccelGroup()
        window.add_accel_group(self.accel_group)
        self.run_button.add_accelerator("activate", self.accel_group, Gdk.KEY_A, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.MASK)

        self.command_label.set_halign(Gtk.Align.START)
        self.command_label.set_valign(Gtk.Align.START)

        self.pack_start(self.command_label, True, True, 0)
        self.pack_start(self.run_button, False, False, 0)

        self.run_button.connect("clicked", self.on_click_run)

    def on_click_run_async(self, data=None):
        Gdk.threads_enter()
        sourcecode   = self.code_window.get_text()
        command      = self.command_label.get_text()
        include_dirs = compiler_opt.get_include_paths()
        Gdk.threads_leave()

        process1 = subprocess.Popen(["ninja", "clang", "-v"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    cwd=BINARY_DIRECTORY+"build")

        Gdk.threads_enter()
        terminal.set_text(terminal.get_text()+"Build updated version of clang\n")
        Gdk.threads_leave()

        terminal.connect_to_stream(process1.stdout)
        process1.wait()

        command = ["./build/bin/clang++", "-std=c++17", "-S", "-emit-llvm", "-O2", "-gline-tables-only", "-xc++", "-", "-o", "-"]
        command = command[:2] + [token for path in include_dirs for token in ["-I", path]] + command[2:] 
        process = subprocess.Popen(command,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   cwd=BINARY_DIRECTORY)

        Gdk.threads_enter()
        terminal.set_text(terminal.get_text()+"Run modified clang over source code\n")
        terminal.set_text(terminal.get_text()+"    "+" ".join(command)+"\n")
        Gdk.threads_leave()

        terminal.connect_to_stream(process.stderr)

        process.stdin.write(sourcecode.encode("utf8"))
        process.stdin.close()
        ir_code = process.stdout.read().decode("utf8")

        return_code = process.wait()
        if return_code == 0:
            solution_code = open("replace-report--.json").read()

            Gdk.threads_enter()
            terminal.set_text(terminal.get_text()+"Done\n")
            Gdk.threads_leave()

            Gdk.threads_enter()
            self.ir_window.set_text(ir_code)
            self.solution_view.set_text(solution_code)
            self.run_button.set_sensitive(True)
            Gdk.threads_leave()
        else:
            Gdk.threads_enter()
            terminal.set_text(terminal.get_text()+"Error\n")
            Gdk.threads_leave()

    def on_click_run(self, data=None):
        self.run_button.set_sensitive(False)
        threading.Thread(target=self.on_click_run_async, args=(data,)).start()

    def set_command_line(self, text):
        self.command_label.set_text(text)

class CompilerOptionWidget(Gtk.VBox):
    def get_menu_item(self, label, icon, key):
        item    = Gtk.MenuItem()
        pack    = Gtk.HBox()
        img     = Gtk.Image()
        label   = Gtk.AccelLabel(label)
        label.set_accel(key, Gdk.ModifierType.CONTROL_MASK)
        img.set_from_stock(icon, 1)
        pack.pack_start(img, False, False, 0)
        pack.pack_start(label, True, True, 0)
        item.add(pack)
        return item
    
    def __init__(self, code_window, ir_window, solution_view):
        Gtk.VBox.__init__(self)
        self.compiler_choices = ["C", "C++"]
        self.compiler_names   = {"C":"clang", "C++":"clang++"}
        self.language_choices = {"C":["c90", "c99", "c11", "gnu90", "gnu99", "gnu11"],
                                 "C++":["c++98", "c++03", "c++11", "c++14", "c++17",
                                        "gnu++98", "gnu++03", "gnu++11", "gnu++14", "gnu++17"]}

        self.code_window   = code_window
        self.ir_window     = ir_window
        self.solution_view = solution_view
        self.include_dirs  = []
        self.filename      = None

        self.menu_bar      = Gtk.MenuBar()
        self.menu_File     = Gtk.MenuItem("File")
        self.menu_Edit     = Gtk.MenuItem("Edit")
        self.menu_Compiler = Gtk.MenuItem("Compiler")
        self.menu_bar.append(self.menu_File)
        self.menu_bar.append(self.menu_Edit)
        self.menu_bar.append(self.menu_Compiler)

        self.submenu_File    = Gtk.Menu()
        self.menuitem_New    = Gtk.MenuItem("New")
        self.menuitem_Open   = Gtk.MenuItem("Open")
        self.menuitem_Save   = Gtk.MenuItem("Save")
        self.menuitem_SaveAs = Gtk.MenuItem("Save As")
        self.menuitem_Close  = Gtk.MenuItem("Close")
#        self.submenu_File.append(self.menuitem_New)
        self.submenu_File.append(self.menuitem_Open)
#        self.submenu_File.append(self.menuitem_Save)
#        self.submenu_File.append(self.menuitem_SaveAs)
        self.submenu_File.append(self.menuitem_Close)
        self.menu_File.set_submenu(self.submenu_File)

        self.submenu_Edit       = Gtk.Menu()
        self.menuitem_Undo      = Gtk.MenuItem("Undo")
        self.menuitem_Redo      = Gtk.MenuItem("Redo")
        self.menuitem_Cut       = Gtk.MenuItem("Cut")
        self.menuitem_Copy      = Gtk.MenuItem("Copy")
        self.menuitem_Paste     = Gtk.MenuItem("Paste")
        self.menuitem_Delete    = Gtk.MenuItem("Delete")
        self.menuitem_SelectAll = Gtk.MenuItem("Select All")
        self.submenu_Edit.append(self.menuitem_Undo)
        self.submenu_Edit.append(self.menuitem_Redo)
        self.submenu_Edit.append(self.menuitem_Cut)
        self.submenu_Edit.append(self.menuitem_Copy)
        self.submenu_Edit.append(self.menuitem_Paste)
        self.submenu_Edit.append(self.menuitem_Delete)
        self.submenu_Edit.append(self.menuitem_SelectAll)
        self.menu_Edit.set_submenu(self.submenu_Edit)

        self.submenu_Compiler     = Gtk.Menu()
        self.menuitem_Compile     = Gtk.MenuItem("Compile")
        self.menuitem_Language    = Gtk.MenuItem("Lanugage")
        self.menuitem_AddIncludes = Gtk.MenuItem("Add Include Path")
        self.menuitem_RemIncludes = Gtk.MenuItem("Remove Include Path")
        self.submenu_Compiler.append(self.menuitem_Compile)
#        self.submenu_Compiler.append(self.menuitem_Language)
        self.submenu_Compiler.append(self.menuitem_AddIncludes)
        self.submenu_Compiler.append(self.menuitem_RemIncludes)
        self.menu_Compiler.set_submenu(self.submenu_Compiler)

        self.submenu_RemIncludes = Gtk.Menu()
        self.menuitem_RemIncludes.set_submenu(self.submenu_RemIncludes)

        self.menu_Language           = Gtk.Menu()
        self.menuitem_Language_nest1 = {}
        self.manu_Language_nest1     = {}
        self.menuitem_Language_nest2 = {}
        for lang in ["C", "C++"]:
            self.menuitem_Language_nest1[lang] = Gtk.MenuItem(lang)
            self.menu_Language.append(self.menuitem_Language_nest1[lang])

            self.manu_Language_nest1[lang]     = Gtk.Menu()
            self.menuitem_Language_nest2[lang] = {}
            for lang2 in self.language_choices[lang]:
                self.menuitem_Language_nest2[lang][lang2] = Gtk.RadioMenuItem(lang2)
                self.manu_Language_nest1[lang].append(self.menuitem_Language_nest2[lang][lang2])
            self.menuitem_Language_nest1[lang].set_submenu(self.manu_Language_nest1[lang])
        self.menuitem_Language.set_submenu(self.menu_Language)
            

        self.submenu_Includes    = Gtk.Menu()
        self.menuitem_AddInclude = Gtk.MenuItem("add include directory")
        self.submenu_Includes.append(self.menuitem_AddInclude)

        self.first_line     = Gtk.HBox()
        self.second_line    = RunButton(code_window, ir_window, solution_view)
        self.include_button = Gtk.Button("Include Dir")
        self.noincl_button  = Gtk.Button("Clear includes")
        self.compiler_combo = Gtk.ComboBoxText()
        self.language_combo = Gtk.ComboBoxText()

        self.pack_start(self.menu_bar, True, True, 0)
        self.first_line.pack_start(self.first_line, True, True, 0)
        self.first_line.pack_start(self.compiler_combo, True, True, 0)
        self.first_line.pack_start(self.language_combo, True, True, 0)
        self.first_line.pack_start(self.include_button, True, True, 0)
        self.first_line.pack_start(self.noincl_button, True, True, 0)

        self.accel_group = Gtk.AccelGroup()
        window.add_accel_group(self.accel_group)
        self.menuitem_New.add_accelerator("activate", self.accel_group, Gdk.KEY_N, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.MASK)
        self.menuitem_Open.add_accelerator("activate", self.accel_group, Gdk.KEY_O, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.MASK)
        self.menuitem_Save.add_accelerator("activate", self.accel_group, Gdk.KEY_S, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.MASK)
        self.menuitem_Close.add_accelerator("activate", self.accel_group, Gdk.KEY_W, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.MASK)
        self.menuitem_Undo.add_accelerator("activate", self.accel_group, Gdk.KEY_Z, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.MASK)
        self.menuitem_Redo.add_accelerator("activate", self.accel_group, Gdk.KEY_Y, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.MASK)
        self.menuitem_Cut.add_accelerator("activate", self.accel_group, Gdk.KEY_X, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.MASK)
        self.menuitem_Copy.add_accelerator("activate", self.accel_group, Gdk.KEY_C, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.MASK)
        self.menuitem_Paste.add_accelerator("activate", self.accel_group, Gdk.KEY_V, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.MASK)
        self.menuitem_SelectAll.add_accelerator("activate", self.accel_group, Gdk.KEY_A, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.MASK)
        self.menuitem_Compile.add_accelerator("activate", self.accel_group, Gdk.KEY_F8, 0, Gtk.AccelFlags.MASK)

        self.menuitem_New.connect      ("activate", self.on_click_new)
        self.menuitem_Open.connect     ("activate", self.on_click_load)
        self.menuitem_Save.connect     ("activate", self.on_click_save)
        self.menuitem_SaveAs.connect   ("activate", self.on_click_saveas)
        self.menuitem_Close.connect    ("activate", self.on_click_close)
        self.menuitem_Undo.connect     ("activate", self.on_click_undo)
        self.menuitem_Redo.connect     ("activate", self.on_click_redo)
        self.menuitem_Cut.connect      ("activate", self.on_click_cut)
        self.menuitem_Copy.connect     ("activate", self.on_click_copy)
        self.menuitem_Paste.connect    ("activate", self.on_click_paste)
        self.menuitem_Delete.connect   ("activate", self.on_click_delete)
        self.menuitem_SelectAll.connect("activate", self.on_click_selectall)
        self.menuitem_Compile.connect  ("activate", self.on_click_compile)

        self.compiler_combo.connect("changed", self.set_language_choices)
        self.language_combo.connect("changed", self.set_command_line)
        self.menuitem_AddIncludes.connect("activate", self.on_click_addinclude)
        self.set_compiler_choices()

    def get_include_paths(self):
        return self.include_dirs

    def set_include_paths(self, paths):
        self.include_dirs = paths

        for child in [child for child in self.submenu_RemIncludes.get_children()]:
            self.submenu_RemIncludes.remove(child)

        for path in paths:
            new_item = Gtk.MenuItem(path)
            self.submenu_RemIncludes.append(new_item)
            new_item.connect("activate", self.on_click_reminclude)

        self.menuitem_RemIncludes.show_all()

    def on_click_new(self, button):
        self.on_click_close(button)

    def on_click_load(self, button):
        if self.filename:
            old_path = "/".join(self.filename.split("/")[:-1])
            include_dirs = [folder for folder in self.get_include_paths() if folder != old_path]
        else:
            include_dirs = self.get_include_paths()

        dialog = Gtk.FileChooserDialog("Open File", window, Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN,   Gtk.ResponseType.OK))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            selected_file = dialog.get_filename()
        else:
            selected_file = None
        dialog.destroy()

        if selected_file:
            self.filename = selected_file
            self.set_include_paths(include_dirs + ["/".join(selected_file.split("/")[:-1])])
            self.code_window.set_text(" ".join(line for line in open(selected_file)))

            if selected_file.split(".")[-1] in ["c", "C"]:
                self.compiler_combo.set_active(0)
            elif selected_file.split(".")[-1] in ["cc", "CC", "cpp", "CPP"]:
                self.compiler_combo.set_active(1)
            else:
                self.set_command_line()

    def on_click_save(self, button):
        if self.filename:
            pass
        else:
            self.on_click_saveas(button)

    def on_click_saveas(self, button):
        if self.filename:
            old_path = "/".join(self.filename.split("/")[:-1])
            include_dirs = [folder for folder in self.get_include_paths() if folder != old_path]
        else:
            include_dirs = self.get_include_paths()

        dialog = Gtk.FileChooserDialog("Save File", window, Gtk.FileChooserAction.SAVE,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN,   Gtk.ResponseType.OK))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            selected_file = dialog.get_filename()
        else:
            selected_file = None
        dialog.destroy()

        if selected_file:
            self.filename = selected_file
            self.set_include_paths(include_dirs + ["/".join(selected_file.split("/")[:-1])])
            self.code_window.set_text(" ".join(line for line in open(selected_file)))
            self.set_command_line()

    def on_click_close(self, button):
        if self.filename:
            old_path = "/".join(self.filename.split("/")[:-1])
            self.set_include_paths([folder for folder in self.get_include_paths() if folder != old_path])
            self.filename     = None
            self.code_window.set_text("")

    def on_click_undo(self, button):
        if self.code_window.is_focus():
            self.code_window.get_buffer().undo()
        elif constrview.is_focus():
            constrview.get_buffer().undo()

    def on_click_redo(self, button):
        if self.code_window.is_focus():
            self.code_window.get_buffer().redo()
        elif constrview.is_focus():
            constrview.get_buffer().redo()

    def on_click_cut(self, button):
        if self.code_window.is_focus():
            self.copy_from_buffer(self.code_window.get_buffer())
            self.paste_to_buffer(self.code_window.get_buffer(), "")
        elif constrview.is_focus():
            self.copy_from_buffer(constrview.get_buffer())
            self.paste_to_buffer(constrview.get_buffer(), "")

    def copy_from_buffer(self, buffer):
        start_iter    = buffer.get_iter_at_mark(buffer.get_selection_bound())
        end_iter      = buffer.get_iter_at_mark(buffer.get_insert())
        selected_text = buffer.get_text(start_iter, end_iter, False)

        if selected_text:
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(buffer.get_text(start_iter, end_iter, False), -1)

    def on_click_copy(self, button):
        if self.code_window.is_focus():
            self.copy_from_buffer(self.code_window.get_buffer())
        elif constrview.is_focus():
            self.copy_from_buffer(constrview.get_buffer())

    def paste_to_buffer(self, buffer, text):
        start_iter    = buffer.get_iter_at_mark(buffer.get_selection_bound())
        end_iter      = buffer.get_iter_at_mark(buffer.get_insert())

        Gtk.TextIter.order(start_iter, end_iter)

        buffer.begin_user_action()
        buffer.set_text(buffer.get_text(buffer.get_bounds()[0], start_iter, False)+text
                       +buffer.get_text(end_iter, buffer.get_bounds()[1], False))
        buffer.end_user_action()

    def on_click_paste(self, button):
        clipboard_text = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()
        if clipboard_text:
            if self.code_window.is_focus():
                self.paste_to_buffer(self.code_window.get_buffer(), clipboard_text)
            elif constrview.is_focus():
                self.paste_to_buffer(constrview.get_buffer(), clipboard_text)

    def on_click_delete(self, button):
        if self.code_window.is_focus():
            self.paste_to_buffer(self.code_window.get_buffer(), "")
        elif constrview.is_focus():
            self.paste_to_buffer(constrview.get_buffer(), "")

    def on_click_selectall(self, button):
        if self.code_window.is_focus():
            self.code_window.get_buffer().move_mark(
                self.code_window.get_buffer().get_selection_bound(),
                self.code_window.get_buffer().get_bounds()[0])
            self.code_window.get_buffer().move_mark(
                self.code_window.get_buffer().get_insert(),
                self.code_window.get_buffer().get_bounds()[1])
        elif constrview.is_focus():
            constrview.get_buffer().move_mark(
                constrview.get_buffer().get_selection_bound(),
                constrview.get_buffer().get_bounds()[0])
            constrview.get_buffer().move_mark(
                constrview.get_buffer().get_insert(),
                constrview.get_buffer().get_bounds()[1])

    def on_click_compile(self, button):
        constrview.update_file()
        self.second_line.on_click_run()

    def set_compiler_choices(self):
        for choice in self.compiler_choices:
            self.compiler_combo.append(choice, choice)
        self.compiler_combo.set_active(0)

    def set_language_choices(self, data=None):
        compiler_choice = self.compiler_combo.get_active_text()

        if compiler_choice in self.compiler_choices:
            self.language_combo.remove_all()
            for choice in self.language_choices[compiler_choice]:
                self.language_combo.append(choice, choice)
        if compiler_choice == "c":
            self.language_combo.set_active(2)
        elif compiler_choice == "c++":
            self.language_combo.set_active(4)

    def on_click_addinclude(self, button=None):
        dialog = Gtk.FileChooserDialog("Open File", window, Gtk.FileChooserAction.SELECT_FOLDER,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN,   Gtk.ResponseType.OK))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            selected_folder = dialog.get_filename()
        else:
            selected_folder = None
        dialog.destroy()

        if selected_folder:
            include_dirs = self.get_include_paths()
            if selected_folder not in include_dirs:
                include_dirs.append(selected_folder)
            self.set_include_paths(include_dirs)

    def on_click_reminclude(self, button=None):
        text = button.get_label()
        self.set_include_paths([path for path in self.get_include_paths() if path != text])

    def set_command_line(self, data=None):
        if self.language_combo.get_active_text():
            binary   = self.compiler_names[self.compiler_combo.get_active_text()]
            compiler = "\""+"/".join(sys.argv[0].split("/")[:-1])+"/build/bin/"+binary+"\""
            standard = "-std="+self.language_combo.get_active_text()
            options  = "-O2 -gline-tables-only -S -emit-llvm -o -"
            langopt  = "-x "+self.compiler_combo.get_active_text()+" -"
            includes = " ".join("\n    -I\""+folder+"\"" for folder in self.include_dirs)

            complete = compiler+" "+standard+" "+options+" "+langopt+" "+includes
            self.second_line.set_command_line(complete)

window        = Gtk.Window()
toplevel_box  = Gtk.VBox()
nextlevel_box = Gtk.HPaned()
main_box      = Gtk.VPaned()
terminal      = TerminalWindow()
leftnotebook  = Gtk.Notebook()
rightnotebook = Gtk.Notebook()
source_box    = Gtk.ScrolledWindow()
ircode_box    = Gtk.ScrolledWindow()
constr_box    = Gtk.ScrolledWindow()
solution_box  = Gtk.ScrolledWindow()
sourcecode    = CodeView()
ircodeveiw    = IRView()
constrview    = ConstraintsView()
solutionview  = SolutionView()
compiler_opt  = CompilerOptionWidget(sourcecode, ircodeveiw, solutionview)

toplevel_box.pack_start(compiler_opt, False, False, 0)
toplevel_box.pack_start(main_box, True, True, 0)
nextlevel_box.pack1(leftnotebook, True, False)
nextlevel_box.pack2(rightnotebook, True, False)
main_box.pack1(nextlevel_box, True, False)
main_box.pack2(terminal, False, False)
leftnotebook.append_page(source_box, Gtk.Label("source code"))
leftnotebook.append_page(ircode_box, Gtk.Label("compiler IR code"))
rightnotebook.append_page(constr_box,   Gtk.Label("constraint specifications"))
rightnotebook.append_page(solution_box, Gtk.Label("detection results"))

window.      add(toplevel_box)
source_box.  add(sourcecode)
ircode_box.  add(ircodeveiw)
constr_box.  add(constrview)
solution_box.add(solutionview)

window.connect("delete-event", Gtk.main_quit)

Gdk.threads_init()
window.show_all()
Gtk.main()
