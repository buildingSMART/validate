import sys, os
import ifcopenshell
from helper import database



import math

def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return f"{s} {size_name[i]}"

ifc_fn = sys.argv[1]
ifc_file = ifcopenshell.open(ifc_fn)

try:
    detected_mvd = ifc_file.header.file_description.description[0].split(" ", 1)[1]
    detected_mvd = detected_mvd[1:-1]
except:
    detected_mvd = "no MVD detected"

try:
    authoring_app = ifc_file.by_type("IfcApplication")[0].ApplicationFullName
except:
    authoring_app = 'no authoring app detected'

with database.Session() as session:
    model = session.query(database.model).filter(database.model.code == ifc_fn[:-4]).all()[0]
    model.size = convert_size(os.path.getsize(ifc_fn))
    model.schema = ifc_file.schema
    model.authoring_application = authoring_app
    model.mvd = detected_mvd
    try:
        model.number_of_elements = len(ifc_file.by_type("IfcBuildingElement"))
    except:
        model.number_of_elements = len(ifc_file.by_type("IfcBuiltElement"))
    model.number_of_geometries = len(ifc_file.by_type("IfcShapeRepresentation"))
    model.number_of_properties = len(ifc_file.by_type("IfcProperty"))

    session.commit()
    session.close()



