import glob
import os
import sys
import shutil
import tempfile

os.environ["environment"] = "development"

from worker import syntax_validation_task, ifc_validation_task
import database
import utils

if __name__ == "__main__":
    i = utils.generate_id()

    # with tempfile.TemporaryDirectory() as tmpdirname:
    tmpdirname = tempfile.mkdtemp()
    if True:
        for fn in glob.glob(os.path.join(os.path.dirname(sys.argv[1]), "*.exp")):
            shutil.copyfile(fn, os.path.join(tmpdirname, os.path.basename(fn)))
            if os.path.exists(fn + ".cache.dat"):
                shutil.copyfile(fn + ".cache.dat", os.path.join(tmpdirname, os.path.basename(fn + ".cache.dat")))
            if os.path.exists(fn[:-4] + ".py"):
                shutil.copyfile(fn[:-4] + ".py", os.path.join(tmpdirname, os.path.basename(fn[:-4] + ".py")))
        shutil.copyfile(sys.argv[1], os.path.join(tmpdirname, i + ".ifc"))

        args = tmpdirname, i

        with database.Session() as session:
            session.add(database.model(args[1], None, None))
            session.commit()

        try:
            syntax_validation_task((0, 1))(*args)
            ifc_validation_task((1, 2))(*args)
        except RuntimeError as e:
            import traceback
            traceback.print_exc()
            pass

        with database.Session() as session:
            m = (
                session.query(database.model)
                .filter(database.model.code == args[1])
                .all()[0]
            )

            for ch in ["syntax", "schema"]:
                if getattr(m, f"status_{ch}") != "v":
                    t = [
                        t
                        for t in m.tasks
                        if isinstance(t, getattr(database, f"{ch}_validation_task"))
                    ][0]
                    for r in t.results:
                        print(r.msg)
                    exit(1)
