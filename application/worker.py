##################################################################################
#                                                                                #
# Copyright (c) 2020 AECgeeks                                                    #
#                                                                                #
# Permission is hereby granted, free of charge, to any person obtaining a copy   #
# of this software and associated documentation files (the "Software"), to deal  #
# in the Software without restriction, including without limitation the rights   #
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell      #
# copies of the Software, and to permit persons to whom the Software is          #
# furnished to do so, subject to the following conditions:                       #
#                                                                                #
# The above copyright notice and this permission notice shall be included in all #
# copies or substantial portions of the Software.                                #
#                                                                                #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR     #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,       #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE    #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER         #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,  #
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE  #
# SOFTWARE.                                                                      #
#                                                                                #
##################################################################################

import os
import sys
import json
import glob
import platform
import traceback
import importlib
import subprocess
import tempfile
import operator
import shutil

import threading
import requests

on_windows = platform.system() == 'Windows'
ext = ".exe" if on_windows else ""
exe_path = os.path.join(os.path.dirname(__file__), "win" if on_windows else "nix")
IFCCONVERT = os.path.join(exe_path, "IfcConvert") + ext
if not os.path.exists(IFCCONVERT):
    IFCCONVERT = "IfcConvert"


import utils
import database


def set_progress(id, progress):
    session = database.Session()
   
    id = id.split("_")[0]

    model = session.query(database.model).filter(database.model.code == id).all()[0]
    model.progress = int(progress)
    session.commit()
    session.close()


class task(object):
    def __init__(self, progress_map):
        import inspect
        print(self.__class__.__name__, inspect.getfile(type(self)), *progress_map)
        self.begin, self.end = progress_map

    def sub_progress(self, i):
        set_progress(self.id, self.begin + (self.end - self.begin) * i / 100.)

    def __call__(self, directory, id, *args):
        self.id = id
        self.execute(directory, id, *args)
        self.sub_progress(100)


class general_info_task(task):
    
    est_time = 1
    
    def execute(self, directory, id):
        info_program = os.path.join(os.getcwd() + "/checks", "info.py")
        subprocess.call([sys.executable, info_program, id + ".ifc", os.path.join(os.getcwd())], cwd=directory)


class syntax_validation_task(task):
    est_time = 10

    def execute(self, directory, id):
        f = open(os.path.join(directory, "dresult_syntax.json"), "w")
        check_program = os.path.join(os.getcwd() + "/checks/step-file-parser", "parse_file.py")
        #subprocess.call([sys.executable, check_program, id + ".ifc", "--json"], cwd=directory, stdout=f)
        proc = subprocess.Popen([sys.executable, check_program, id + ".ifc", "--json"], cwd=directory, stdout=subprocess.PIPE)
        i = 0
        while True:
            ch = proc.stdout.read(1)
            
            if not ch and proc.poll() is not None:
                break

            if ch and ord(ch) == ord('.'):
                i += 1
                self.sub_progress(i)



class ifc_validation_task(task):
    est_time = 10

    def execute(self, directory, id):
        f = open(os.path.join(directory, "dresult_schema.json"), "w")
        check_program = os.path.join(os.getcwd() + "/checks", "validate.py")
        proc = subprocess.Popen([sys.executable, check_program, id + ".ifc", "--json"], cwd=directory, stdout=subprocess.PIPE)
        i = 0
        while True:
            ch = proc.stdout.read(1)
            
            if not ch and proc.poll() is not None:
                break

            if ch and ord(ch) == ord('.'):
                i += 1
                self.sub_progress(i)


class mvd_validation_task(task):
    est_time =10

    
    def execute(self, directory, id):
        check_program = os.path.join(os.getcwd() + "/checks", "check_MVD.py")
        outname = id +"_mvd.txt"
      
        with open(os.path.join(directory, outname), "w") as f:
            subprocess.call([sys.executable, check_program, id + ".ifc"],cwd=directory,stdout=f)

class bsdd_validation_task(task):
    est_time = 10

    def execute(self, directory, id):
        
        session = database.Session()

        model = session.query(database.model).filter(database.model.code == id).all()[0]

        validation_task = database.bsdd_validation_task(model.id)

        session.add(validation_task)
        session.commit()
        validation_task_id = str(validation_task.id)
        session.close()

        check_program = os.path.join(os.getcwd() + "/checks", "check_bsdd_v2.py")

        proc = subprocess.Popen([sys.executable, check_program, "--input", id + ".ifc", "--task",validation_task_id], cwd=directory, stdout=subprocess.PIPE)
        i = 0
        while True:
            ch = proc.stdout.read(1)
        
            if not ch and proc.poll() is not None:
                break

            if ch and ord(ch) == ord('.'):
                i += 1
                self.sub_progress(i)


class ids_validation_task(task):
    est_time = 10

    def execute(self, directory, id):
        check_program = os.path.join(os.getcwd() + "/checks", "ids.py")
        #todo allow series of ids specs to be processed
        ids_files = [f for f in os.listdir(directory) if f.endswith(".xml")]
        proc = subprocess.Popen([sys.executable, check_program, ids_files[0], id + ".ifc"], cwd=directory, stdout=subprocess.PIPE)
        i = 0
        while True:
            ch = proc.stdout.read(1)
        
            if not ch and proc.poll() is not None:
                break

            if ch and ord(ch) == ord('.'):
                i += 1
                self.sub_progress(i)


class xml_generation_task(task):
    est_time = 1

    def execute(self, directory, id):
        subprocess.call([IFCCONVERT, id + ".ifc", id + ".xml", "-yv"], cwd=directory)


class geometry_generation_task(task):
    est_time = 10

    def execute(self, directory, id):
        proc = subprocess.Popen([IFCCONVERT, id + ".ifc", id + ".glb", "-qyv", "--log-format", "json", "--log-file", "log.json"], cwd=directory, stdout=subprocess.PIPE)
        i = 0
        while True:
            ch = proc.stdout.read(1)

            if not ch and proc.poll() is not None:
                break

            if ch and ord(ch) == ord('.'):
                i += 1
                self.sub_progress(i)

        # GLB generation is mandatory to succeed
        if proc.poll() != 0:
            raise RuntimeError()

                
class glb_optimize_task(task):
    est_time = 1
    
    def execute(self, directory, id):
        if subprocess.call(["gltf-pipeline" + ('.cmd' if on_windows else ''), "-i", id + ".glb", "-o", id + ".optimized.glb", "-b", "-d"], cwd=directory) == 0:
            os.rename(os.path.join(directory, id + ".glb"), os.path.join(directory, id + ".unoptimized.glb"))
            os.rename(os.path.join(directory, id + ".optimized.glb"), os.path.join(directory, id + ".glb"))


class gzip_task(task):
    est_time = 1
    order = 2000
    
    def execute(self, directory, id):
        import gzip
        for ext in ["glb", "xml", "svg"]:
            fn = os.path.join(directory, id + "." + ext)
            if os.path.exists(fn):
                with open(fn, 'rb') as orig_file:
                    with gzip.open(fn + ".gz", 'wb') as zipped_file:
                        zipped_file.writelines(orig_file)
                        
                        
class svg_rename_task(task):
    """
    In case of an upload of multiple files copy the SVG file
    for an aspect model with [\w+]_[0-9].svg to [\w+].svg if
    and only if the second file does not exist yet or the
    first file is larger in terms of file size.
    """
    
    est_time = 1
    order = 1000
    
    def execute(self, directory, id):
        svg1_fn = os.path.join(directory, id + ".svg")
        svg2_fn = os.path.join(directory, id.split("_")[0] + ".svg")
        
        if os.path.exists(svg1_fn):
            if os.path.exists(svg1_fn) and (not os.path.exists(svg2_fn) or os.path.getsize(svg1_fn) > os.path.getsize(svg2_fn)):
                shutil.copyfile(svg1_fn, svg2_fn)


class svg_generation_task(task):
    est_time = 10

    def execute(self, directory, id):
        proc = subprocess.Popen([IFCCONVERT, id + ".ifc", id + ".svg", "-qy", "--plan", "--model", "--section-height-from-storeys", "--door-arcs", "--print-space-names", "--print-space-areas", "--bounds=1024x1024", "--include", "entities", "IfcSpace", "IfcWall", "IfcWindow", "IfcDoor", "IfcAnnotation"], cwd=directory, stdout=subprocess.PIPE)
        i = 0
        while True:
            ch = proc.stdout.read(1)

            if not ch and proc.poll() is not None:
                break

            if ch and ord(ch) == ord('.'):
                i += 1
                self.sub_progress(i)


def do_process(id, validation_config, ids_spec):

    d = utils.storage_dir_for_id(id)

    
    with open(os.path.join(d,'config.json'), 'w') as outfile:
        json.dump(validation_config, outfile)

    if ids_spec:    
        ids_spec_storages = []
        n_ids_spec = int(len(ids_spec)/32)
        ids_spec_storages = []
        b = 0
        j = 1
        a = 32

        for n in range(n_ids_spec):
            token = ids_spec[b:a]
            ids_spec_storages.append(utils.storage_dir_for_id(token))
            # count += 1
            b = a
            j+=1
            a = 32*j

        for ids_folder in ids_spec_storages:
            for ids_file in os.listdir(ids_folder):
                shutil.copy(os.path.join(ids_folder, ids_file), d )
        
    input_files = [name for name in os.listdir(d) if os.path.isfile(os.path.join(d, name)) and os.path.join(d, name).endswith("ifc")]
    
    tasks = [general_info_task]

    

    for task, to_validate in validation_config["config"].items():
       
        if int(to_validate):
            if task == 'syntax' and to_validate:
                tasks.append(syntax_validation_task)
            elif task == 'schema' and to_validate:
                tasks.append(ifc_validation_task)
            elif task == 'mvd' and to_validate:
                tasks.append(mvd_validation_task)
            elif task == 'bsdd' and to_validate:
                tasks.append(bsdd_validation_task)
            elif task =='ids' and to_validate:
                tasks.append(ids_validation_task)

    
    # tasks = [
    #     # syntax_validation_task,
    #     # ifc_validation_task,
    #     bsdd_validation_task,
    #     mvd_validation_task,
    #     # xml_generation_task,
    #     # geometry_generation_task,
    #     # svg_generation_task,
    #     # glb_optimize_task,
    #     # gzip_task
    # ]
    
    tasks_on_aggregate = []
    
    is_multiple = any("_" in n for n in input_files)
    if is_multiple:
        tasks.append(svg_rename_task)
    
    """
    # Create a file called task_print.py with the following
    # example content to add application-specific tasks

    import sys
    
    from worker import task as base_task
    
    class task(base_task):
        est_time = 1    
        
        def execute(self, directory, id):
            print("Executing task 'print' on ", id, ' in ', directory, file=sys.stderr)
    """
    

    for fn in glob.glob("task_*.py"):
        mdl = importlib.import_module(fn.split('.')[0])
        if getattr(mdl.task, 'aggregate_model', False):
            tasks_on_aggregate.append(mdl.task)
        else:
            tasks.append(mdl.task)
        
    tasks.sort(key=lambda t: getattr(t, 'order', 10))
    tasks_on_aggregate.sort(key=lambda t: getattr(t, 'order', 10))

    elapsed = 0
    set_progress(id, elapsed)
    
    n_files = len([name for name in os.listdir(d) if os.path.isfile(os.path.join(d, name)) and os.path.join(d, name).endswith("ifc")])
    
    total_est_time = \
        sum(map(operator.attrgetter('est_time'), tasks)) * n_files + \
        sum(map(operator.attrgetter('est_time'), tasks_on_aggregate))
        
    def run_task(t, args, aggregate_model=False):
        nonlocal elapsed
        begin_end = (elapsed / total_est_time * 99, (elapsed + t.est_time) / total_est_time * 99)
        task = t(begin_end)
        try:
            task(d, *args)
        except:
            traceback.print_exc(file=sys.stdout)
            # Mark ID as failed
            with open(os.path.join(d, 'failed'), 'w') as f:
                pass
            return False
        elapsed += t.est_time
        return True
    
    for i in range(n_files):
        for t in tasks:
            if not run_task(t, ["%s_%d" % (id, i) if is_multiple else id]):
                break
        # to break out of nested loop
        else: continue
        break
    
   
    for t in tasks_on_aggregate:
        run_task(t, [id, input_files], aggregate_model=True)

    elapsed = 100
    set_progress(id, elapsed)


def process(ids, validation_config, ids_spec = None , callback_url=None):

    try:
        do_process(ids, validation_config, ids_spec)
        status = "success"
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        status = "failure"        
    if callback_url is not None:       
        r = requests.post(callback_url, data={"status": status, "id": ids})
